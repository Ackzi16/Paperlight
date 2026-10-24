import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pymupdf as fitz
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QDoubleSpinBox
from PySide6.QtTest import QTest
from paperlight.app import Window
from .test_pdf import source,create_scan
from .test_ui import app,wait_for


def open_window(path):
    window=Window()
    window.error=lambda exc: (_ for _ in ()).throw(RuntimeError(str(exc)))
    window.show()
    window.open_path(str(path))
    wait_for(lambda:window.job is None)
    return window


def close_window(window):
    window.cancel_inline_text()
    window.session.saved_position=window.session.position
    window.close()


def test_read_cursor_selects_native_text_without_markup(app,source):
    window=open_window(source)
    try:
        assert window.canvas.mode=='read' and not window.markup_bar.isVisible()
        units=window.canvas.text_model.units
        first,last=fitz.Rect(units[0].rect),fitz.Rect(units[9].rect)
        def view(point):
            return window.canvas.mapFromScene(point.x*window.canvas.factor,point.y*window.canvas.factor)
        start=view(fitz.Point(first.x0+.1,(first.y0+first.y1)/2))
        end=view(fitz.Point(last.x1-.1,(last.y0+last.y1)/2))
        QTest.mouseMove(window.canvas.viewport(),start)
        assert window.canvas.cursor().shape()==Qt.CursorShape.IBeamCursor
        QTest.mousePress(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(window.canvas.viewport(),end)
        QTest.mouseRelease(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=end)
        assert window.canvas.selected_text=='Paperlight'
        assert window.copy_action.isEnabled()
        assert not window.markup_bar.isVisible()
    finally: close_window(window)


def test_click_live_text_and_save_without_separate_dialog(app,source,tmp_path):
    window=open_window(source)
    try:
        window.choose_tool('text')
        point=window.canvas.mapFromScene(75*window.canvas.factor,330*window.canvas.factor)
        QTest.mouseClick(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=point)
        box=window.inline_text
        assert box is not None and QApplication.activeModalWidget() is None
        assert abs(box.pos().x()-point.x())<2 and abs(box.pos().y()-point.y())<2
        box.editor.setPlainText('Live text 中文')
        assert box.isVisible() and box.more_button.isVisible()
        assert 'Live text' not in window.session.doc[0].get_text()
        assert window.save_action.isEnabled()
        window.save_action.trigger()
        assert window.inline_text is None
        with fitz.open(source) as saved:
            assert 'Live text' in saved[0].get_text() and '中文' in saved[0].get_text()
        window.undo()
        assert 'Live text' not in window.session.doc[0].get_text()
    finally: close_window(window)


def test_cancel_and_overflow_keep_original(app,source):
    window=open_window(source)
    try:
        window.choose_tool('text'); window.start_inline_text(fitz.Point(60,400))
        window.inline_text.editor.setPlainText('Cancel me')
        QTest.keyClick(window.inline_text.editor,Qt.Key.Key_Escape)
        assert window.inline_text is None and not window.session.dirty
        window.start_inline_text(fitz.Point(60,400))
        window.inline_text.editor.setPlainText('too much text '*500)
        errors=[];window.error=lambda exc:errors.append(str(exc))
        assert not window.commit_inline_text()
        assert errors and window.inline_text is not None and not window.session.dirty
    finally: close_window(window)


def test_ocr_button_writes_layer_corrects_scan_and_undo(app,tmp_path):
    path=tmp_path/'scan.pdf';create_scan(path)
    window=open_window(path)
    try:
        before=window.session.doc[0].get_pixmap().samples
        assert not window.session.doc[0].search_for('OCEAN')
        window.index_action.trigger()
        wait_for(lambda:window.job is None and window.session.dirty,30000)
        assert window.session.doc[0].search_for('OCEAN')
        assert window.session.doc[0].search_for('中文文件')
        assert window.session.doc[0].get_pixmap().samples==before
        words_before=window.session.doc[0].get_text('words')
        window.index_action.trigger()
        wait_for(lambda:window.job is None,30000)
        assert len(window.session.doc[0].get_text('words'))==len(words_before)
        box=window.session.doc[0].search_for('OCEAN')[0]+(-1,-2,8,4)
        window.handle_gesture('correct',box)
        assert 'OCEAN' in window.inline_text.editor.toPlainText()
        window.inline_text.editor.setPlainText('RIVER')
        assert window.commit_inline_text()
        assert window.session.doc[0].search_for('RIVER')
        assert not window.session.doc[0].search_for('OCEAN')
        window.undo()
        assert window.session.doc[0].search_for('OCEAN')
        window.undo()
        assert not window.session.doc[0].search_for('OCEAN')
        window.redo()
        assert window.session.doc[0].search_for('OCEAN')
        assert window.save_current()
        with fitz.open(path) as saved: assert saved[0].search_for('OCEAN')
    finally: close_window(window)


def test_rotated_page_click_anchors_box_and_commit(app,source):
    window=open_window(source)
    try:
        window.rotate();window.choose_tool('text')
        displayed=fitz.Point(180,260)
        point=displayed*window.session.doc[0].derotation_matrix
        window.start_inline_text(point)
        box=window.inline_text
        expected=window.canvas.mapFromScene(displayed.x*window.canvas.factor,displayed.y*window.canvas.factor)
        assert abs(box.pos().x()-expected.x())<2 and abs(box.pos().y()-expected.y())<2
        box.editor.setPlainText('Rotated note')
        QTest.keyClick(box.editor,Qt.Key.Key_Return,Qt.KeyboardModifier.ControlModifier)
        assert window.inline_text is None
        assert window.session.doc[0].search_for('Rotated note')
    finally: close_window(window)


def test_three_dot_formats_live_and_cancel_is_non_destructive(app,source):
    from PySide6.QtCore import QTimer
    window=open_window(source)
    try:
        window.choose_tool('text');window.start_inline_text(fitz.Point(70,350))
        box=window.inline_text;box.editor.setPlainText('Format preview')
        box.more_button.click()
        panel=box.format_panel
        assert isinstance(panel,QDialog) and panel.isVisible()
        panel.findChildren(QDoubleSpinBox)[0].setValue(18)
        assert box.style.size==18
        assert box.style.line_height>=18
        assert box.editor.font().pixelSize()==max(1,round(18*window.canvas.factor))
        panel.accept()
        assert box.style.size==18
        window.cancel_inline_text()
        assert not window.session.dirty and not window.save_action.isEnabled()
    finally: close_window(window)
