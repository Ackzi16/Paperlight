import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from pathlib import Path

import pymupdf as fitz
import pytest
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest

from paperlight.app import Window, STYLE, TextDialog
from .test_pdf import source
from .test_typography import formatted_pdf


@pytest.fixture(scope='module')
def app():
    application=QApplication.instance() or QApplication([])
    # The offscreen plugin does not discover Windows TTC fonts automatically.
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    application.setApplicationName('Paperlight-Test')
    application.setStyleSheet(STYLE)
    return application


def wait_for(predicate,timeout=12000):
    elapsed=0
    while not predicate() and elapsed<timeout:
        QTest.qWait(30)
        elapsed+=30
    assert predicate()


def test_open_search_rotation_and_markup(app,source,tmp_path):
    window=Window()
    window.error=lambda exc: (_ for _ in ()).throw(exc)
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    assert len(window.records)==3
    window.search_box.setText('ALPHA-923')
    wait_for(lambda:window.results.count()==1)
    assert window.results.item(0).data(Qt.ItemDataRole.UserRole)['page']==0
    window.rotate()
    assert window.session.doc[0].rotation==90
    # Displayed point and PDF point must round-trip on rotated pages.
    pdf=fitz.Point(100,150)
    display=pdf*window.session.doc[0].rotation_matrix
    point=window.canvas.mapFromScene(display.x*window.canvas.factor,display.y*window.canvas.factor)
    actual=window.canvas.pdf_point(point)
    assert abs(actual.x-pdf.x)<2 and abs(actual.y-pdf.y)<2
    window.undo()
    assert window.session.doc[0].rotation==0
    window.choose_tool('draw')
    start=window.canvas.mapFromScene(80*window.canvas.factor,300*window.canvas.factor)
    end=window.canvas.mapFromScene(150*window.canvas.factor,320*window.canvas.factor)
    QTest.mousePress(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=start)
    QTest.mouseMove(window.canvas.viewport(),end,delay=10)
    QTest.mouseRelease(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=end)
    assert len(list(window.session.doc[0].annots()))==1
    def accept_text():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,TextDialog)
        dialog.editor.setPlainText('A short note 中文')
        dialog.accept()
    QTimer.singleShot(40,accept_text)
    window.handle_gesture('text',fitz.Rect(55,400,400,450))
    assert 'short note' in window.session.doc[0].get_text()
    window.start_index(False)
    wait_for(lambda:window.job is None)
    window.search_box.setText('short note')
    wait_for(lambda:window.results.count()==1)
    window.grab().save(str(tmp_path/'ui-edited.png'))
    window.session.saved_position=window.session.position
    window.close()


def test_ocr_process_and_clear_cache(app,tmp_path):
    from .test_pdf import create_scan
    path=tmp_path/'mixed.pdf'
    create_scan(path)
    window=Window()
    window.error=lambda exc: (_ for _ in ()).throw(exc)
    window.cache_root=tmp_path/'cache'
    window.remember_cache_action.setChecked(True)
    window.show()
    window.open_path(str(path))
    wait_for(lambda:window.job is None)
    window.start_index(True)
    wait_for(lambda:window.job is None,timeout=30000)
    assert window.ocr_complete
    window.search_box.setText('OCEAN')
    wait_for(lambda:window.results.count()>0)
    assert window.session_keys
    assert any(window.cache_root.iterdir())
    window.clear_cache()
    assert not list(window.cache_root.iterdir())
    assert not window.records
    window.close()


