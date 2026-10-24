import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import io
import pymupdf as fitz
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
import pytest
from paperlight.core import PdfSession
from paperlight.objects import discover,edit_graphic,fingerprint
from paperlight.app import Window
from .test_ui import app,wait_for

@pytest.fixture(autouse=True)
def object_fonts(app):
    for name in ('arial.ttf','arialbd.ttf','ariali.ttf','segoeui.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+name)

@pytest.fixture
def objects_pdf(tmp_path):
    path=tmp_path/'objects.pdf'
    image=Image.new('RGB',(80,50),'#4b7dad');data=io.BytesIO();image.save(data,format='PNG')
    with fitz.open() as doc:
        p=doc.new_page(width=595,height=842)
        p.draw_rect((45,50,400,110),color=(.2,.3,.6),fill=(.92,.96,1),width=2)
        p.insert_text((60,80),'Normal ',fontsize=14)
        p.insert_text((108,80),'bold text',fontname='hebo',fontsize=14)
        p.draw_line((50,210),(250,210),color=(.1,.2,.3),width=2)
        p.draw_circle((350,200),35,color=(.8,.2,.2))
        xref=p.insert_image((50,300,130,350),stream=data.getvalue())
        p.insert_image((220,300,300,350),xref=xref)
        p2=doc.new_page(width=595,height=842);p2.insert_image((50,300,130,350),xref=xref)
        doc.set_toc([[1,'Section',1]]);doc.set_metadata({'title':'Object test'})
        doc.save(path)
    return path


def test_discover_and_graphic_instance_edits(objects_pdf,tmp_path):
    session=PdfSession(str(objects_pdf))
    try:
        objects=discover(session.doc[0]);assert any(o.title=='Rectangle' and o.writable for o in objects)
        assert any(o.title=='Ellipse' and o.writable for o in objects)
        images=[o for o in objects if o.kind=='image'];assert len(images)==2
        before=session.doc[0].get_text();page2=session.doc[1].get_pixmap().samples
        first=min(images,key=lambda o:o.rect[0]);new=fitz.Rect(first.rect)+(20,30,20,30)
        session.edit_object(0,first,rect=new)
        rects=[tuple(i['bbox']) for i in session.doc[0].get_image_info()]
        assert tuple(new) in rects and (220.,300.,300.,350.) in rects
        assert session.doc[1].get_pixmap().samples==page2 and session.doc[0].get_text()==before
        session.undo();assert tuple(first.rect) in [tuple(i['bbox']) for i in session.doc[0].get_image_info()]
        session.redo();assert tuple(new) in [tuple(i['bbox']) for i in session.doc[0].get_image_info()]
        rect=next(o for o in discover(session.doc[0]) if o.title=='Rectangle')
        session.edit_object(0,rect,delete=True)
        assert session.doc[0].get_text()==before
        assert len(session.doc[0].get_drawings())==2
        output=tmp_path/'edited.pdf';session.save(output)
        with fitz.open(output) as saved:
            assert len(saved[0].get_drawings())==2 and saved[0].get_text()==before
    finally: session.close()


def test_graphic_scope_stale_and_clipping_fail_closed(objects_pdf):
    session=PdfSession(str(objects_pdf))
    try:
        obj=next(o for o in discover(session.doc[0]) if o.title=='Rectangle')
        session.edit_object(0,obj,stroke=(1,0,0))
        with pytest.raises(ValueError,match='changed'):session.edit_object(0,obj,delete=True)
        from paperlight.objects import set_content
        with session.operation('Clipped test'):
            p=session.doc[0];set_content(p,b'q 0 0 100 100 re W n '+p.read_contents()+b' Q')
        shapes=[o for o in discover(session.doc[0]) if o.kind=='shape']
        assert shapes and all(not o.writable for o in shapes)
    finally: session.close()


def test_edit_pdf_click_mixed_fonts_and_keep_border(app,objects_pdf):
    window=Window();window.error=lambda exc: (_ for _ in ()).throw(RuntimeError(str(exc)))
    window.show();window.open_path(str(objects_pdf));wait_for(lambda:window.job is None)
    try:
        window.choose_tool('edit');wait_for(lambda:bool(window.canvas.page_objects) and not window.canvas.commit_pending)
        assert window.tool_actions['edit'].isChecked()
        obj=next(o for o in window.canvas.page_objects if o.kind=='text')
        before=[(tuple(d['rect']),d['color'],d['fill']) for d in window.session.doc[0].get_drawings()]
        window.choose_object(obj);box=window.inline_text
        assert box.rich and box.editor.toPlainText()=='Normal bold text'
        # Append in the final bold run; retain the initial regular run.
        cursor=box.editor.textCursor();cursor.movePosition(cursor.MoveOperation.End);box.editor.setTextCursor(cursor)
        box.rect+= (0,0,20,0);box.update_layout()
        box.editor.insertPlainText('!')
        assert window.commit_inline_text()
        page=window.session.doc[0]
        assert 'Normal bold text!' in page.get_text().replace('\n','')
        styles=[(s['text'],s['font']) for b in page.get_text('dict')['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans']]
        assert any('Normal' in value and 'Bold' not in font for value,font in styles)
        assert any('bold text!' in value and 'Bold' in font for value,font in styles)
        after=[(tuple(d['rect']),d['color'],d['fill']) for d in page.get_drawings()]
        assert after==before
        window.undo();assert '!' not in window.session.doc[0].get_text()
        window.redo();assert '!' in window.session.doc[0].get_text()
        assert window.save_current()
        with fitz.open(objects_pdf) as saved:
            assert '!' in saved[0].get_text()
            assert saved.get_toc()==[[1,'Section',1]] and saved.metadata['title']=='Object test'
    finally:
        window.cancel_inline_text();window.session.saved_position=window.session.position;window.close()


def test_edit_pdf_noop_and_handle_drag(app,objects_pdf):
    window=Window();window.error=lambda exc: (_ for _ in ()).throw(RuntimeError(str(exc)))
    window.show();window.open_path(str(objects_pdf));wait_for(lambda:window.job is None)
    try:
        window.choose_tool('edit');wait_for(lambda:bool(window.canvas.page_objects) and not window.canvas.commit_pending);obj=next(o for o in window.canvas.page_objects if o.kind=='text')
        window.choose_object(obj);QTest.qWait(20)
        assert window.inline_text.editor.document().begin().layout().lineCount()==1
        assert window.commit_inline_text();assert not window.session.dirty
        obj=next(o for o in window.canvas.page_objects if o.title=='Ellipse')
        p=fitz.Rect(obj.rect).tl+fitz.Point(20,20)
        start=window.canvas.mapFromScene(p.x*window.canvas.factor,p.y*window.canvas.factor)
        end=start+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(25,20)
        QTest.mousePress(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(window.canvas.viewport(),end)
        QTest.mouseRelease(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=end)
        assert window.session.dirty
        wait_for(lambda:not window.canvas.commit_pending)
        ellipse=next(o for o in window.canvas.page_objects if o.title=='Ellipse')
        assert ellipse.rect[0]>obj.rect[0]+10
    finally:
        window.cancel_inline_text();window.session.saved_position=window.session.position;window.close()


def test_native_text_reflow_and_background_preserved(app,objects_pdf):
    window=Window();window.error=lambda exc: (_ for _ in ()).throw(RuntimeError(str(exc)))
    window.show();window.open_path(str(objects_pdf));wait_for(lambda:window.job is None)
    try:
        window.choose_tool('edit');wait_for(lambda:bool(window.canvas.page_objects) and not window.canvas.commit_pending);obj=next(o for o in window.canvas.page_objects if o.kind=='text')
        page=window.session.doc[0];pixel_before=page.get_pixmap().pixel(70,83)
        window.choose_object(obj);box=window.inline_text
        box.rect=fitz.Rect(obj.rect)+(0,0,120,80);box.update_layout()
        box.editor.setPlainText('A longer paragraph that wraps inside its own text box. English and 中文文字.')
        assert window.commit_inline_text()
        page=window.session.doc[0]
        assert page.search_for('中文文字')
        assert page.get_pixmap().pixel(70,83)==pixel_before
        lines=[line for block in page.get_text('dict')['blocks'] if block['type']==0 for line in block['lines']]
        assert len(lines)>=2
    finally:
        window.cancel_inline_text();window.session.saved_position=window.session.position;window.close()


def test_edit_mode_ocr_only_current_scanned_page(app,tmp_path):
    from .test_pdf import create_scan
    path=tmp_path/'scanned.pdf';create_scan(path)
    with fitz.open(path) as original:
        original.fullcopy_page(0);original.save(tmp_path/'two-scans.pdf')
    window=Window();window.error=lambda exc: (_ for _ in ()).throw(RuntimeError(str(exc)))
    window.show();window.open_path(str(tmp_path/'two-scans.pdf'));wait_for(lambda:window.job is None)
    try:
        window.choose_tool('edit');wait_for(lambda:bool(window.canvas.page_objects) and not window.canvas.commit_pending)
        wait_for(lambda:window.job is None and bool(window.session.doc[0].search_for('OCEAN')),30000)
        assert not window.session.doc[1].search_for('OCEAN')
        wait_for(lambda:not window.canvas.commit_pending)
        choices=[o for o in window.canvas.page_objects if o.kind=='ocr' and 'OCEAN' in o.text]
        assert choices,repr([(o.kind,o.text) for o in window.canvas.page_objects])
        ocr=choices[0]
        window.choose_object(ocr);box=window.inline_text
        box.rect+= (0,0,120,40);box.update_layout()
        box.editor.setPlainText('Account number RIVER 4826')
        assert window.commit_inline_text()
        assert window.session.doc[0].search_for('RIVER')
        assert not window.session.doc[0].search_for('OCEAN')
    finally:
        window.cancel_inline_text();window.session.saved_position=window.session.position;window.close()


def test_object_detection_does_not_modify_and_scope_uses_outer_transform(objects_pdf):
    from paperlight.objects import set_content
    session=PdfSession(str(objects_pdf))
    try:
        before=session.position;data=session.doc[0].read_contents()
        discover(session.doc[0]);assert session.position==before and session.doc[0].read_contents()==data
        with session.operation('Outer transform'):
            page=session.doc[0];set_content(page,b'q .8 0 0 .8 10 20 cm '+page.read_contents()+b' Q')
        obj=next(o for o in discover(session.doc[0]) if o.title=='Rectangle' and o.writable)
        target=fitz.Rect(obj.rect)+(30,40,30,40)
        session.edit_object(0,obj,rect=target)
        changed=next(o for o in discover(session.doc[0]) if o.title=='Rectangle' and o.writable)
        assert all(abs(a-b)<.1 for a,b in zip(changed.rect,target))
    finally: session.close()


def test_color_change_preserves_mixed_fonts(app,objects_pdf):
    from dataclasses import replace
    from paperlight.richtext import apply_format
    window=Window();window.error=lambda exc: (_ for _ in ()).throw(RuntimeError(str(exc)))
    window.show();window.open_path(str(objects_pdf));wait_for(lambda:window.job is None)
    try:
        window.choose_tool('edit');wait_for(lambda:bool(window.canvas.page_objects) and not window.canvas.commit_pending);obj=next(o for o in window.canvas.page_objects if o.kind=='text')
        window.choose_object(obj);box=window.inline_text
        assert not window.session.dirty and not window.save_action.isEnabled()
        box.style=replace(box.style,color=(0,1,0));box.format_modified=True
        apply_format(box,'color')
        box.update_layout()
        assert window.commit_inline_text()
        spans=[s for b in window.session.doc[0].get_text('dict')['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans']]
        assert any('Normal' in s['text'] and 'Bold' not in s['font'] for s in spans)
        assert any('bold text' in s['text'] and 'Bold' in s['font'] for s in spans)
        assert all(s['color']==0x00ff00 for s in spans)
    finally:
        window.cancel_inline_text();window.session.saved_position=window.session.position;window.close()


def test_native_shared_form_text_edit_does_not_change_other_instances(app,tmp_path):
    path=tmp_path/'shared-text.pdf'
    with fitz.open() as stamp:
        p=stamp.new_page(width=200,height=100);p.insert_text((20,45),'Shared text',fontsize=14);p.insert_text((20,70),'中文',fontname='china-s',fontsize=14)
        with fitz.open() as doc:
            p=doc.new_page();p.show_pdf_page(fitz.Rect(30,50,230,150),stamp,0);p.show_pdf_page(fitz.Rect(300,50,500,150),stamp,0)
            p=doc.new_page();p.show_pdf_page(fitz.Rect(30,50,230,150),stamp,0);doc.save(path)
    session=PdfSession(str(path))
    try:
        obj=min((o for o in discover(session.doc[0]) if o.kind=='text'),key=lambda o:o.rect[0])
        session.object_text(0,obj,obj.rect,runs=[])
        assert session.doc[0].get_text().count('Shared text')==1
        assert session.doc[1].get_text().count('Shared text')==1
        assert session.doc[1].get_text().count('中文')==1
        session.undo();assert session.doc[0].get_text().count('Shared text')==2
    finally:session.close()
