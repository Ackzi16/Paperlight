from datetime import date
import pymupdf as fitz
from PySide6.QtCore import QSettings, Qt, QPoint, QTimer
from PySide6.QtGui import QFontInfo
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from paperlight.app import Window
from paperlight.core import PdfSession
from paperlight.i18n import LanguageManager, activate
from paperlight.signatures import SignatureDialog, SignatureStore, normalize_strokes, format_date, DATE_FORMATS
from .test_ui import app, wait_for
from .test_pdf import source


def manager(tmp_path):
    return LanguageManager(QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat))


def test_continuous_page_navigation_editing_and_selection(app, source, tmp_path):
    settings = manager(tmp_path)
    window = Window(settings)
    window.error = lambda exc: (_ for _ in ()).throw(exc)
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    window.view_actions['continuous'].trigger()
    QTest.qWait(80)
    assert window.continuous
    assert len(window.canvas.page_layout)==3
    assert window.canvas.sceneRect().height()>window.canvas.viewport().height()*3
    window.go_page(1)
    wait_for(lambda:window.page_index==1)
    origin = window.canvas.page_origin
    assert origin.y()>0
    # Drag on the second page; the stored ink must use that page's coordinates.
    window.choose_tool('draw')
    def screen(x,y):
        p = fitz.Point(x,y)*window.session.doc[window.page_index].rotation_matrix
        return window.canvas.mapFromScene(p.x*window.canvas.factor+window.canvas.page_origin.x(),
                                          p.y*window.canvas.factor+window.canvas.page_origin.y())
    a,b = screen(70,300),screen(140,325)
    QTest.mousePress(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=a)
    QTest.mouseMove(window.canvas.viewport(),b,delay=25)
    QTest.mouseRelease(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=b)
    assert len(list(window.session.doc[1].annots()))==1
    assert not list(window.session.doc[0].annots() or [])
    page = window.session.doc[1]
    points = next(page.annots()).vertices[0]
    assert abs(points[0][0]-70)<2
    assert abs(points[0][1]-300)<2
    assert window.capture_signature_action.isEnabled()
    window.choose_tool('select')
    window.canvas.select_range(0,10)
    assert window.canvas.selected_text=='Paperlight'
    assert window.canvas.selection_items[0].rect().top()>window.canvas.page_origin.y()
    window.go_page(2)
    window.rotate()
    p = fitz.Point(100,150)*window.session.doc[2].rotation_matrix
    screen_point = window.canvas.mapFromScene(p.x*window.canvas.factor+window.canvas.page_origin.x(),
                                              p.y*window.canvas.factor+window.canvas.page_origin.y())
    actual = window.canvas.pdf_point(screen_point)
    assert abs(actual.x-100)<2 and abs(actual.y-150)<2
    window.view_actions['single'].trigger()
    assert not window.continuous and window.page_index==2
    assert window.canvas.page_origin.y()==0
    assert window.canvas.sceneRect().height()<window.canvas.viewport().height()+120
    window.session.saved_position=window.session.position
    window.close()
    restored=Window(manager(tmp_path))
    assert not restored.continuous
    restored.close()


def test_large_continuous_document_keeps_bounded_rasters(app,tmp_path):
    path=tmp_path/'many-pages.pdf'
    with fitz.open() as doc:
        for n in range(300):
            page=doc.new_page(width=595 if n%2 else 620,height=842)
            page.insert_text((55,75),f'Page {n+1}')
        doc.save(path)
    settings=manager(tmp_path)
    window=Window(settings)
    window.show()
    window.open_path(str(path))
    window.set_page_mode('continuous')
    wait_for(lambda:window.job is None)
    assert len(window.canvas.page_layout)==300
    assert 0<len(window.canvas.page_images)<8
    window.go_page(180)
    QTest.qWait(80)
    assert window.page_index==180
    assert 180 in window.canvas.page_images
    assert 0 not in window.canvas.page_images
    assert len(window.canvas.page_images)<8
    # Real scrollbar changes update page number and thumbnail without arrow clicks.
    window.canvas.verticalScrollBar().setValue(round(window.canvas.page_layout[250].top()))
    wait_for(lambda:window.page_index==250)
    assert window.page_number.value()==251
    assert window.pages.currentRow()==250
    window.close()
    restored=Window(manager(tmp_path))
    assert restored.continuous
    restored.close()