def test_tool_cursors_font_picker_and_compact_toolbar(app,source,tmp_path):
    window=Window()
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    assert not window.markup_bar.isVisible()
    window.choose_tool('text')
    assert window.markup_bar.isVisible()
    assert window.canvas.cursor().shape()==Qt.CursorShape.IBeamCursor
    window.choose_tool('draw')
    assert window.canvas.cursor().shape()==Qt.CursorShape.BitmapCursor
    window.choose_tool('redact')
    redact=window.canvas.cursor().pixmap().toImage()
    window.choose_tool('draw')
    assert window.canvas.cursor().pixmap().toImage()!=redact
    window.choose_tool('form')
    QTest.qWait(80)
    p=window.canvas.mapFromScene(90*window.canvas.factor,195*window.canvas.factor)
    QTest.mouseMove(window.canvas.viewport(),p)
    assert window.canvas.cursor().shape()==Qt.CursorShape.PointingHandCursor
    p=window.canvas.mapFromScene(400*window.canvas.factor,400*window.canvas.factor)
    QTest.mouseMove(window.canvas.viewport(),p)
    assert window.canvas.cursor().shape()==Qt.CursorShape.ArrowCursor
    catalog=window.session.font_catalog()
    style=catalog.style(0,fitz.Rect(50,100,480,130))
    dialog=TextDialog(window,'Replacement text','Correct text',catalog,style)
    assert dialog.size.value()==pytest.approx(12)
    assert dialog.font_combo.count()==len(catalog.choices)
    assert dialog.selected_style().choice is catalog.choices[0]
    window.grab().save(str(tmp_path/'new-markup.png'))
    dialog.close()
    window.session.saved_position=window.session.position
    window.close()


def test_document_font_picker_choices(app,formatted_pdf):
    window=Window()
    window.open_path(str(formatted_pdf))
    wait_for(lambda:window.job is None)
    catalog=window.session.font_catalog()
    dialog=TextDialog(window,'New text',catalog=catalog,style=catalog.style(0))
    assert dialog.font_combo.count()==4
    assert dialog.font_combo.currentData().name=='Times-Roman'
    dialog.font_combo.setCurrentIndex(2)
    assert dialog.selected_style().choice is catalog.choices[2]
    dialog.close()
    window.close()


def test_drag_copy_select_all_zoom_and_rotation(app,source,tmp_path):
    window=Window()
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    window.choose_tool('select')
    QTest.qWait(100)
    model=window.canvas.text_model
    target='Paperlight'
    def screen(point):
        point=fitz.Point(point)*window.session.doc[0].rotation_matrix
        return window.canvas.mapFromScene(point.x*window.canvas.factor,point.y*window.canvas.factor)
    first=fitz.Rect(model.units[0].rect)
    last=fitz.Rect(model.units[len(target)-1].rect)
    a=screen((first.x0+.1,(first.y0+first.y1)/2))
    b=screen((last.x1-.1,(last.y0+last.y1)/2))
    QTest.mousePress(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=a)
    QTest.mouseMove(window.canvas.viewport(),b,delay=20)
    QTest.mouseRelease(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=b)
    assert window.canvas.selected_text==target
    assert window.copy_action.isEnabled()
    QTest.keyClick(window.canvas,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier)
    assert QApplication.clipboard().text()==target
    window.change_zoom(1)
    QTest.qWait(40)
    assert window.canvas.selected_text==target
    assert window.canvas.selection_items
    window.grab().save(str(tmp_path/'select-text.png'))
    QTest.keyClick(window.canvas,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
    assert 'ALPHA-923' in window.canvas.selected_text
    assert not window.session.dirty
    QTest.keyClick(window.canvas,Qt.Key.Key_Escape)
    assert not window.canvas.selected_text and not window.copy_action.isEnabled()
    window.rotate()
    QTest.qWait(80)
    model=window.canvas.text_model
    first=fitz.Rect(model.units[0].rect)
    last=fitz.Rect(model.units[len(target)-1].rect)
    a=screen((first.x0+.1,(first.y0+first.y1)/2))
    b=screen((last.x1-.1,(last.y0+last.y1)/2))
    QTest.mousePress(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=b)
    QTest.mouseMove(window.canvas.viewport(),a,delay=20)
    QTest.mouseRelease(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=a)
    assert window.canvas.selected_text==target
    window.go_page(1)
    assert not window.canvas.selected_text
    window.session.saved_position=window.session.position
    window.close()
