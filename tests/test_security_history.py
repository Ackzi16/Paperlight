import io
from pathlib import Path
import pymupdf as fitz
from PIL import Image, ImageDraw

from paperlight.core import PdfSession
from .test_pdf import source


def test_redaction_removes_hidden_ocr_and_partial_image_pixels(source,tmp_path):
    scan=tmp_path/'scan.pdf'
    image=Image.new('RGB',(400,300),'white')
    draw=ImageDraw.Draw(image)
    draw.rectangle((10,10,150,90),fill='red')
    draw.rectangle((220,140,380,290),fill='blue')
    stream=io.BytesIO()
    image.save(stream,format='PNG')
    with fitz.open() as doc:
        p=doc.new_page(width=400,height=300)
        p.insert_image(p.rect,stream=stream.getvalue())
        p.insert_text((20,60),'HIDDEN-PRIVATE-827',fontsize=12,render_mode=3)
        p.insert_text((230,180),'HIDDEN-PUBLIC-124',fontsize=12,render_mode=3)
        doc.save(scan)
    session=PdfSession(str(scan))
    session.mark_redaction(0,fitz.Rect(0,0,210,110))
    session.apply_redactions()
    output=tmp_path/'sanitized.pdf'
    session.save(str(output))
    with fitz.open(output) as doc:
        assert 'HIDDEN-PRIVATE' not in doc[0].get_text()
        assert 'HIDDEN-PUBLIC' in doc[0].get_text()
        pix=doc[0].get_pixmap()
        assert pix.pixel(50,50)==(0,0,0)
        assert pix.pixel(260,200)==(0,0,255)
        # Inspect the underlying retained image, independently of the black overlay.
        images=doc[0].get_images()
        assert len(images)==1
        raw=fitz.Pixmap(doc,images[0][0])
        assert raw.pixel(50,50)!=(255,0,0)
        assert raw.pixel(260,200)==(0,0,255)
        streams=b''.join(doc.xref_stream(x) or b'' for x in range(1,doc.xref_length()))
        assert b'HIDDEN-PRIVATE' not in streams
    session.close()


def test_undo_redo_edit_branch_and_cleanup(source,tmp_path):
    session=PdfSession(str(source))
    temporary=Path(session._temporary.name)
    session.text(0,fitz.Rect(55,300,450,350),'First correction',14)
    session.save_in_place()
    assert not session.dirty
    session.undo()
    assert session.dirty
    assert 'First correction' not in session.doc[0].get_text()
    session.redo()
    assert not session.dirty
    assert 'First correction' in session.doc[0].get_text()
    session.undo()
    session.text(0,fitz.Rect(55,300,450,350),'Different correction',14)
    assert session.dirty
    assert not session.can_do()['redo']
    session.close()
    assert not temporary.exists()