def test_chinese_ui_font_is_explicit_and_document_unchanged(app,source,tmp_path):
    settings=manager(tmp_path)
    window=Window(settings)
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    text=window.session.doc[0].get_text()
    settings.set_language('zh_CN')
    app.processEvents()
    assert QFontInfo(window.document_detail.font()).family()=='Microsoft YaHei UI'
    assert window.session.doc[0].get_text()==text
    assert not window.session.dirty
    assert window.view_actions['continuous'].text()=='连续滚动'
    window.close()
    activate('en')


def test_signature_pad_store_reload_and_date_preferences(app,tmp_path):
    store=SignatureStore(tmp_path/'signatures.json')
    settings=manager(tmp_path).settings
    dialog=SignatureDialog(store=store,settings=settings)
    dialog.show()
    QTest.qWait(30)
    for points in [[QPoint(40,90),QPoint(90,40),QPoint(155,110)],
                   [QPoint(60,130),QPoint(220,95)]]:
        QTest.mousePress(dialog.pad,Qt.MouseButton.LeftButton,pos=points[0])
        for point in points[1:]:
            QTest.mouseMove(dialog.pad,point,delay=12)
        QTest.mouseRelease(dialog.pad,Qt.MouseButton.LeftButton,pos=points[-1])
    dialog.name.setText('我的签名')
    dialog.save_signature()
    assert len(store.load())==1
    assert store.load()[0]['name']=='我的签名'
    assert len(store.load()[0]['strokes'])==2
    dialog.include_date.setChecked(True)
    dialog.date_format.setCurrentIndex(dialog.date_format.findData('yyyy年MM月dd日'))
    dialog.accept()
    reopened=SignatureDialog(store=SignatureStore(store.path),settings=settings)
    reopened.saved.setCurrentIndex(1)
    assert len(reopened.pad.strokes)==2
    assert reopened.include_date.isChecked()
    assert reopened.date_format.currentData()=='yyyy年MM月dd日'
    assert format_date('yyyy年MM月dd日') in reopened.date_preview.text()
    reopened.delete_signature()
    assert not store.load()
    reopened.close()


def test_signature_date_and_undo_are_one_edit(source,tmp_path):
    expected=['2026-01-02','02/01/2026','01/02/2026','02 Jan 2026','2026年01月02日']
    assert [format_date(p,date(2026,1,2)) for p in DATE_FORMATS]==expected
    signature=normalize_strokes([[(1,2),(40,30),(70,4)],[(5,40),(75,40)]])
    session=PdfSession(str(source))
    session.signature(0,fitz.Rect(50,300,270,410),signature,expected[-1])
    assert len(list(session.doc[0].annots()))==1
    assert expected[-1] in session.doc[0].get_text().replace(' ','')
    assert session.position==1
    session.undo()
    assert not list(session.doc[0].annots() or [])
    assert expected[-1] not in session.doc[0].get_text()
    session.redo()
    output=tmp_path/'signed.pdf'
    session.save(output)
    with fitz.open(output) as doc:
        assert expected[-1] in doc[0].get_text().replace(' ','')
        assert next(doc[0].widgets()).field_value=='Original customer'
    session.close()


def test_capture_page_ink_then_reuse_dated_signature(app,source,tmp_path,monkeypatch):
    store=SignatureStore(tmp_path/'signatures.json')
    window=Window(manager(tmp_path),signature_store=store)
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    window.choose_tool('draw')
    window.handle_gesture('draw',[fitz.Point(55,300),fitz.Point(110,330),fitz.Point(180,300)])
    def save_captured():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,SignatureDialog)
        assert dialog.pad.strokes
        dialog.name.setText('Personal')
        dialog.save_signature()
        dialog.reject()
    QTimer.singleShot(40,save_captured)
    window.capture_signature_action.trigger()
    assert len(store.load())==1
    def select_saved():
        dialog=QApplication.activeModalWidget()
        dialog.saved.setCurrentIndex(1)
        dialog.include_date.setChecked(True)
        dialog.date_format.setCurrentIndex(1)
        dialog.accept()
    QTimer.singleShot(40,select_saved)
    window.open_signature_manager()
    assert window.canvas.mode=='signature'
    monkeypatch.setattr('paperlight.app.format_date',lambda p:format_date(p,date(2026,10,17)))
    window.handle_gesture('signature',fitz.Rect(55,400,280,510))
    assert len(list(window.session.doc[0].annots()))==2
    assert '17/10/2026' in window.session.doc[0].get_text()
    window.session.saved_position=window.session.position
    window.close()
