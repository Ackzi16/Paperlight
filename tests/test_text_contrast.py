import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pymupdf as f
import pytest
from PySide6.QtGui import QPalette,QColor,QTextCursor
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from paperlight.app import Window
from .test_ui import app,wait_for
from .test_objects import object_fonts


@pytest.mark.parametrize('mixed',[False,True])
def test_light_text_readable_and_saved_colors_preserved(app,tmp_path,mixed):
    path=tmp_path/'light-text.pdf'
    with f.open() as doc:
        page=doc.new_page();page.draw_rect((30,40,500,120),fill=(.08,.12,.2))
        page.insert_text((55,85),'White text ',fontsize=18,color=(1,1,1))
        if mixed:page.insert_text((150,85),'Black text',fontsize=18,color=(0,0,0))
        doc.save(path)
    w=Window();w.show();w.open_path(str(path));wait_for(lambda:w.job is None)
    try:
        w.choose_tool('edit');wait_for(lambda:bool(w.canvas.page_objects) and not w.canvas.commit_pending)
        obj=next(o for o in w.canvas.page_objects if o.kind=='text');w.choose_object(obj);box=w.inline_text
        expected='#767676' if mixed else '#202124'
        assert box.readable_background()==expected
        assert f'background:{expected}' in box.editor.styleSheet()
        box.editor.selectAll();QTest.qWait(30)
        assert box.editor.palette().color(QPalette.ColorRole.HighlightedText).name()=='#15171b'
        # Selection contrast is a display property, never a stored character color.
        cursor=box.editor.textCursor();cursor.movePosition(QTextCursor.MoveOperation.Start);cursor.clearSelection();box.editor.setTextCursor(cursor)
        box.rect.x1+=100;box.update_layout();box.editor.insertPlainText('New ')
        assert w.commit_inline_text();assert w.save_current()
        with f.open(path) as saved:
            spans=[s for b in saved[0].get_text('dict')['blocks'] if b['type']==0 for line in b['lines'] for s in line['spans']]
            assert any('New' in s['text'] and s['color']==0xffffff for s in spans)
            if mixed:assert any('Black' in s['text'] and s['color']==0 for s in spans)
            assert saved[0].get_drawings()[0]['fill']==pytest.approx((.08,.12,.2),abs=.001)
    finally:w.cancel_inline_text();w.session.saved_position=w.session.position;w.close()


def test_selection_overrides_light_system_palette(app,tmp_path):
    path=tmp_path/'ordinary-text.pdf'
    with f.open() as doc:
        page=doc.new_page();page.insert_text((50,80),'Selection stays readable',fontsize=16);doc.save(path)
    w=Window();w.show();w.open_path(str(path));wait_for(lambda:w.job is None)
    try:
        w.choose_tool('edit');wait_for(lambda:bool(w.canvas.page_objects) and not w.canvas.commit_pending)
        w.choose_object(next(o for o in w.canvas.page_objects if o.kind=='text'));box=w.inline_text
        palette=box.editor.palette();palette.setColor(QPalette.ColorRole.HighlightedText,QColor('white'));box.editor.setPalette(palette)
        box.editor.selectAll();box.editor.ensurePolished();QTest.qWait(20)
        assert 'selection-color:#15171b' in box.editor.styleSheet()
        assert box.readable_background()=='#ffffff'
        assert not w.session.dirty
    finally:w.cancel_inline_text();w.close()
