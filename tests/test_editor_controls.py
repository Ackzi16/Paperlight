import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import base64
import math
import pymupdf as f
import pytest
from PySide6.QtCore import Qt,QPoint,QPointF
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from paperlight.app import Window,Canvas,NumberEdit
from paperlight.objects import discover
from paperlight.geometry import rotation_matrix
from paperlight import edit_worker
from .test_ui import app,wait_for
from .test_objects import objects_pdf,object_fonts


@pytest.mark.parametrize('rotation,factor',[(0,.65),(0,2.7),(90,1.8),(270,2.2)])
def test_transformed_visible_preview_matches_page_coordinates(app,objects_pdf,monkeypatch,rotation,factor):
    from paperlight.core import PdfSession
    session=PdfSession(str(objects_pdf));canvas=Canvas()
    try:
        if rotation:
            with session.operation('Rotate fixture'):session.doc[0].set_rotation(rotation)
        canvas.mode='edit';canvas.show_page(session.doc[0],factor)
        canvas.page_origin=QPointF(37,93);canvas.single_page_image.setPos(canvas.page_origin)
        obj=next(o for o in discover(session.doc[0]) if o.title=='Ellipse' and o.writable)
        canvas.selected_object=obj;canvas.page_objects=[obj]
        rows=[];monkeypatch.setattr(edit_worker,'emit',rows.append)
        edit_worker.process(dict(task='preview',path=str(session._working),password=session._working_password,page=0,scale=factor,object=edit_worker.serial(obj)))
        layers={}
        for row in rows:
            pix=QPixmap();assert pix.loadFromData(base64.b64decode(row['png']),'PNG')
            layers[row['layer']]=dict(pixmap=pix,x=row['x'],y=row['y'],scale=row['scale'])
        canvas.accept_edit_preview(edit_worker.serial(obj),layers)
        matrix=rotation_matrix(obj.quad,31)*f.Matrix(1,0,0,1,42,27)
        canvas.apply_preview_transform(matrix)
        item=canvas.preview_items[0];scale=layers['selected']['scale']
        for point in canvas.object_quad(obj):
            raster=point*session.doc[0].rotation_matrix*f.Matrix(scale,scale)
            actual=item.mapToScene(QPointF(*raster));expected=canvas.page_scene(point*matrix)
            assert math.hypot(actual.x()-expected.x(),actual.y()-expected.y())<.002
        canvas.object_drag=dict(matrix=matrix,path=None);canvas.paint_objects()
        # The selection follows the actual curved outline, not its box.
        assert canvas.outline_items[0].path().elementCount()>8
    finally:canvas.clear_edit_preview();canvas.close();session.close()


def test_all_editing_tools_visible_and_numeric_control_keys(app,objects_pdf):
    window=Window();window.show();window.open_path(str(objects_pdf));wait_for(lambda:window.job is None)
    try:
        assert not hasattr(window,'markup_toggle')
        for action in window.tool_actions.values():
            widget=window.basic_bar.widgetForAction(action)
            assert widget and widget.isVisible()
            assert window.basic_bar.rect().contains(widget.geometry().center())
        field=window.pen_width;field.setFocus();QTest.keyClick(field,Qt.Key.Key_Up)
        assert field.value()==2.5
        QTest.keyClick(field,Qt.Key.Key_Backspace)
    finally:window.close()


