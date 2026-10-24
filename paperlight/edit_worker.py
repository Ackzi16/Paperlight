"""Persistent page-local edit analysis/render server. Secrets enter over stdin."""
import base64,json,math,sys
from dataclasses import asdict
import pymupdf as f
from .objects import discover,PageObject,parse,isolate,set_content,validate

MAX_PIXELS=8_000_000


def emit(row):
    print(json.dumps(row,ensure_ascii=True,separators=(',',':')),flush=True)


def serial(obj):
    result=asdict(obj)
    result['drawing']={key:value for key,value in obj.drawing.items() if key in ('color','fill','width','dashes','lineCap','lineJoin','fill_opacity','stroke_opacity','even_odd','closePath')}
    return result


def image(page,scale,alpha=False,clip=None,annots=True):
    pix=page.get_pixmap(matrix=f.Matrix(scale,scale),alpha=alpha,clip=clip,annots=annots,colorspace=f.csRGB)
    data=pix.tobytes('png')
    if len(data)>36*1024*1024:raise ValueError('Edit preview exceeds the memory limit.')
    return dict(png=base64.b64encode(data).decode(),x=pix.x,y=pix.y)


def source_patch(page,scale,rect):
    import io
    from PIL import Image
    # Match the full-page raster's scan sampling, then crop the selected patch.
    pix=page.get_pixmap(matrix=f.Matrix(scale,scale),alpha=False,colorspace=f.csRGB)
    bounds=(f.Rect(rect)*page.rotation_matrix*f.Matrix(scale,scale)).irect
    bounds &= f.IRect(0,0,pix.width,pix.height)
    if bounds.is_empty:raise ValueError('Invalid text preview bounds.')
    cropped=Image.frombytes('RGB',(pix.width,pix.height),pix.samples).crop(tuple(bounds))
    buffer=io.BytesIO();cropped.save(buffer,format='PNG');data=buffer.getvalue()
    if len(data)>36*1024*1024:raise ValueError('Edit preview exceeds the memory limit.')
    return dict(png=base64.b64encode(data).decode(),x=bounds.x0,y=bounds.y0)


def text_preview(doc,page_index,obj,scale):
    from .objects import erase_native_text,fingerprint
    from .typography import FontCatalog,normalized,rgb
    from .richtext import insert
    from dataclasses import replace
    original_selected=None
    if obj.kind!='text':
        original_selected=source_patch(doc[page_index],scale,obj.rect)
    with f.open() as scratch:
        scratch.insert_pdf(doc,from_page=page_index,to_page=page_index,annots=True,widgets=True)
        page=scratch[0]
        catalog=FontCatalog(scratch) if obj.kind=='text' else None
        style=catalog.style(0,obj.rect) if catalog else None
        rect=f.Rect(obj.rect)
        if obj.kind=='text':
            local=replace(obj,digest=fingerprint(page));page=erase_native_text(page,local)
        elif obj.kind=='ocr':
            page.add_redact_annot(rect,fill=(1,1,1),cross_out=False);page.apply_redactions(images=2,graphics=0,text=0)
        else:
            candidates=[a for a in page.annots() or [] if a.type[0]==f.PDF_ANNOT_FREE_TEXT]
            if not candidates:raise ValueError('Text annotation is unavailable.')
            page.delete_annot(min(candidates,key=lambda a:abs(a.rect.tl-rect.tl)))
        emit(dict(kind='layer',layer='before',scale=scale,**image(page,scale)))
        with f.open() as selected:
            target=selected.new_page(width=page.mediabox.width,height=page.mediabox.height)
            target.set_cropbox(page.cropbox);target.set_rotation(page.rotation)
            if obj.kind=='text':
                runs=[dict(text=s['text'],x=s['origin'][0]-rect.x0,y=s['origin'][1]-rect.y0,size=s['size'],color=rgb(s['color']),choice=catalog.by_name.get(normalized(s['font']),style.choice)) for s in obj.spans]
                insert(target,rect,runs)
                clip=(rect+(-2,-2,2,2))*target.rotation_matrix;clip &= target.rect
                selected_layer=image(target,scale,alpha=True,clip=clip,annots=False)
            else:
                selected_layer=original_selected
            emit(dict(kind='layer',layer='selected',scale=scale,**selected_layer))
            set_content(target,b'')
            emit(dict(kind='layer',layer='after',scale=scale,**image(target,scale,alpha=True,annots=False)))


def process(config):
    page_index=int(config['page']);task=config['task']
    with f.open(config['path']) as doc:
        if not doc.authenticate(config['password']):raise ValueError('Protected PDF verification failed.')
        page=doc[page_index]
        scale=min(float(config['scale']),4096/max(page.rect.width,page.rect.height),math.sqrt(MAX_PIXELS/max(1,page.rect.get_area())))
        if not math.isfinite(scale) or scale<=0:raise ValueError('Invalid preview scale.')
        if task=='refresh':
            wanted=list(dict.fromkeys([page_index]+config.get('pages',[])))[:4]
            for n in wanted:
                p=doc[n];factor=min(scale,math.sqrt(MAX_PIXELS/max(1,p.rect.get_area())))
                emit(dict(kind='frame',page=n,scale=factor,**image(p,factor)))
            objects=discover(page,config.get('ocr_words',[]))
            emit(dict(kind='objects',objects=[serial(o) for o in objects][:3000]))
        elif task=='preview':
            obj=PageObject(**config['object']);validate(page,obj)
            if obj.kind in ('text','ocr','annotation'):
                text_preview(doc,page_index,obj,scale);return
            operations=parse(page).operations
            with f.open() as scratch:
                scratch.insert_pdf(doc,from_page=page_index,to_page=page_index,annots=True,widgets=True)
                p=scratch[0];xref=scratch.get_new_xref();scratch.update_object(xref,'<<>>');scratch.update_stream(xref,b'');p.set_contents(xref)
                # Three layers preserve foreground occlusion throughout a gesture.
                scratch.update_stream(xref,isolate(operations,0,obj.start))
                before=image(p,scale,alpha=False,annots=False)
                emit(dict(kind='layer',layer='before',scale=scale,**before))
                scratch.update_stream(xref,isolate(operations,obj.start,obj.end))
                bounds=[f.Rect(r) for kind,r in p.get_bboxlog() if kind!='ignore-text']
                clip=f.Rect(obj.rect)
                for r in bounds:clip|=r
                clip=(clip+(-2,-2,2,2))*p.rotation_matrix;clip &= p.rect
                selected=image(p,scale,alpha=True,clip=clip,annots=False)
                emit(dict(kind='layer',layer='selected',scale=scale,**selected))
                scratch.update_stream(xref,isolate(operations,obj.end,len(operations)))
                emit(dict(kind='layer',layer='after',scale=scale,**image(p,scale,alpha=True,annots=True)))
        else:raise ValueError('Invalid edit worker request.')


def main():
    global emit
    output=emit
    for line in sys.stdin:
        if len(line)>12*1024*1024:return 1
        try:
            config=json.loads(line);request=config['request']
            emit=lambda row:output(dict(row,request=request))
            process(config);emit(dict(kind='done'))
        except Exception:
            # Native/document exception values may contain private document text.
            emit(dict(kind='error',message='The edit preview could not be prepared.'))
    return 0
