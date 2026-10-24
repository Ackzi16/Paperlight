"""Page object discovery and instance-specific PDF edits.

Only isolated, balanced native graphics scopes are writable. Unmapped graphics
remain visible in the inspector but are never erased by rectangle redaction.
"""
from dataclasses import dataclass, field
import hashlib
from collections import Counter
import math
import pymupdf as fitz
from pypdf.generic import ContentStream, DecodedStreamObject, FloatObject
from pypdf.errors import PyPdfError

PAINT={b'S',b's',b'f',b'F',b'f*',b'B',b'B*',b'b',b'b*'}
TEXT={b'Tj',b'TJ',b"'",b'"'}
PATH={b'm',b'l',b'c',b'v',b'y',b're',b'h'}
MAX_CONTENT=16*1024*1024

@dataclass
class PageObject:
    kind: str
    rect: tuple
    digest: str
    title: str=''
    text: str=''
    spans: list=field(default_factory=list)
    writable: bool=True
    reason: str=''
    start: int=-1
    end: int=-1
    ctm: tuple=(1,0,0,1,0,0)
    xref: int=0
    drawing: dict=field(default_factory=dict)
    path: list=field(default_factory=list)
    quad: list=field(default_factory=list)


def fingerprint(page):
    return hashlib.sha256(page.read_contents()).hexdigest()


def object_identity(obj):
    value=obj if isinstance(obj,dict) else vars(obj)
    return (value['digest'],value['kind'],value['start'],value['end'],value['xref'],tuple(value['rect']))


def parse(page):
    data=page.read_contents()
    if len(data)>MAX_CONTENT:
        raise ValueError('This page is too complex for object editing.')
    stream=DecodedStreamObject();stream.set_data(data)
    result=ContentStream(stream,None)
    if len(result.operations)>150000:
        raise ValueError('This page is too complex for object editing.')
    return result


def encode(operations):
    stream=DecodedStreamObject();stream.set_data(b'')
    result=ContentStream(stream,None);result.operations=operations
    return result.get_data()


def set_content(page,data):
    doc=page.parent;xref=doc.get_new_xref()
    doc.update_object(xref,'<<>>');doc.update_stream(xref,data)
    page.set_contents(xref)


def scopes(operations):
    stack=[];ctm=fitz.Identity;path=False;text=False;clipped=False
    candidates=[]
    for index,(args,op) in enumerate(operations):
        if op==b'q': stack.append((index,fitz.Matrix(ctm),path,text,clipped))
        elif op==b'Q':
            if not stack: return []
            start,old,had_path,had_text,old_clip=stack.pop()
            body=operations[start:index+1]
            paints=[code for _,code in body if code in PAINT or code in TEXT or code==b'Do' or code==b'INLINE IMAGE' or code==b'sh']
            if len(paints)==1 and (paints[0] in PAINT or paints[0]==b'Do') and not had_path and not path and not had_text and not old_clip and not any(code in (b'W',b'W*',b'gs',b'BX',b'EX',b'BDC',b'BMC',b'EMC') for _,code in body):
                candidates.append((start,index+1,tuple(old),paints[0]))
            ctm=old;clipped=old_clip
        elif op==b'cm' and len(args)==6: ctm=fitz.Matrix(*map(float,args))*ctm
        elif op==b'BT': text=True
        elif op==b'ET': text=False
        elif op in PATH: path=True
        elif op in PAINT or op==b'n': path=False
        elif op in (b'W',b'W*'): clipped=True
    if stack: return []
    # Choose the tightest enclosing balanced graphics scope for each paint.
    selected=[]
    for item in sorted(candidates,key=lambda x:x[1]-x[0]):
        if not any(max(item[0],other[0])<min(item[1],other[1]) for other in selected): selected.append(item)
    return sorted(selected)


