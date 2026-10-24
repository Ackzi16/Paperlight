import base64
import io
import json
import math
import time
import copy
import pymupdf as f
import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from paperlight.core import PdfSession
from paperlight.objects import discover
from paperlight.geometry import rotation_matrix,valid_path
from paperlight import edit_worker
from paperlight.app import Window
from .test_objects import objects_pdf,object_fonts
from .test_ui import app,wait_for


def test_rotation_and_nodes_preserve_other_content(objects_pdf,tmp_path):
    session=PdfSession(str(objects_pdf))
    try:
        native=session.doc[0].get_text();other=session.doc[1].get_pixmap().samples
        image=next(o for o in discover(session.doc[0]) if o.kind=='image')
        matrix=rotation_matrix(image.quad,37)
        session.edit_object(0,image,transform=matrix)
        moved=next(o for o in discover(session.doc[0]) if o.kind=='image')
        expected=f.Rect(image.rect)*matrix
        assert all(abs(a-b)<.02 for a,b in zip(expected,moved.rect))
        assert session.doc[1].get_pixmap().samples==other
        session.undo();session.redo()
        shape=next(o for o in discover(session.doc[0]) if o.title=='Rectangle' and o.writable)
        nodes=copy.deepcopy(shape.path);nodes[1][2]+=25
        assert valid_path(nodes)
        session.edit_object(0,shape,path=nodes)
        changed=next(o for o in discover(session.doc[0]) if o.kind=='shape' and abs(o.rect[0]-45)<.1)
        assert any(abs(p.y-75)<.1 for item in changed.drawing['items'] for p in item[1:] if isinstance(p,f.Point))
        assert session.doc[0].get_text()==native
        before=session.position
        with pytest.raises(ValueError):session.edit_object(0,changed,path=[['M',float('nan'),0],['L',0,0]])
        assert session.position==before
        session.save(tmp_path/'geometry.pdf')
        with f.open(tmp_path/'geometry.pdf') as saved:
            assert saved[0].get_text()==native
    finally:session.close()


@pytest.mark.parametrize('rotation',[0,90])
def test_worker_layers_preserve_occlusion(objects_pdf,monkeypatch,rotation):
    session=PdfSession(str(objects_pdf))
    try:
        if rotation:session.rotate(0)
        obj=next(o for o in discover(session.doc[0]) if o.title=='Rectangle' and o.writable)
        rows=[];monkeypatch.setattr(edit_worker,'emit',rows.append)
        edit_worker.process(dict(task='preview',path=str(session._working),password=session._working_password,page=0,scale=1,object=edit_worker.serial(obj)))
        expected=session.doc[0].get_pixmap(alpha=False)
        composite=Image.new('RGBA',(expected.width,expected.height),'white')
        for row in rows:
            layer=Image.open(io.BytesIO(base64.b64decode(row['png']))).convert('RGBA')
            composite.alpha_composite(layer,(row['x'],row['y']))
        from PIL import ImageChops,ImageStat
        difference=ImageChops.difference(composite.convert('RGB'),Image.frombytes('RGB',(expected.width,expected.height),expected.samples))
        assert max(ImageStat.Stat(difference).mean)<.2
    finally:session.close()


def test_retained_drag_rotation_escape_and_single_undo(app,objects_pdf,tmp_path):
    window=Window();window.show();window.open_path(str(objects_pdf));wait_for(lambda:window.job is None)
    try:
        window.choose_tool('edit');c=window.canvas
        wait_for(lambda:bool(c.page_objects) and not c.commit_pending)
        obj=next(o for o in c.page_objects if o.title=='Ellipse' and o.writable)
        c.selected_object=obj;c.paint_objects();window.edit_controller.preview(obj)
        wait_for(lambda:c.preview_identity is not None)
        identities=[id(i) for i in c.outline_items];position=window.session.position
        control=next(x for x in c.controls() if x[0]=='rotate')
        start=c.mapFromScene(control[-1]);center=c.page_scene(sum(c.object_quad(obj),f.Point())/4)
        end=c.mapFromScene(center.x()+65,center.y())
        QTest.mousePress(c.viewport(),Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(c.viewport(),end)
        assert c.object_drag and c.object_drag['changed']
        assert [id(i) for i in c.outline_items]==identities
        assert window.session.position==position
        QTest.keyClick(c,Qt.Key.Key_Escape)
        QTest.mouseRelease(c.viewport(),Qt.MouseButton.LeftButton,pos=end)
        assert window.session.position==position
        QTest.mousePress(c.viewport(),Qt.MouseButton.LeftButton,pos=start)
        timings=[]
        for n in range(120):
            point=start+(end-start)*(n/119)
            tick=time.perf_counter();QTest.mouseMove(c.viewport(),point);timings.append((time.perf_counter()-tick)*1000)
        QTest.mouseRelease(c.viewport(),Qt.MouseButton.LeftButton,pos=end)
        assert window.session.position==position+1
        wait_for(lambda:not c.commit_pending)
        result=dict(events=len(timings),median_ms=sorted(timings)[60],p95_ms=sorted(timings)[114],note='Offscreen event processing; excludes display presentation and commit.')
        (tmp_path/'interaction.json').write_text(json.dumps(result))
        print('INTERACTION',json.dumps(result))
        window.undo();assert window.session.position==position
    finally:
        window.session.saved_position=window.session.position;window.close()


def test_point_gesture_keeps_controls_and_keyboard_nudge(app,objects_pdf):
    window=Window();window.show();window.open_path(str(objects_pdf));wait_for(lambda:window.job is None)
    try:
        window.choose_tool('edit');c=window.canvas
        wait_for(lambda:bool(c.page_objects) and not c.commit_pending)
        obj=next(o for o in c.page_objects if o.title=='Ellipse' and o.writable)
        c.selected_object=obj;window.toggle_point_editing()
        wait_for(lambda:c.preview_identity is not None)
        control=next(x for x in c.controls() if x[2]=='control')
        start=c.mapFromScene(control[-1]);end=start+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(18,12)
        position=window.session.position
        QTest.mousePress(c.viewport(),Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(c.viewport(),end)
        QTest.mouseRelease(c.viewport(),Qt.MouseButton.LeftButton,pos=end)
        wait_for(lambda:not c.commit_pending and not window.edit_controller.busy)
        assert c.point_mode and c.selected_object and c.controls()[0][0]=='node'
        assert window.session.position==position+1
        original=c.selected_object.rect
        QTest.keyClick(c,Qt.Key.Key_Right,Qt.KeyboardModifier.ShiftModifier)
        wait_for(lambda:not c.commit_pending and not window.edit_controller.busy)
        assert abs(c.selected_object.rect[0]-original[0]-10)<.1
        window.undo();assert window.session.position==position+1
    finally:
        window.session.saved_position=window.session.position;window.close()

