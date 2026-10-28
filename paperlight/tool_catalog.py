"""Offline toolbox definitions shared by the UI and the worker."""
from dataclasses import dataclass,field

@dataclass(frozen=True)
class Option:
    key:str
    label:str
    kind:str='text'
    default:object=''
    minimum:float=0
    maximum:float=100
    choices:tuple=()

@dataclass(frozen=True)
class Tool:
    key:str
    title:str
    group:str
    description:str
    output:str='pdf'
    options:tuple=()
    pages:bool=False
    workflow:bool=True

def number(key,label,default,minimum,maximum):return Option(key,label,'number',default,minimum,maximum)
def choice(key,label,default,choices):return Option(key,label,'choice',default,choices=tuple(choices))
def check(key,label,default=False):return Option(key,label,'check',default)

DPI=number('dpi','Resolution (DPI)',150,72,300)
QUALITY=number('quality','JPEG quality',80,30,100)
PAPER=choice('paper','Paper size','A4',('A4','Letter','A3'))
POSITION=choice('position','Position','Bottom center',('Top left','Top center','Top right','Center','Bottom left','Bottom center','Bottom right'))

TOOLS=[
 Tool('compress','Compress PDF','Convert','Optimize streams and shared objects without rasterizing text. Optional image recompression reduces scan detail.',options=(check('images','Recompress images'),DPI,QUALITY)),
 Tool('pdf_images','PDF to images','Convert','Export selected pages to a PNG or JPEG ZIP. This is a plain image export, not a searchable PDF.','zip',(DPI,choice('format','Image format','PNG',('PNG','JPEG')),QUALITY),True,False),
 Tool('images_pdf','Images to PDF','Convert','Combine selected PNG, JPEG, TIFF or WebP images into one PDF. Includes all TIFF frames.','pdf',(PAPER,),False,False),
 Tool('text','Extract text','Convert','Export native text and existing OCR to UTF-8 text. Image-only scans need Recognize text first.','txt',(),True,False),
 Tool('tables','Extract tables to CSV','Convert','Detect ruled or aligned tables in native text and export CSV files in a ZIP. Scanned tables need OCR and may require manual cleanup.','zip',(),True,False),
 Tool('extract_images','Extract embedded images','Convert','Export embedded image objects to a ZIP. These are source images, not full page screenshots.','zip',(),True,False),
 Tool('compare','Compare PDF text','Review','Create a plain-text difference report for native text and existing OCR. This does not compare visual layout.','txt',(Option('other','Other PDF','file'),),True,False),
 Tool('info','Document information','Review','Export metadata, page sizes, fonts, permissions, attachment names and form/annotation counts. Signature trust is not validated.','json',(),False,False),
 Tool('metadata','Change metadata','Review','Change the nonempty fields below. Other fields are retained; use Remove metadata to clear them.',options=tuple(Option(k,v) for k,v in (('title','Title'),('author','Author'),('subject','Subject'),('keywords','Keywords')))),
 Tool('bookmarks','Edit bookmarks','Review','One bookmark per line: level | page | title. Levels start at 1. Page numbers start at 1.',options=(Option('bookmarks','Bookmarks','multiline'),check('clear','Clear all bookmarks'))),
 Tool('watermark','Text watermark','Stamp','Add searchable text to selected pages. This is a visual watermark, not edit protection.',options=(Option('text','Watermark text',default='DRAFT'),number('size','Font size',42,6,144),number('opacity','Opacity (%)',25,5,100),choice('angle','Angle',45,(-45,0,45)),choice('position','Position','Center',POSITION.choices)),pages=True),
 Tool('numbers','Page numbers','Stamp','Number selected pages using {page}, {total} and {number}. PDF page numbers and running numbers can differ.',options=(Option('text','Format',default='{page} / {total}'),number('start','Start number',1,0,1000000),number('size','Font size',11,6,48),POSITION),pages=True),
 Tool('blank','Insert blank page','Pages','Insert blank pages before a chosen page. Use page count + 1 to append.',options=(number('before','Before page',1,1,10001),number('count','Number of blank pages',1,1,100),PAPER)),
 Tool('duplicate','Duplicate pages','Pages','Insert copies of selected pages after the last selected page, preserving copied form fields.',pages=True),
 Tool('reverse','Reverse page order','Pages','Reverse all pages in the exported copy.'),
 Tool('rotate','Rotate pages','Pages','Rotate selected pages clockwise, leaving other pages unchanged.',options=(choice('degrees','Degrees clockwise',90,(90,180,270)),),pages=True),
 Tool('keep_pages','Keep selected pages','Pages','Export only the selected pages, in the entered order.',pages=True),
 Tool('remove_pages','Remove selected pages','Pages','Remove the selected pages from the exported copy. At least one page must remain.',pages=True),
 Tool('crop','Crop page margins','Pages','Trim visible margins in PDF points, before page rotation. Cropping hides content; it does not redact or remove hidden content.',options=tuple(number(k,v,18,0,2000) for k,v in (('left','Left margin'),('top','Top margin'),('right','Right margin'),('bottom','Bottom margin'))),pages=True),
 Tool('resize','Resize pages','Layout','Fit content to a new paper size. Layout exports flatten forms and annotations but retain native page text.',options=(PAPER,number('margin','Margin (pt)',18,0,144))),
 Tool('nup','Multiple pages per sheet','Layout','Place several pages on each sheet. Forms and annotations become permanent page content.',options=(PAPER,choice('per_sheet','Pages per sheet',4,(2,4,6,9)),number('margin','Margin (pt)',18,0,100))),
 Tool('booklet','Booklet layout','Layout','Create two-up landscape sheets in booklet order, padding with blank pages. Print duplex with short-edge flipping. Forms and annotations are flattened.',options=(PAPER,number('margin','Margin (pt)',12,0,100))),
 Tool('tiles','Split pages into tiles','Layout','Split each page into a grid of separate pages. Forms and annotations are flattened.',options=(number('columns','Columns',2,1,4),number('rows','Rows',1,1,4))),
 Tool('long_page','Join into one long page','Layout','Stack pages vertically, retaining native text. Limited to 20,000 PDF points in length. Forms and annotations are flattened.'),
 Tool('overlay','Overlay another PDF','Layout','Overlay corresponding pages from another PDF. A one-page overlay repeats on every page. Forms and annotations are flattened.',options=(Option('other','Overlay PDF','file'),)),
 Tool('flatten','Flatten forms and annotations','Cleanup','Convert form fields and annotations to permanent visible page content. This is not encryption or redaction.'),
 Tool('annotations','Remove annotations','Cleanup','Remove comments, highlights, ink and other annotations from selected pages. Form fields are retained.',pages=True),
 Tool('images','Remove images','Cleanup','Remove image appearances throughout the document, including scan backgrounds. Invisible OCR may remain. This is not a redaction tool.'),
 Tool('blank_pages','Remove blank pages','Cleanup','Conservatively remove white pages without text, links, fields or annotations. Retains one page if all are blank.'),
 Tool('clear_metadata','Remove metadata','Cleanup','Remove standard and XML metadata. Bookmarks and visible page content are retained.'),
 Tool('sanitize','Sanitize PDF','Cleanup','Remove scripts, external actions, links, attachments, metadata, thumbnails and annotation responses. Visible page content and filled field values are retained. Not a security certification.'),
 Tool('repair','Repair PDF','Cleanup','Rebuild a PDF that the local parser can still open. This can repair cross-reference damage, but cannot recover every damaged file.'),
 Tool('unlock_forms','Unlock read-only form fields','Cleanup','Clear read-only field flags after PDF editing permission has been granted. This does not bypass an owner password.'),
 Tool('grayscale','Grayscale PDF','Scans','Render pages to grayscale images while retaining existing text as an invisible search layer. Forms and annotations are flattened.',options=(DPI,QUALITY)),
 Tool('invert','Invert PDF colors','Scans','Render pages with inverted colors while retaining existing text as an invisible search layer. Forms and annotations are flattened.',options=(DPI,QUALITY)),
 Tool('contrast','Adjust scan contrast','Scans','Render pages with adjusted contrast, retaining existing text as an invisible search layer. Forms and annotations are flattened.',options=(DPI,QUALITY,number('contrast','Contrast (%)',130,50,250))),
]
BY_KEY={tool.key:tool for tool in TOOLS}

def options_for(tool,values):
    if not isinstance(values,dict):raise ValueError('Invalid tool options.')
    result={}
    for option in tool.options:
        value=values.get(option.key,option.default)
        if option.kind=='number':
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not option.minimum<=value<=option.maximum:raise ValueError('A numeric option is outside its allowed range.')
        elif option.kind=='choice':
            if value not in option.choices:raise ValueError('Invalid tool choice.')
        elif option.kind=='check':
            if not isinstance(value,bool):raise ValueError('Invalid checkbox option.')
        elif not isinstance(value,str) or len(value)>(100000 if option.kind=='multiline' else 4096) or '\0' in value:raise ValueError('Invalid text option.')
        result[option.key]=value
    return result