def isolate(operations,start,end):
    result=[];mode=0;stack=[]
    for n,(args,op) in enumerate(operations):
        if op==b'q': stack.append(mode)
        elif op==b'Q' and stack: mode=stack.pop()
        elif op==b'Tr': mode=int(args[0])
        if start<=n<end: result.append((args,op))
        elif op in PAINT: result.append(([],b'n'))
        elif op in (b'Do',b'sh',b'INLINE IMAGE'): continue
        elif op in TEXT:
            result.extend([([FloatObject(3)],b'Tr'),(args,op),([FloatObject(mode)],b'Tr')])
        else: result.append((args,op))
    return encode(result)


def shape_kind(drawing):
    items=drawing['items']
    if len(items)==1 and items[0][0]=='re': return 'Rectangle'
    if len(items)==1 and items[0][0]=='l': return 'Line'
    if len(items)==4 and all(item[0]=='c' for item in items) and abs(items[0][1]-items[-1][-1])<.1:
        # A closed four-curve path is only an ellipse when its control geometry
        # matches the standard cubic ellipse construction.
        r=drawing['rect'];cx,cy=(r.x0+r.x1)/2,(r.y0+r.y1)/2
        if r.width>0 and r.height>0:
            endpoints=[items[0][1]]+[i[-1] for i in items]
            if all(min(abs(p.x-cx)+abs(abs(p.y-cy)-r.height/2),abs(p.y-cy)+abs(abs(p.x-cx)-r.width/2))<.1 for p in endpoints): return 'Ellipse'
    return 'Graphic'


def paragraphs(block):
    groups=[]
    for line in block['lines']:
        r=fitz.Rect(line['bbox']);match=None
        for group in reversed(groups):
            last=fitz.Rect(group[-1]['bbox']);advance=r.y0-last.y0
            overlap=max(0,min(r.x1,last.x1)-max(r.x0,last.x0))
            if .3*min(r.height,last.height)<advance<1.8*max(r.height,last.height) and overlap>.25*min(r.width,last.width):
                match=group;break
        if match is None:groups.append([line])
        else:match.append(line)
    result=[]
    for lines in groups:
        rect=fitz.Rect(lines[0]['bbox'])
        for line in lines[1:]:rect|=fitz.Rect(line['bbox'])
        result.append(dict(type=0,bbox=tuple(rect),lines=lines))
    return result


