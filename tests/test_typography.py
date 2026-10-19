from dataclasses import replace
from pathlib import Path
import pymupdf as fitz
import pytest

from paperlight.core import PdfSession
from paperlight.typography import FontCatalog, normalized


@pytest.fixture
def formatted_pdf(tmp_path):
    path=tmp_path/'formatted.pdf'
    with fitz.open() as doc:
        page=doc.new_page()
        page.insert_text((55,70),'A bold heading',fontname='hebo',fontsize=25,color=(.15,.2,.3))
        for n in range(8):
            page.insert_text((55,120+n*18),'Most of the document uses this proportional serif body font.',
                             fontname='tiro',fontsize=11,color=(.2,.2,.2))
        page.insert_text((55,330),'Italic date 2026-10-16',fontname='tiit',fontsize=13,color=(.65,.1,.15))
        page.insert_text((55,380),'Monospaced code',fontname='cour',fontsize=10)
        page=doc.new_page()
        page.insert_text((55,70),'Another short bold heading',fontname='hebo',fontsize=25)
        doc.save(path)
    return path


def test_document_majority_and_selected_format(formatted_pdf,tmp_path):
    session=PdfSession(str(formatted_pdf))
    catalog=session.font_catalog()
    assert catalog.choices[0].name=='Times-Roman'
    assert {c.name for c in catalog.choices}=={'Times-Roman','Times-Italic','Helvetica-Bold','Courier'}
    default=catalog.style(0)
    assert default.choice.name=='Times-Roman' and default.size==11
    rect=fitz.Rect(53,310,350,339)
    style=catalog.style(0,rect)
    assert style.choice.name=='Times-Italic'
    assert style.size==13
    assert style.anchor==pytest.approx((55,330))
    assert style.color==pytest.approx((.65,.1,.15),abs=.005)
    session.text(0,rect,'Italic date 2026-11-20',replace=True)
    output=tmp_path/'corrected.pdf'
    session.save(str(output))
    with fitz.open(output) as doc:
        spans=[s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
        span=next(s for s in spans if '2026-11-20' in s['text'])
        assert normalized(span['font'])=='timesitalic'
        assert span['size']==pytest.approx(13)
        assert span['origin']==pytest.approx((55,330),abs=.01)
        assert span['color']==round(style.color[0]*255)<<16 | round(style.color[1]*255)<<8 | round(style.color[2]*255)
        expected=fitz.Font('tiit').text_length(span['text'],fontsize=13)
        assert fitz.Rect(span['bbox']).width==pytest.approx(expected,abs=.3)
        assert '2026-10-16' not in doc[0].get_text()
    session.close()


def test_embedded_face_and_subset_glyph_recovery(tmp_path):
    source=tmp_path/'embedded.pdf'
    full_source=tmp_path/'full-font.pdf'
    with fitz.open() as doc:
        page=doc.new_page()
        page.insert_font(fontname='OriginalArial',fontfile='C:/Windows/Fonts/arial.ttf')
        page.insert_text((50,100),'Arial body 111',fontname='OriginalArial',fontsize=14)
        doc.save(full_source)
        doc.subset_fonts()
        doc.save(source)
    session=PdfSession(str(source))
    catalog=session.font_catalog()
    selected=catalog.style(0,fitz.Rect(48,80,300,110))
    assert 'arial' in normalized(selected.choice.name)
    assert selected.choice.buffer
    _,where,missing=selected.choice.resolve('Arial body 111')
    assert where in ('Embedded PDF font','Installed copy of PDF font')
    # New glyphs absent from a subset can use the same installed font face.
    _,where,missing=selected.choice.resolve('New word 9278')
    assert not missing
    session.text(0,fitz.Rect(48,80,300,110),'New word 9278',replace=True,style=selected)
    assert 'New word 9278' in session.doc[0].get_text().replace('\xa0',' ')
    assert 'arial' in normalized(next(s['font'] for b in session.doc[0].get_text('dict')['blocks']
                                     for l in b.get('lines',[]) for s in l['spans'] if 'New' in s['text']))
    session.undo()
    assert 'Arial body 111' in session.doc[0].get_text().replace('\xa0',' ')
    session.close()
    full=PdfSession(str(full_source))
    style=full.font_catalog().style(0,fitz.Rect(48,80,300,110))
    _,where,missing=style.choice.resolve('Other text 9278')
    assert where=='Embedded PDF font' and not missing
    full.text(0,fitz.Rect(48,80,300,110),'Other text 9278',replace=True,style=style)
    assert 'Other text 9278' in full.doc[0].get_text().replace('\xa0',' ')
    full.close()


def test_font_override_and_line_spacing(formatted_pdf,tmp_path):
    session=PdfSession(str(formatted_pdf))
    catalog=session.font_catalog()
    style=catalog.style(0)
    courier=next(c for c in catalog.choices if c.name=='Courier')
    custom=replace(style,choice=courier,size=12.5,line_height=19,color=(0,.2,.6))
    session.text(1,fitz.Rect(55,150,450,240),'First line\nSecond line',style=custom)
    spans=[s for b in session.doc[1].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']
           if 'line' in s['text']]
    assert all(normalized(s['font'])=='courier' for s in spans)
    assert all(s['size']==pytest.approx(12.5) for s in spans)
    assert spans[1]['origin'][1]-spans[0]['origin'][1]==pytest.approx(19,abs=.02)
    session.close()


def test_hidden_ocr_does_not_choose_visual_font(tmp_path):
    path=tmp_path/'ocr-layer.pdf'
    with fitz.open() as doc:
        p=doc.new_page()
        p.insert_text((50,60),'Visible heading',fontname='helv',fontsize=18)
        for n in range(20):
            p.insert_text((50,100+n*20),'This is invisible OCR text and is not the printed font.',
                          fontname='cour',fontsize=11,render_mode=3)
        doc.save(path)
    session=PdfSession(str(path))
    catalog=session.font_catalog()
    assert [choice.name for choice in catalog.choices]==['Helvetica']
    assert catalog.style(0).size==18
    session.close()
