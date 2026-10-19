import io
import json
import time
from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

from paperlight.core import PdfSession, page_range, insert_ocr_words, atomic_pdf_write
from paperlight.worker import index_document, search_words


@pytest.fixture
def source(tmp_path):
    path=tmp_path/'source.pdf'
    with fitz.open() as doc:
        for n in range(3):
            page=doc.new_page(width=595,height=842)
            page.insert_text((55,75),f'Paperlight test page {n+1}',fontsize=22)
            page.insert_text((55,120),'Invoice date 2026-10-16. '+('Secret account ALPHA-923.' if n==0 else 'Public account.'),fontsize=12)
        field=fitz.Widget()
        field.field_name='customer'
        field.field_type=fitz.PDF_WIDGET_TYPE_TEXT
        field.rect=fitz.Rect(55,180,280,210)
        field.field_value='Original customer'
        doc[0].add_widget(field)
        box=fitz.Widget()
        box.field_name='approved'
        box.field_type=fitz.PDF_WIDGET_TYPE_CHECKBOX
        box.rect=fitz.Rect(55,230,75,250)
        doc[0].add_widget(box)
        doc.save(path)
    return path


def test_page_operations_undo_forms(source,tmp_path):
    original=source.read_bytes()
    session=PdfSession(str(source))
    session.rotate(0)
    assert session.doc[0].rotation==90
    session.undo()
    assert session.doc[0].rotation==0
    session.redo()
    assert session.doc[0].rotation==90
    session.reorder([2,0,1])
    assert 'page 3' in session.doc[0].get_text()
    session.undo()
    assert 'page 1' in session.doc[0].get_text()
    session.delete([2])
    assert len(session.doc)==2
    session.merge(str(source),1)
    assert len(session.doc)==5
    output=tmp_path/'pages.pdf'
    session.split([0,2],str(output))
    with fitz.open(output) as doc:
        assert len(doc)==2
        assert doc[0].rotation==90
        assert len(list(doc[0].widgets()))==2
    assert source.read_bytes()==original


def test_edit_form_ink_and_text_save(source,tmp_path):
    session=PdfSession(str(source))
    page=session.doc[0]
    field=next(w for w in page.widgets() if w.field_name=='customer')
    session.fill(0,field.xref,'Updated customer')
    session.ink(0,[(60,300),(90,330),(160,315)],width=3)
    session.text(0,fitz.Rect(55,350,400,410),'Added text and 中文',14)
    session.text(0,fitz.Rect(55,102,205,127),'Corrected date',11,replace=True)
    destination=tmp_path/'edited.pdf'
    session.save(str(destination))
    reader=PdfReader(destination)
    fields=reader.get_fields()
    assert fields['customer']['/V']=='Updated customer'
    with fitz.open(destination) as doc:
        assert 'Added text' in doc[0].get_text()
        assert '中文' in doc[0].get_text()
        assert 'Corrected date' in doc[0].get_text()
        assert len(list(doc[0].annots()))==1
        widget=next(w for w in doc[0].widgets() if w.field_name=='customer')
        assert widget.field_value=='Updated customer'
        assert '/AP' in doc.xref_object(widget.xref)


def test_redaction_removes_text_images_and_fields(source,tmp_path):
    session=PdfSession(str(source))
    image=Image.new('RGB',(300,90),'white')
    draw=ImageDraw.Draw(image)
    draw.rectangle((10,10,270,75),fill='red')
    image_path=tmp_path/'signature.png'
    image.save(image_path)
    session.image(0,fitz.Rect(55,300,355,390),str(image_path))
    session.mark_redaction(0,fitz.Rect(50,100,580,130))
    session.mark_redaction(0,fitz.Rect(50,175,290,215))
    session.mark_redaction(0,fitz.Rect(50,295,360,395))
    with pytest.raises(ValueError,match='pending'):
        session.save(str(tmp_path/'pending.pdf'))
    session.apply_redactions()
    destination=tmp_path/'redacted.pdf'
    session.save(str(destination))
    with fitz.open(destination) as doc:
        assert 'ALPHA-923' not in doc[0].get_text()
        assert 'Original customer' not in doc[0].get_text()
        assert all(w.field_name!='customer' for w in doc[0].widgets() or [])
        pix=doc[0].get_pixmap()
        assert pix.pixel(100,330)==(0,0,0)
        assert not doc[0].get_images()
        # Unused streams are actually discarded by the export, not just hidden.
        all_streams=b''.join(doc.xref_stream(x) or b'' for x in range(1,doc.xref_length()))
        assert b'ALPHA-923' not in all_streams
    assert 'ALPHA-923' in fitz.open(source)[0].get_text()


def test_overflow_is_atomic_and_source_protected(source,tmp_path):
    session=PdfSession(str(source))
    before=session.doc[0].get_text()
    with pytest.raises(ValueError,match='does not fit'):
        session.text(0,fitz.Rect(55,55,65,65),'This will never fit',48,replace=True)
    assert session.doc[0].get_text()==before
    with pytest.raises(ValueError,match='preserve'):
        session.save(str(source))
    with pytest.raises(ValueError):
        session.delete([0,1,2])


def test_ranges_and_phrase_search():
    assert page_range('1-3, 5, 2',5)==[0,1,2,4]
    for value in ('0','6','3-1','', '1,,2'):
        with pytest.raises(ValueError):
            page_range(value,5)
    words=[dict(text=t,rect=[i*20,0,i*20+18,15]) for i,t in enumerate(['Hello','WORLD','中','文'])]
    assert len(search_words(words,'hello world'))==1
    assert len(search_words(words,'中文'))==1


def create_scan(path,language='mixed'):
    image=Image.new('RGB',(1240,1754),'white')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',44)
    draw.text((100,180),'SEARCHABLE SCANNED INVOICE',font=font,fill='black')
    draw.text((100,260),'Account number OCEAN 4826',font=font,fill='black')
    chinese=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',48)
    draw.text((100,380),'中文文件 测试发票',font=chinese,fill='black')
    draw.text((100,470),'中文文件 測試發票',font=chinese,fill='black')
    buf=io.BytesIO()
    image.save(buf,format='PNG')
    with fitz.open() as doc:
        page=doc.new_page(width=620,height=877)
        page.insert_image(page.rect,stream=buf.getvalue())
        if language=='mixed':
            page.insert_text((50,45),'Native header',fontsize=18)
        doc.save(path)


def test_ocr_cache_and_searchable_export(tmp_path,capsys):
    path=tmp_path/'scan.pdf'
    create_scan(path)
    cache=tmp_path/'cache'
    index_document(str(path),str(cache))
    rows=[json.loads(line) for line in capsys.readouterr().out.splitlines()]
    result=next(row for row in rows if row['kind']=='page' and row.get('complete'))
    text=' '.join(w['text'] for w in result['words'])
    assert 'OCEAN' in text
    assert search_words(result['words'],'中文文件')
    assert 'Native' in text
    index_document(str(path),str(cache))
    second=[json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(row.get('cached') and row.get('complete') for row in second)
    assert not any(row['kind']=='progress' for row in second)
    with fitz.open(path) as doc:
        insert_ocr_words(doc[0],result['words'])
        output=tmp_path/'searchable.pdf'
        atomic_pdf_write(doc,str(output))
    with fitz.open(output) as doc:
        assert 'OCEAN' in doc[0].get_text()
        assert doc[0].search_for('中文')
