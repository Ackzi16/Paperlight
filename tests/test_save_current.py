import pymupdf as fitz
import pytest
from pypdf import PdfReader
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QFileDialog
from paperlight.core import PdfSession
from paperlight.security import Protection
from paperlight.app import Window
from .test_ui import app,wait_for
from .test_pdf import source


def test_inplace_save_retains_session_undo_forms_and_repeated_saves(source):
    session=PdfSession(str(source))
    page=session.doc[0]
    field=next(page.widgets())
    session.fill(0,field.xref,'Saved in this file')
    session.rotate(1)
    session.save_in_place()
    assert not session.dirty
    with fitz.open(source) as output:
        assert next(output[0].widgets()).field_value=='Saved in this file'
        assert output[1].rotation==90
    session.undo()
    assert session.dirty
    session.save_in_place()
    with fitz.open(source) as output:
        assert output[1].rotation==0
    session.redo()
    session.save_in_place()
    with fitz.open(source) as output:
        assert output[1].rotation==90
    assert not session.dirty
    session.close()


def test_other_window_changes_are_not_overwritten(source,tmp_path):
    first,second=PdfSession(str(source)),PdfSession(str(source))
    first.rotate(0)
    second.rotate(2)
    first.save_in_place()
    newer=source.read_bytes()
    with pytest.raises(ValueError,match='changed outside'):
        second.save_in_place()
    assert source.read_bytes()==newer and second.dirty
    second.save(tmp_path/'recovered.pdf')
    with fitz.open(tmp_path/'recovered.pdf') as output:
        assert output[0].rotation==0 and output[2].rotation==90
    first.close()
    second.close()


def test_export_copy_does_not_mark_the_source_saved(source,tmp_path):
    original=source.read_bytes()
    session=PdfSession(str(source))
    session.rotate(0)
    session.save(tmp_path/'copy.pdf')
    assert session.dirty and source.read_bytes()==original
    session.save_in_place()
    assert not session.dirty and source.read_bytes()!=original
    session.close()


def test_replace_failure_leaves_source_intact_and_edits_unsaved(source,monkeypatch):
    original=source.read_bytes()
    session=PdfSession(str(source))
    session.rotate(0)
    def fail(*args):
        raise PermissionError('The file is open in another program.')
    monkeypatch.setattr('paperlight.core.os.replace',fail)
    with pytest.raises(PermissionError):
        session.save_in_place()
    assert source.read_bytes()==original and session.dirty
    assert session.doc[0].rotation==90
    assert not list(source.parent.glob('.paperlight-*.pdf'))
    session.close()


def test_external_change_during_write_is_not_overwritten(source,monkeypatch):
    session=PdfSession(str(source))
    session.rotate(0)
    newer=source.read_bytes()+b'\n% newer external version\n'
    original_save=fitz.Document.save
    def concurrent_save(doc,*args,**kwargs):
        result=original_save(doc,*args,**kwargs)
        source.write_bytes(newer)
        return result
    monkeypatch.setattr(fitz.Document,'save',concurrent_save)
    with pytest.raises(ValueError,match='changed outside'):
        session.save_in_place()
    assert source.read_bytes()==newer and session.dirty
    assert not list(source.parent.glob('.paperlight-*.pdf'))
    session.close()


@pytest.mark.parametrize('opening',['','Reader-secret'])
@pytest.mark.parametrize('redact',[False,True])
def test_inplace_keeps_both_passwords_permissions_and_redaction(source,tmp_path,opening,redact):
    protected=tmp_path/'protected.pdf'
    creator=PdfSession(str(source))
    creator.save(protected,Protection('Owner-secret',opening,allow_print=False,allow_copy=False))
    creator.close()
    original=protected.read_bytes()
    before=PdfReader(protected)
    before.decrypt(opening)
    permissions=int(before.trailer['/Encrypt']['/P'])
    session=PdfSession(str(protected),opening)
    with pytest.raises(ValueError,match='owner password'):
        session.save_in_place()
    assert protected.read_bytes()==original
    session.unlock('Owner-secret')
    if redact:
        session.mark_redaction(0,fitz.Rect(50,100,580,130))
        with pytest.raises(ValueError,match='redactions'):
            session.save_in_place()
        session.apply_redactions()
    else:
        page=session.doc[0]
        session.fill(0,next(page.widgets()).xref,'Owner edited 中文')
        session.rotate(1)
        session.undo()
        session.redo()
    session.save_in_place()
    assert not session.dirty
    reader=PdfReader(protected)
    assert reader.is_encrypted
    assert not reader.decrypt('wrong')
    assert reader.decrypt(opening)
    assert int(reader.trailer['/Encrypt']['/P'])==permissions
    assert reader.trailer['/Encrypt']['/Length']==256
    if redact:
        assert 'ALPHA-923' not in ''.join(p.extract_text() for p in reader.pages)
    else:
        assert reader.pages[1].rotation==90
        assert reader.get_fields()['customer']['/V']=='Owner edited 中文'
    assert reader.decrypt('Owner-secret')==2
    # A second save preserves unknown reader credentials too.
    session.rotate(2)
    session.save_in_place()
    second=PdfReader(protected)
    assert second.decrypt(opening)
    assert second.pages[2].rotation==90
    session.close()


def test_reader_with_edit_permission_saves_without_knowing_owner_password(source,tmp_path):
    path=tmp_path/'allowed.pdf'
    with fitz.open(source) as doc:
        doc.save(path,encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='Unknown-owner',
                 user_pw='Reader-password',permissions=-1)
    session=PdfSession(str(path),'Reader-password')
    assert not session.readonly
    session.rotate(0)
    session.save_in_place()
    reader=PdfReader(path)
    assert reader.decrypt('Reader-password')
    assert reader.pages[0].rotation==90
    assert reader.decrypt('Unknown-owner')==2
    session.close()


def test_ctrl_s_and_close_save_use_current_filename(app,source,monkeypatch):
    window=Window()
    window.error=lambda exc:(_ for _ in ()).throw(exc)
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    session=window.session
    window.rotate()
    def no_picker(*args,**kwargs):
        raise AssertionError('Save must not open a Save copy file picker.')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',no_picker)
    window.start_index(False)
    assert window.job is not None
    QTest.keyClick(window,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(50)
    assert window.session is session and not session.dirty
    assert window.job is None
    assert not window.save_action.isEnabled()
    assert '*' not in window.windowTitle()
    with fitz.open(source) as output:
        assert output[0].rotation==90
    window.rotate()
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.StandardButton.Save)
    assert window.confirm_discard()
    with fitz.open(source) as output:
        assert output[0].rotation==180
    window.close()
