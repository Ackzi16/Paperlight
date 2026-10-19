import pymupdf as fitz
from paperlight.selection import PageText


def test_native_multiline_selection_and_word_boundaries():
    with fitz.open() as doc:
        p=doc.new_page()
        p.insert_text((50,70),'Hello PDF world',fontsize=14)
        p.insert_text((50,95),'Second line',fontsize=14)
        model=PageText.from_page(p)
        assert model.text(0,len(model.units))=='Hello PDF world\nSecond line'
        assert model.text(*model.word_range(7))=='PDF'
        assert model.text(0,5)=='Hello'
        assert model.text(5,0)=='Hello'
        first=model.units[0]
        r=fitz.Rect(first.rect)
        assert model.caret((r.x0+.1,(r.y0+r.y1)/2))==0
        assert model.caret((r.x1-.1,(r.y0+r.y1)/2))==1
        assert len(model.rectangles(0,len(model.units)))==2


def test_ocr_word_selection_and_chinese_spacing():
    with fitz.open() as doc:
        p=doc.new_page()
        words=[dict(source='ocr',text=t,rect=[50+i*40,50,85+i*40,70],block=0,line=0)
               for i,t in enumerate(['Invoice','OCEAN','4826'])]
        words += [dict(source='ocr',text=t,rect=[50+i*30,95,75+i*30,120],block=1,line=0)
                  for i,t in enumerate(['中文','文件'])]
        model=PageText.from_page(p,words)
        assert model.text(0,5)=='Invoice OCEAN 4826\n中文文件'
        assert model.text(*model.word_range(1))=='OCEAN'
        assert model.text(2,1)=='OCEAN'
        assert model.caret((91,60))==1
        assert model.caret((122,60))==2


def test_empty_page_selection():
    with fitz.open() as doc:
        model=PageText.from_page(doc.new_page())
        assert model.caret((50,50))==0
        assert model.text(0,100)==''
        assert model.word_range(0)==(0,0)
