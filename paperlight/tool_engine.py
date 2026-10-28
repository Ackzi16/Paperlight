"""Bounded local PDF utilities. Invoked only by the isolated toolbox worker."""
import csv,difflib,io,json,math,os,tempfile,zipfile
from pathlib import Path
import pymupdf as f
from PIL import Image,ImageOps,ImageEnhance
from .core import page_range,insert_ocr_words,atomic_pdf_write,file_version
from .security import access
from .tool_catalog import BY_KEY,options_for

MAX_PIXELS=8_000_000
EXTRACT={'pdf_images','text','tables','extract_images','compare','info'}
LAYOUT={'resize','nup','booklet','tiles','long_page','overlay'}

def validate_document(doc):
    if not doc.is_pdf or not 1<=len(doc)<=10000:raise ValueError('Open a PDF containing 1 to 10,000 pages.')
    for page in doc:
        if any(not math.isfinite(v) or not 0<v<=20000 for v in (page.rect.width,page.rect.height)):raise ValueError('This document contains unsupported page dimensions.')
        if any(row[2]*row[3]>120_000_000 for row in page.get_images(full=True)):raise ValueError('This document contains an image exceeding the supported size.')
        if any(a.type[0]==f.PDF_ANNOT_REDACT for a in page.annots() or []):raise ValueError('Apply or undo pending redactions before exporting tools results.')

def open_pdf(path,password=''):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>1024**3:raise ValueError('The input PDF is missing or exceeds 1 GiB.')
    doc=f.open(path)
    try:
        permissions=access(doc,password);validate_document(doc)
        return doc,permissions
    except Exception:doc.close();raise

def raster(page,dpi=150):
    scale=min(dpi/72,math.sqrt(MAX_PIXELS/max(1,page.rect.get_area())),4096/max(page.rect.width,page.rect.height))
    return page.get_pixmap(matrix=f.Matrix(scale,scale),alpha=False,colorspace=f.csRGB)

def text_of(doc,pages):
    parts=[];size=0
    for n in pages:
        text=doc[n].get_text(sort=True);size+=len(text)
        if size>2_000_000:raise ValueError('Text export exceeds the supported size. Export a smaller page range.')
        parts.append(text)
    return parts

def csv_cell(value):
    text='' if value is None else str(value)
    if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r')):return "'"+text
    return text

def sanitize(doc):
    doc.scrub(attached_files=True,embedded_files=True,hidden_text=False,javascript=True,metadata=True,
              redactions=False,remove_links=True,reset_fields=False,reset_responses=True,thumbnails=True,xml_metadata=True)
    doc.xref_set_key(doc.pdf_catalog(),'OpenAction','null')
    for xref in range(1,doc.xref_length()):
        keys=doc.xref_get_keys(xref)
        kind=doc.xref_get_key(xref,'Type')
        if 'AA' in keys and (kind in (('name','/Page'),('name','/Annot'),('name','/Catalog')) or 'FT' in keys or doc.xref_get_key(xref,'Subtype')==('name','/Widget')):doc.xref_set_key(xref,'AA','null')
        if doc.xref_get_key(xref,'S') in tuple(('name',name) for name in ('/JavaScript','/Launch','/GoToR','/GoToE','/URI','/SubmitForm','/ImportData','/Rendition','/Movie','/Sound')):
            if doc.xref_is_stream(xref):doc.update_stream(xref,b'')
            doc.update_object(xref,'<<>>')

def paper(name,landscape=False):
    width,height=f.paper_size(name)
    return (height,width) if landscape else (width,height)

def show_page(target,rect,source,n,**options):
    if source[n].get_contents():target.show_pdf_page(rect,source,n,**options)

def replace_pages(doc,result,toc=None):
    if not 1<=len(result)<=10000:raise ValueError('The result exceeds the supported page count.')
    doc.set_toc([]);doc.delete_pages(0,len(doc)-1);doc.insert_pdf(result,widgets=True)
    if toc:doc.set_toc(toc)