def text_spans(page):
    return [span for block in page.get_text('dict',flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks'] if block['type']==0 for line in block['lines'] for span in line['spans']]


def span_identity(span):
    return span['font'],span['text'],tuple(round(v,3) for v in span['origin'])


def validate_text_target(page,obj,rect):
    selected=Counter(span_identity(span) for span in obj.spans)
    all_spans=text_spans(page);counts=Counter(span_identity(span) for span in all_spans)
    if any(counts[key]>count for key,count in selected.items()):
        raise ValueError('Identical overlapping text cannot be edited separately.')
    for span in all_spans:
        if span_identity(span) not in selected and (fitz.Rect(span['bbox'])&fitz.Rect(rect)).get_area()>1:
            raise ValueError('This text box would overlap other text. Move or resize it first.')


def discover(page,ocr_words=()):
    digest=fingerprint(page);result=[]
    exclusion=[]
    for widget in page.widgets() or []:
        exclusion.append(widget.rect)
        result.append(PageObject('form',tuple(widget.rect),digest,'Form field',xref=widget.xref))
    for annot in page.annots() or []:
        exclusion.append(annot.rect)
        writable=annot.type[0]==fitz.PDF_ANNOT_FREE_TEXT
        result.append(PageObject('annotation',tuple(annot.rect),digest,annot.type[1],text=annot.info.get('content',''),xref=annot.xref,writable=writable,reason='' if writable else 'This annotation type uses its original markup tool.'))
    traces=page.get_texttrace()
    hidden=[fitz.Rect(t['bbox']) for t in traces if t['type']==3]
    hidden_origins={(round(ch[2][0],1),round(ch[2][1],1)) for trace in traces if trace['type']==3 for ch in trace['chars']}
    blocks=page.get_text('dict',flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']
    for block in [part for b in blocks if b['type']==0 for part in paragraphs(b)]:
        rect=fitz.Rect(block['bbox'])
        if any((rect&r).get_area()>rect.get_area()*.4 for r in exclusion): continue
        spans=[];lines=[]
        for line in block['lines']:
            lines.append(''.join(span['text'] for span in line['spans']))
            spans.extend(dict(span,line=line['bbox'],direction=line['dir']) for span in line['spans'])
        if not ''.join(lines).strip(): continue
        is_ocr=all('glyphless' in span['font'].lower() or (round(span['origin'][0],1),round(span['origin'][1],1)) in hidden_origins for span in spans)
        inside_traces=[trace for trace in traces if rect.contains(fitz.Rect(trace['bbox']).tl+(fitz.Rect(trace['bbox']).br-fitz.Rect(trace['bbox']).tl)*.5)]
        if inside_traces and all(trace['type']==3 for trace in inside_traces): is_ocr=True
        result.append(PageObject('ocr' if is_ocr else 'text',tuple(rect),digest,'Recognized text' if is_ocr else 'Text box',text='\n'.join(lines),spans=spans))
    groups={}
    for word in ocr_words:
        if word.get('source')=='ocr' and not any(fitz.Rect(o.rect).intersects(word['rect']) for o in result if o.kind in ('text','ocr')):
            groups.setdefault(word.get('block',0),[]).append(word)
    for words in groups.values():
        rect=fitz.Rect(words[0]['rect'])
        for w in words[1:]: rect|=fitz.Rect(w['rect'])
        result.append(PageObject('ocr',tuple(rect),digest,'Recognized text',text=' '.join(w['text'] for w in words)))
    try:
        parsed=parse(page);operations=parsed.operations;candidates=scopes(operations)
        # A bounded page-local probe gives geometry without assuming that MuPDF
        # display-list sequence numbers are PDF operator indexes.
        budget=max(1,min(400,2_000_000//max(1,len(operations))))
        candidates=candidates[:budget]
        with fitz.open() as probe:
            probe.insert_pdf(page.parent,from_page=page.number,to_page=page.number,annots=False,widgets=False)
            pp=probe[0]
            scratch=probe.get_new_xref();probe.update_object(scratch,'<<>>');probe.update_stream(scratch,b'');pp.set_contents(scratch)
            direct_images={row[7] for row in page.get_images(full=True) if row[-1]==0}
            for start,end,ctm,paint in candidates:
                if paint==b'Do':
                    name=next(str(a[0]).lstrip('/') for a,o in operations[start:end] if o==b'Do')
                    if name not in direct_images: continue
                probe.update_stream(scratch,isolate(operations,start,end))
                if paint==b'Do':
                    images=pp.get_image_info()
                    if len(images)!=1: continue
                    matrix=fitz.Matrix(images[0]['transform'])
                    quad=[list(fitz.Point(*p)*matrix) for p in ((0,0),(1,0),(1,1),(0,1))]
                    result.append(PageObject('image',tuple(images[0]['bbox']),digest,'Image',start=start,end=end,ctm=ctm,quad=quad))
                else:
                    drawings=pp.get_drawings()
                    if len(drawings)!=1: continue
                    drawing=drawings[0]
                    if any(not math.isfinite(v) for v in drawing['rect']): continue
                    from .geometry import path_from_drawing,quad_for_path
                    path=path_from_drawing(drawing)
                    if path and path[-1][0]!='Z' and any(op==b'h' for _,op in operations[start:end]):path.append(['Z'])
                    quad=[list(p) for p in quad_for_path(path,drawing['rect'])]
                    result.append(PageObject('shape',tuple(drawing['rect']),digest,shape_kind(drawing),start=start,end=end,ctm=ctm,drawing=drawing,path=path,quad=quad))
    except (ValueError,TypeError,KeyError,IndexError,RuntimeError,PyPdfError):
        pass
    # Show unsupported native paths too, but fail closed rather than broad erase.
    for drawing in page.get_drawings():
        r=drawing['rect']
        if not any(o.kind=='shape' and all(abs(a-b)<.2 for a,b in zip(o.rect,r)) for o in result):
            result.append(PageObject('shape',tuple(r),digest,shape_kind(drawing),writable=False,reason='This graphic has clipping, shared resources or a complex content stream.',drawing=drawing))
    return result


def validate(page,obj):
    if fingerprint(page)!=obj.digest: raise ValueError('The page changed. Select the object again.')
    if not obj.writable: raise ValueError(obj.reason)


def edit_graphic(page,obj,rect=None,delete=False,stroke=None,fill=None,width=None,transform=None,path=None):
    validate(page,obj)
    if obj.kind not in ('shape','image') or obj.start<0: raise ValueError('This object cannot be changed by the graphic editor.')
    for values in (stroke,fill):
        if values is not None and (len(values)!=3 or any(not math.isfinite(v) or not 0<=v<=1 for v in values)): raise ValueError('Invalid object color.')
    if width is not None and (not math.isfinite(width) or not .1<=width<=30): raise ValueError('Invalid stroke width.')
    operations=parse(page).operations
    if not any(a==obj.start and b==obj.end for a,b,_,_ in scopes(operations)): raise ValueError('The object source could not be verified.')
    body=operations[obj.start:obj.end]
    if delete: replacement=[]
    else:
        before=fitz.Rect(obj.rect);after=fitz.Rect(rect or obj.rect)
        if not all(math.isfinite(v) for v in after) or after.width<0 or after.height<0: raise ValueError('Invalid object dimensions.')
        sx=after.width/before.width if before.width else 1
        sy=after.height/before.height if before.height else 1
        transform=fitz.Matrix(transform) if transform is not None else fitz.Matrix(sx,0,0,sy,after.x0-before.x0*sx,after.y0-before.y0*sy)
        if any(not math.isfinite(v) for v in transform) or abs(transform.a*transform.d-transform.b*transform.c)<1e-8:raise ValueError('Invalid object transform.')
        if path is not None:
            from .geometry import valid_path
            if obj.kind!='shape' or not valid_path(path):raise ValueError('Invalid editable path.')
        p=page.transformation_matrix;c=fitz.Matrix(obj.ctm)
        if abs(c.a*c.d-c.b*c.c)<1e-8: raise ValueError('This object has a singular transform.')
        matrix=c*p*transform*~p*~c
        replacement=[([],b'q'),([FloatObject(v) for v in matrix],b'cm')]
        current=fitz.Matrix(obj.ctm);stack=[]
        for args,op in body:
            if op==b'q':stack.append(fitz.Matrix(current))
            elif op==b'Q':current=stack.pop()
            elif op==b'cm':current=fitz.Matrix(*map(float,args))*current
            if path is not None and op in PATH:continue
            if op in PAINT:
                if path is not None:
                    from .geometry import path_operators
                    if abs(current.a*current.d-current.b*current.c)<1e-8:raise ValueError('Invalid object transform.')
                    replacement.extend(path_operators(path,~(current*page.transformation_matrix)))
                if stroke is not None: replacement.append(([FloatObject(v) for v in stroke],b'RG'))
                if fill is not None: replacement.append(([FloatObject(v) for v in fill],b'rg'))
                if width is not None: replacement.append(([FloatObject(width)],b'w'))
            if op in PAINT and fill is not None and op in (b'S',b's'): op=b'B' if op==b'S' else b'b'
            if op in PAINT and stroke is not None and op in (b'f',b'F',b'f*'): op=b'B*' if op==b'f*' else b'B'
            replacement.append((args,op))
        replacement.append(([],b'Q'))
    set_content(page,encode(operations[:obj.start]+replacement+operations[obj.end:]))


def isolate_form_instances(page):
    """Give every invoked Form its own stream/resource tree before redaction.

    PDF redaction may rewrite shared Form streams globally. New names per Do
    occurrence isolate repeated uses on this page as well as other pages.
    """
    if not page.get_xobjects(): return page
    doc=page.parent;budget=[0,0];serial=[0]

    def dictionary(kind,value):
        if kind=='xref': value=doc.xref_object(int(value.split()[0]),compressed=False)
        if kind not in ('dict','xref') or not value.lstrip().startswith('<<') or len(value)>2_000_000:
            raise ValueError('This shared graphic is too complex for text editing.')
        xref=doc.get_new_xref();doc.update_object(xref,value);return xref

    def resources(owner,fallback=None):
        kind,value=doc.xref_get_key(owner,'Resources')
        if kind=='null' and fallback is not None:
            kind,value='xref',str(fallback)+' 0 R'
        if kind=='null':
            seen=set();current=owner
            while current not in seen:
                seen.add(current);pk,pv=doc.xref_get_key(current,'Parent')
                if pk!='xref':break
                current=int(pv.split()[0]);kind,value=doc.xref_get_key(current,'Resources')
                if kind!='null':break
        return dictionary(kind,value)

    def rewrite(data,res,ancestors):
        if len(data)>MAX_CONTENT: raise ValueError('This shared graphic is too complex for text editing.')
        stream=DecodedStreamObject();stream.set_data(data)
        operations=ContentStream(stream,None).operations
        if len(operations)>150000: raise ValueError('This shared graphic is too complex for text editing.')
        kind,value=doc.xref_get_key(res,'XObject')
        if kind=='null':return data
        objects=dictionary(kind,value);doc.xref_set_key(res,'XObject',f'{objects} 0 R')
        rewritten=[]
        for args,op in operations:
            if op==b'Do':
                name=str(args[0]).lstrip('/')
                if any(c in name for c in '/#[]<>%()'):
                    raise ValueError('This shared graphic uses an unsupported resource name.')
                kind,value=doc.xref_get_key(objects,name)
                if kind=='xref':
                    old=int(value.split()[0])
                    if doc.xref_get_key(old,'Subtype')==('name','/Form'):
                        if old in ancestors or len(ancestors)>16:
                            raise ValueError('This shared graphic has recursive resources.')
                        budget[0]+=1;source=doc.xref_stream(old);budget[1]+=len(source)
                        if budget[0]>300 or budget[1]>32*1024*1024:
                            raise ValueError('This shared graphic is too complex for text editing.')
                        cloned=doc.get_new_xref();doc.update_object(cloned,'<<>>');doc.xref_copy(old,cloned)
                        child=resources(old,res);doc.xref_set_key(cloned,'Resources',f'{child} 0 R')
                        doc.update_stream(cloned,rewrite(source,child,ancestors|{old}))
                        serial[0]+=1;new_name='PLobject'+str(serial[0])
                        while doc.xref_get_key(objects,new_name)[0]!='null':
                            serial[0]+=1;new_name='PLobject'+str(serial[0])
                        doc.xref_set_key(objects,new_name,f'{cloned} 0 R')
                        from pypdf.generic import NameObject
                        args=[NameObject('/'+new_name)]
            rewritten.append((args,op))
        return encode(rewritten)

    res=resources(page.xref)
    data=rewrite(page.read_contents(),res,set())
    doc.xref_set_key(page.xref,'Resources',f'{res} 0 R');set_content(page,data)
    return doc.reload_page(page)


def erase_native_text(page,obj):
    validate(page,obj)
    rect=fitz.Rect(obj.rect)
    validate_text_target(page,obj,rect)
    page=isolate_form_instances(page)
    page.add_redact_annot(rect,fill=None,cross_out=False)
    page.apply_redactions(images=0,graphics=0,text=0)
    return page