def test_text_select_move_resize_and_double_click_edit(app,objects_pdf):
    window=Window();window.show();window.error=lambda exc: (_ for _ in ()).throw(RuntimeError(str(exc)))
    window.open_path(str(objects_pdf));wait_for(lambda:window.job is None)
    try:
        window.choose_tool('edit');c=window.canvas
        wait_for(lambda:bool(c.page_objects) and not c.commit_pending)
        obj=next(o for o in c.page_objects if o.kind=='text')
        before_drawings=[tuple(d['rect']) for d in window.session.doc[0].get_drawings()]
        center=(f.Rect(obj.rect).tl+f.Rect(obj.rect).br)/2
        start=c.mapFromScene(c.page_scene(center));QTest.mouseClick(c.viewport(),Qt.MouseButton.LeftButton,pos=start)
        assert c.selected_object is obj and window.inline_text is None and len(c.controls())==4
        wait_for(lambda:c.preview_identity is not None)
        position=window.session.position;end=start+QPoint(0,round(80*c.factor))
        QTest.mousePress(c.viewport(),Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(c.viewport(),end)
        assert window.inline_text and window.inline_text.rect.y0>obj.rect[1]+70
        assert window.session.position==position
        QTest.mouseRelease(c.viewport(),Qt.MouseButton.LeftButton,pos=end)
        wait_for(lambda:not c.commit_pending and not window.edit_controller.busy)
        assert window.session.position==position+1 and window.inline_text is None
        moved=c.selected_object;assert moved and moved.rect[1]>obj.rect[1]+70
        spans=[s for b in window.session.doc[0].get_text('dict')['blocks'] if b['type']==0 for line in b['lines'] for s in line['spans']]
        assert any('Normal' in s['text'] and 'Bold' not in s['font'] for s in spans)
        assert any('bold text' in s['text'] and 'Bold' in s['font'] for s in spans)
        assert [tuple(d['rect']) for d in window.session.doc[0].get_drawings()]==before_drawings
        corner=next(control for control in c.controls() if control[1]==2)
        start=c.mapFromScene(corner[-1]);end=start+QPoint(-round(65*c.factor),round(65*c.factor))
        QTest.mousePress(c.viewport(),Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(c.viewport(),end)
        assert window.inline_text and window.inline_text.rect.width<f.Rect(moved.rect).width
        QTest.mouseRelease(c.viewport(),Qt.MouseButton.LeftButton,pos=end)
        wait_for(lambda:not c.commit_pending and not window.edit_controller.busy)
        assert window.session.position==position+2
        selected=c.selected_object;center=(f.Rect(selected.rect).tl+f.Rect(selected.rect).br)/2
        view=c.mapFromScene(c.page_scene(center))
        QTest.mouseDClick(c.viewport(),Qt.MouseButton.LeftButton,pos=view)
        QTest.mouseRelease(c.viewport(),Qt.MouseButton.LeftButton,pos=view)
        assert window.inline_text and window.inline_text.editor.toPlainText().replace('\n','').replace(' ','')=='Normalboldtext'
        wait_for(lambda:c.preview_identity is not None and not window.edit_controller.busy)
        assert not c.preview_items[0].isVisible()
        window.cancel_inline_text();assert c.preview_items[0].isVisible()
        window.undo();window.undo();assert window.session.position==position
        assert abs(discover(window.session.doc[0])[0].rect[1]-obj.rect[1])<.1
    finally:
        window.cancel_inline_text();window.session.saved_position=window.session.position;window.close()


def test_text_preview_rejects_other_box_on_same_page(app,objects_pdf,monkeypatch):
    from dataclasses import replace
    from paperlight.objects import object_identity
    from paperlight.core import PdfSession
    session=PdfSession(str(objects_pdf));c=Canvas()
    try:
        c.mode='edit';c.show_page(session.doc[0],1)
        first=next(o for o in discover(session.doc[0]) if o.kind=='text')
        second=replace(first,rect=tuple(f.Rect(first.rect)+(0,100,0,100)))
        assert object_identity(first)!=object_identity(second)
        c.selected_object=second;c.accept_edit_preview(edit_worker.serial(first),{})
        assert c.preview_identity is None
    finally:c.close();session.close()


def test_scan_selection_keeps_original_pixels(app,tmp_path,monkeypatch):
    import io
    from PIL import Image,ImageChops,ImageStat
    from .test_pdf import create_scan
    from paperlight.core import PdfSession
    from paperlight.objects import PageObject,fingerprint
    path=tmp_path/'scan-preview.pdf';create_scan(path)
    session=PdfSession(str(path))
    try:
        page=session.doc[0]
        obj=PageObject('ocr',(45,85,450,115),fingerprint(page),text='SEARCHABLE SCANNED INVOICE')
        rows=[];monkeypatch.setattr(edit_worker,'emit',rows.append)
        edit_worker.process(dict(task='preview',path=str(session._working),password=session._working_password,page=0,scale=1,object=edit_worker.serial(obj)))
        expected=page.get_pixmap();result=Image.new('RGBA',(expected.width,expected.height),'white')
        for row in rows:
            result.alpha_composite(Image.open(io.BytesIO(base64.b64decode(row['png']))).convert('RGBA'),(row['x'],row['y']))
        diff=ImageChops.difference(result.convert('RGB'),Image.frombytes('RGB',(expected.width,expected.height),expected.samples))
        assert max(ImageStat.Stat(diff).mean)<.01
        assert not session.dirty
    finally:session.close()