def layout(doc,key,o,other_password,progress):
    doc.bake(annots=True,widgets=True)
    with f.open() as source:
        source.insert_pdf(doc)
        with f.open() as result:
            if key=='overlay':
                overlay,(_,readonly,copy_allowed)=open_pdf(o['other'],other_password)
                with overlay:
                    if readonly or not copy_allowed:raise ValueError('Unlock the overlay PDF with its owner password first.')
                    if len(overlay) not in (1,len(doc)):raise ValueError('Use a one-page overlay or one with the same number of pages.')
                    overlay.bake(annots=True,widgets=True)
                    for n,page in enumerate(doc):
                        show_page(page,page.rect*page.derotation_matrix,overlay,0 if len(overlay)==1 else n,rotate=page.rotation,overlay=True)
                        progress(n+1,len(doc))
                return
            if key=='long_page':
                height=sum(p.rect.height for p in source);width=max(p.rect.width for p in source)
                if height>20000:raise ValueError('The joined page exceeds 20,000 PDF points. Join fewer pages.')
                target=result.new_page(width=width,height=height);y=0
                for n,p in enumerate(source):
                    show_page(target,f.Rect((width-p.rect.width)/2,y,(width+p.rect.width)/2,y+p.rect.height),source,n)
                    y+=p.rect.height;progress(n+1,len(source))
            elif key=='tiles':
                columns=int(o['columns']);rows=int(o['rows'])
                if len(source)*columns*rows>10000:raise ValueError('The result exceeds the supported page count.')
                for n,p in enumerate(source):
                    for row in range(rows):
                        for column in range(columns):
                            clip=f.Rect(p.rect.x0+column*p.rect.width/columns,p.rect.y0+row*p.rect.height/rows,p.rect.x0+(column+1)*p.rect.width/columns,p.rect.y0+(row+1)*p.rect.height/rows)
                            target=result.new_page(width=clip.width,height=clip.height);show_page(target,target.rect,source,n,clip=clip)
                    progress(n+1,len(source))
            else:
                per_sheet=1 if key=='resize' else 2 if key=='booklet' else int(o['per_sheet'])
                columns,rows={1:(1,1),2:(2,1),4:(2,2),6:(2,3),9:(3,3)}[per_sheet]
                width,height=paper(o['paper'],per_sheet==2)
                margin=float(o['margin']);cellw=(width-2*margin)/columns;cellh=(height-2*margin)/rows
                if min(cellw,cellh)<=4:raise ValueError('Margins leave no room for page content.')
                order=list(range(len(source)))
                if key=='booklet':
                    count=((len(source)+3)//4)*4;order=[]
                    for low in range(0,count//2,2):order.extend((count-1-low,low,low+1,count-2-low))
                for at in range(0,len(order),per_sheet):
                    target=result.new_page(width=width,height=height)
                    for slot,n in enumerate(order[at:at+per_sheet]):
                        if n>=len(source):continue
                        x=margin+(slot%columns)*cellw;y=margin+(slot//columns)*cellh
                        show_page(target,f.Rect(x+3,y+3,x+cellw-3,y+cellh-3),source,n)
                    progress(min(at+per_sheet,len(order)),len(order))
            replace_pages(doc,result)

def stamp(page,text,size,position,opacity=1,angle=0):
    if not text:raise ValueError('Enter stamp text.')
    with f.open() as overlay:
        p=overlay.new_page(width=page.rect.width,height=page.rect.height)
        font=f.Font('china-s') if any(ord(c)>127 for c in text) else f.Font('helv')
        size=min(float(size),(p.rect.width-48)/max(.1,font.text_length(text,fontsize=1)))
        if size<3:raise ValueError('The stamp text is too long for this page.')
        width=font.text_length(text,fontsize=size)
        x=24 if position.endswith('left') else p.rect.width-24-width if position.endswith('right') else (p.rect.width-width)/2
        y=24+font.ascender*size if position.startswith('Top') else p.rect.height-24 if position.startswith('Bottom') else p.rect.height/2
        writer=f.TextWriter(p.rect);writer.append((x,y),text,font=font,fontsize=size)
        center=f.Point(x+width/2,y-size*(font.ascender+font.descender)/2)
        writer.write_text(p,color=(.25,.25,.25),opacity=opacity,morph=(center,f.Matrix(angle)))
        page.show_pdf_page(page.rect*page.derotation_matrix,overlay,0,rotate=page.rotation,overlay=True)

def transform(doc,key,raw,pages,other_password='',progress=lambda *a:None):
    tool=BY_KEY[key];o=options_for(tool,raw)
    if key in LAYOUT:return layout(doc,key,o,other_password,progress)
    if key=='compress':
        if o['images']:doc.rewrite_images(dpi_threshold=math.ceil(o['dpi']*1.25),dpi_target=int(o['dpi']),quality=int(o['quality']),bitonal=False)
    elif key=='metadata':
        data=doc.metadata
        for field in ('title','author','subject','keywords'):
            if o[field]:data[field]=o[field]
        doc.set_metadata(data)
    elif key=='clear_metadata':doc.set_metadata({});doc.del_xml_metadata()
    elif key=='bookmarks':
        rows=[]
        for line in o['bookmarks'].splitlines():
            if not line.strip():continue
            pieces=line.split('|',2)
            if len(pieces)!=3:raise ValueError('Use level | page | title for each bookmark.')
            level,page=int(pieces[0]),int(pieces[1]);title=pieces[2].strip()
            if not 1<=level<=20 or not 1<=page<=len(doc) or not title or len(title)>1000:raise ValueError('Invalid bookmark level, page or title.')
            if level>(rows[-1][0]+1 if rows else 1):raise ValueError('Bookmark levels must increase one at a time from 1.')
            rows.append([level,title,page])
        if not rows and not o['clear']:raise ValueError('Enter bookmarks or choose Clear all bookmarks.')
        doc.set_toc([] if o['clear'] else rows)
    elif key in ('watermark','numbers'):
        for at,n in enumerate(pages):
            text=o['text']
            if key=='numbers':
                for token,value in (('{page}',n+1),('{total}',len(doc)),('{number}',int(o['start'])+at)):text=text.replace(token,str(value))
            stamp(doc[n],text,o['size'],o['position'],o.get('opacity',100)/100,o.get('angle',0));progress(at+1,len(pages))
    elif key=='blank':
        before=int(o['before'])-1;count=int(o['count'])
        if not 0<=before<=len(doc) or len(doc)+count>10000:raise ValueError('Invalid insertion page or page count.')
        width,height=paper(o['paper'])
        for n in range(count):doc.new_page(pno=before+n,width=width,height=height)
    elif key=='duplicate':
        if len(doc)+len(pages)>10000:raise ValueError('The result exceeds the supported page count.')
        with f.open() as copies:
            for n in pages:copies.insert_pdf(doc,from_page=n,to_page=n,widgets=True)
            doc.insert_pdf(copies,start_at=max(pages)+1,widgets=True,join_duplicates=False)
    elif key=='reverse':doc.select(list(reversed(range(len(doc)))))
    elif key=='rotate':
        for n in pages:doc[n].set_rotation((doc[n].rotation+int(o['degrees']))%360)
    elif key=='keep_pages':doc.select(pages)
    elif key=='remove_pages':
        if len(pages)>=len(doc):raise ValueError('Keep at least one page in the document.')
        doc.delete_pages(pages)
    elif key=='repair':pass  # The verified full rewrite rebuilds the cross-reference table.
    elif key=='crop':
        for n in pages:
            p=doc[n];rect=p.cropbox+(o['left'],o['top'],-o['right'],-o['bottom'])
            if min(rect.width,rect.height)<18:raise ValueError('Crop margins leave less than 18 points of page content.')
            p.set_cropbox(rect)
    elif key=='flatten':doc.bake(annots=True,widgets=True)
    elif key=='annotations':
        for n in pages:
            p=doc[n]
            for a in list(p.annots() or []):p.delete_annot(a)
    elif key=='images':
        seen=set()
        for p in doc:
            for row in p.get_images(full=True):
                if row[0] not in seen:p.delete_image(row[0]);seen.add(row[0])
    elif key=='blank_pages':
        blank=[]
        for n,p in enumerate(doc):
            if not p.get_text().strip() and not list(p.annots() or []) and not list(p.widgets() or []) and not p.get_links():
                pix=raster(p,36)
                if all(v>=250 for v in pix.samples):blank.append(n)
            progress(n+1,len(doc))
        if len(blank)==len(doc):blank=blank[1:]
        if blank:doc.delete_pages(blank)
    elif key=='sanitize':sanitize(doc)
    elif key=='unlock_forms':
        for p in doc:
            for widget in p.widgets() or []:
                widget.field_flags &= ~f.PDF_FIELD_IS_READ_ONLY;widget.update()
    elif key in ('grayscale','invert','contrast'):
        toc=doc.get_toc()
        with f.open() as result:
            for n,p in enumerate(doc):
                pix=raster(p,o['dpi']);image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                if key=='grayscale':image=ImageOps.grayscale(image).convert('RGB')
                elif key=='invert':image=ImageOps.invert(image)
                else:image=ImageEnhance.Contrast(image).enhance(o['contrast']/100)
                buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=int(o['quality']))
                target=result.new_page(width=p.rect.width,height=p.rect.height);target.insert_image(target.rect,stream=buffer.getvalue())
                words=[]
                for word in p.get_text('words'):
                    rect=f.Rect(word[:4])*p.rotation_matrix;words.append(dict(rect=list(rect),text=word[4],source='ocr'))
                if len(words)>50000:raise ValueError('This page exceeds the supported text size.')
                insert_ocr_words(target,words);progress(n+1,len(doc))
            replace_pages(doc,result,toc)
    else:raise ValueError('Unknown PDF transformation.')
    validate_document(doc)

def extract(doc,key,o,pages,destination,other_password,progress,protected=None):
    if key=='text':destination.write_text('\n\f\n'.join(text_of(doc,pages)),encoding='utf-8')
    elif key=='compare':
        other,(_,_,copy_allowed)=open_pdf(o['other'],other_password)
        with other:
            if not copy_allowed:raise ValueError('Copying text from the comparison PDF is restricted.')
            other_pages=range(len(other)) if pages==list(range(len(doc))) else [n for n in pages if n<len(other)]
            a='\n'.join(text_of(doc,pages)).splitlines();b='\n'.join(text_of(other,other_pages)).splitlines()
            if len(a)+len(b)>50000:raise ValueError('Compare a smaller page range.')
            differences=list(difflib.unified_diff(a,b,fromfile='Current PDF',tofile='Other PDF',lineterm=''))
            report='\n'.join(differences) if differences else 'No text differences found.\n' if any(line.strip() for line in a+b) else 'No searchable text was found. Run Recognize text first.\n'
            destination.write_text('Text-only comparison: images and layout are not compared.\n\n'+report,encoding='utf-8')
    elif key=='info':
        data=dict(pages=len(doc),metadata=doc.metadata,permissions=doc.permissions,bookmarks=doc.get_toc(),attachments=doc.embfile_names(),page_info=[])
        data['encrypted']=bool(protected if protected is not None else data['metadata'].get('encryption'))
        if protected is False:data['metadata']['encryption']=None
        for n,p in enumerate(doc):
            data['page_info'].append(dict(page=n+1,width=p.rect.width,height=p.rect.height,rotation=p.rotation,fonts=sorted({row[3] for row in p.get_fonts()}),annotations=len(list(p.annots() or [])),form_fields=len(list(p.widgets() or []))))
            progress(n+1,len(doc))
        destination.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        count=0;seen=set()
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
            for at,n in enumerate(pages):
                page=doc[n]
                if key=='pdf_images':
                    pix=raster(page,o['dpi']);extension='png' if o['format']=='PNG' else 'jpg'
                    data=pix.tobytes('png') if extension=='png' else pix.tobytes('jpeg',jpg_quality=int(o['quality']))
                    archive.writestr(f'page-{n+1:05d}.{extension}',data);count+=1
                elif key=='extract_images':
                    for row in page.get_images(full=True):
                        if row[0] in seen:continue
                        seen.add(row[0]);data=doc.extract_image(row[0])
                        if data:
                            extension=data['ext'] if data['ext'] in ('png','jpg','jpeg','jpx','jp2','tif','tiff','bmp','jbig2','jb2') else 'bin'
                            archive.writestr(f'image-{count+1:05d}.{extension}',data['image']);count+=1
                elif key=='tables':
                    tables=page.find_tables()
                    for table in tables.tables:
                        output=io.StringIO(newline='');writer=csv.writer(output)
                        for row in table.extract():writer.writerow([csv_cell(value) for value in row])
                        archive.writestr(f'page-{n+1:05d}-table-{count+1:04d}.csv',output.getvalue().encode('utf-8-sig'));count+=1
                progress(at+1,len(pages))
            if count==0:archive.writestr('README.txt','No extractable images or native tables were found. Scanned content may need OCR first.')

def images_to_pdf(paths,options,progress):
    doc=f.open()
    try:
        for at,path in enumerate(paths):
            if Path(path).stat().st_size>1024**3:raise ValueError('An input image exceeds 1 GiB.')
            with Image.open(path) as original:
                for frame in range(getattr(original,'n_frames',1)):
                    original.seek(frame)
                    if original.width*original.height>120_000_000:raise ValueError('An input image exceeds the supported pixel size.')
                    image=ImageOps.exif_transpose(original).convert('RGBA');background=Image.new('RGB',image.size,'white');background.paste(image,mask=image.getchannel('A'))
                    buffer=io.BytesIO();background.save(buffer,format='PNG');width,height=paper(options['paper'])
                    page=doc.new_page(width=width,height=height);page.insert_image(page.rect+ (18,18,-18,-18),stream=buffer.getvalue())
                    if len(doc)>10000:raise ValueError('The result exceeds the supported page count.')
            progress(at+1,len(paths))
        return doc
    except Exception:doc.close();raise

def execute(config,emit=lambda row:None):
    """Export each input atomically; completed batch outputs survive cancellation."""
    key=config['tool'];tool=BY_KEY[key];options=options_for(tool,config.get('options',{}))
    inputs=config['inputs'];outputs=config['outputs'];stage=Path(config['stage']).resolve()
    if not 1<=len(inputs)<=100 or not stage.is_dir():raise ValueError('Invalid toolbox job.')
    expected_count=1 if key=='images_pdf' else len(inputs)
    if len(outputs)!=expected_count:raise ValueError('Invalid output plan.')
    blocked={str(Path(p).resolve()).casefold() for p in inputs+config.get('original_paths',[])}
    if options.get('other'):blocked.add(str(Path(options['other']).resolve()).casefold())
    workflow=config.get('workflow',[])
    if len(workflow)>30:raise ValueError('A workflow supports at most 30 steps.')
    for step in workflow:
        item=BY_KEY.get(step.get('tool'))
        if not item or not item.workflow:raise ValueError('This tool cannot be used in a PDF workflow.')
        options_for(item,step.get('options',{}))
    completed=[];failures=0
    for at,output in enumerate(outputs):
        # Own a unique directory, even when a caller supplies an input directory
        # as staging. Never overwrite or clean up a pre-existing staging file.
        workspace=tempfile.TemporaryDirectory(prefix='.job-',dir=stage)
        doc=None;temporary=Path(workspace.name)/('result.'+(tool.output if not workflow else 'pdf'))
        destination=Path(output['path']).resolve()
        try:
            if str(destination).casefold() in blocked:raise ValueError('Choose an output different from every input PDF.')
            emit(dict(kind='progress',current=at+1,total=len(outputs),message='Processing file'))
            progress=lambda n,total:emit(dict(kind='progress',current=n,total=total,message='Processing pages'))
            if key=='images_pdf':
                doc=images_to_pdf(inputs,options,progress);encrypted=False;password=''
            else:
                password=config.get('password','');doc,(encrypted,readonly,copy_allowed)=open_pdf(inputs[at],password)
                if config.get('current_document'):encrypted=bool(config.get('original_encrypted'))
                if config.get('redaction_applied'):sanitize(doc);doc.set_toc([])
                if (key not in EXTRACT or workflow) and readonly:raise ValueError('Unlock editing with the owner password before transforming this PDF.')
                if key in EXTRACT and not copy_allowed:raise ValueError('Copying and extracting content is restricted in this PDF.')
                if encrypted and key in EXTRACT and not workflow and not config.get('allow_plaintext'):raise ValueError('Confirm the unencrypted export of a protected PDF.')
                pages=page_range(config['pages'],len(doc)) if config.get('pages') and tool.pages else list(range(len(doc)))
                if workflow:
                    for step in workflow:
                        selected=page_range(step['pages'],len(doc)) if step.get('pages') and BY_KEY[step['tool']].pages else list(range(len(doc)))
                        transform(doc,step['tool'],step.get('options',{}),selected,config.get('other_password',''),progress)
                elif key in EXTRACT:extract(doc,key,options,pages,temporary,config.get('other_password',''),progress,encrypted)
                else:transform(doc,key,options,pages,config.get('other_password',''),progress)
            if key not in EXTRACT or workflow:
                atomic_pdf_write(doc,str(temporary),keep_encryption=encrypted,password=password,clean_content=bool(config.get('clean_content')))
                with f.open(temporary) as verified:
                    if not verified.authenticate(password if encrypted else ''):raise ValueError('Output verification failed.')
                    validate_document(verified)
            expected=output.get('expected')
            if expected is not None:
                if not destination.exists() or tuple(expected)!=file_version(destination):raise ValueError('The output file changed while this job was running.')
            elif destination.exists():raise ValueError('The output already exists. Choose a different name.')
            os.replace(temporary,destination);completed.append(str(destination))
            emit(dict(kind='result',path=str(destination),bytes=destination.stat().st_size))
        except Exception as exc:
            failures+=1
            message=str(exc) if isinstance(exc,ValueError) and str(exc) in SAFE_ERRORS else 'This file could not be processed. Check its password, permissions, options and available disk space.'
            emit(dict(kind='error',file=at+1,message=message))
        finally:
            if doc is not None:doc.close()
            workspace.cleanup()
    emit(dict(kind='done',outputs=completed,failures=failures))

SAFE_ERRORS={
 'Keep at least one page in the document.',
 'Unlock editing with the owner password before transforming this PDF.',
 'Copying and extracting content is restricted in this PDF.',
 'Confirm the unencrypted export of a protected PDF.',
 'Apply or undo pending redactions before exporting tools results.',
 'Choose an output different from every input PDF.',
 'The output already exists. Choose a different name.',
 'The output file changed while this job was running.',
 'The joined page exceeds 20,000 PDF points. Join fewer pages.',
 'Crop margins leave less than 18 points of page content.',
 'Use a one-page overlay or one with the same number of pages.',
 'The text does not fit. Resize the text box or reduce the font size.',
 'Enter bookmarks or choose Clear all bookmarks.',
 'Bookmark levels must increase one at a time from 1.',
 'Use level | page | title for each bookmark.',
 'Invalid insertion page or page count.',
 'Text export exceeds the supported size. Export a smaller page range.',
}
