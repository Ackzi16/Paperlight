"""Generate an original example document and a 300-page mixed performance fixture."""
import io
from pathlib import Path
import sys

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def make_demo():
    path=ROOT/'assets'/'Welcome to Paperlight.pdf'
    with fitz.open() as doc:
        p=doc.new_page(width=595,height=842)
        p.draw_rect(fitz.Rect(0,0,595,12),fill=(.14,.37,.61),color=None)
        p.insert_text((48,72),'P A P E R L I G H T',fontsize=13,color=(.14,.37,.61))
        p.insert_text((48,128),'Make room for',fontsize=36,color=(.13,.19,.26))
        p.insert_text((48,171),'your paperwork.',fontsize=36,color=(.13,.19,.26))
        p.insert_text((48,211),'An offline PDF workspace for Windows',fontsize=14,color=(.4,.47,.54))
        p.draw_line((48,240),(547,240),color=(.85,.88,.91))
        sections=[('01','Read and find','Use the sidebar to move between pages. Ctrl+F searches text.\nFor scans, choose Recognize text to run English and Chinese OCR.'),
                  ('02','Leave your mark','Draw a signature with your mouse, place a signature image,\nor drag a text box wherever you need one.'),
                  ('03','Put pages in order','Drag thumbnails to rearrange pages. The Pages menu includes\nrotation, deletion, extraction and merging.'),
                  ('04','Save a separate copy','Your original stays unchanged. Apply marked redactions before\nsaving a copy that permanently removes the selected content.')]
        for i,(number,title,body) in enumerate(sections):
            y=289+i*96
            p.insert_text((48,y),number,fontsize=13,color=(.14,.37,.61))
            p.insert_text((88,y),title,fontsize=16,color=(.13,.19,.26))
            p.insert_text((88,y+25),body,fontsize=10.5,lineheight=1.55,color=(.36,.43,.49))
        p.insert_text((48,741),'Try filling this field:',fontsize=11,color=(.36,.43,.49))
        widget=fitz.Widget()
        widget.field_name='your_name'
        widget.field_type=fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect=fitz.Rect(175,723,430,750)
        widget.field_value='Your name'
        widget.border_width=1
        widget.border_color=(.72,.78,.83)
        widget.field_fontsize=12
        p.add_widget(widget)
        p.insert_text((48,804),'LOCAL FILES  /  OFFLINE OCR  /  ORIGINALS PRESERVED',fontsize=8,color=(.49,.55,.61))
        # An actual scanned page for trying OCR, rather than a hidden text demo.
        image=Image.new('RGB',(1240,1754),'white')
        draw=ImageDraw.Draw(image)
        english=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',43)
        chinese=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',48)
        draw.text((100,140),'A scanned document',font=english,fill='#234e7c')
        draw.text((100,250),'Search for: OCEAN 4826',font=english,fill='black')
        draw.text((100,390),'中文文件 测试发票',font=chinese,fill='black')
        draw.text((100,490),'中文文件 測試發票',font=chinese,fill='black')
        draw.text((100,650),'Use Recognize text, then Ctrl+F.',font=english,fill='black')
        buf=io.BytesIO()
        image.save(buf,format='PNG')
        p=doc.new_page(width=595,height=842)
        p.insert_image(p.rect,stream=buf.getvalue())
        doc.save(path,deflate=True)
    return path


def make_large(demo):
    folder=ROOT/'tmp'/'verification'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/'300-page-mixed.pdf'
    with fitz.open(demo) as sample,fitz.open() as output:
        scan=sample[1].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
        template=Image.frombytes('RGB',(scan.width,scan.height),scan.samples)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',28)
        for n in range(300):
            if n%2==0:
                output.insert_pdf(sample,from_page=0,to_page=0,widgets=False)
            else:
                # Give each scan unique pixels and a light paper texture so this
                # fixture cannot collapse to one deduplicated image stream.
                texture=Image.effect_noise(template.size,18).point(lambda p:235+p//13).convert('RGB')
                image=Image.blend(template,texture,.12)
                draw=ImageDraw.Draw(image)
                draw.text((100,1450),f'Original scanned sheet {n+1:03}',font=font,fill='black')
                buffer=io.BytesIO()
                image.save(buffer,format='JPEG',quality=94)
                page=output.new_page(width=595,height=842)
                page.insert_image(page.rect,stream=buffer.getvalue())
            output[-1].insert_text((48,823),f'Page {n+1} / 300 | unique-token-{n+1:03}',fontsize=8)
        output.save(path,garbage=4,deflate=True)
    return path


if __name__=='__main__':
    demo=make_demo()
    print(demo)
    print(make_large(demo))
