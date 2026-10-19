import pymupdf as fitz
import pytest
from pypdf import PdfReader
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog
from PySide6.QtCore import QTimer
from paperlight.core import PdfSession
from paperlight.security import Protection, EDIT_PERMISSIONS
from paperlight.protection_dialog import ProtectionDialog
from paperlight.app import Window
from paperlight.i18n import activate
from .test_pdf import source
from .test_ui import app, wait_for


@pytest.mark.parametrize('opening', ['', 'Reader-pass-中文'])
@pytest.mark.parametrize('print_copy', [False, True])
def test_protection_roundtrip_and_owner_unlock(source, tmp_path, opening, print_copy):
    original = source.read_bytes()
    output = tmp_path/'protected.pdf'
    with_session = PdfSession(str(source))
    with_session.save(output, Protection('Owner-pass-中文', opening, print_copy, print_copy))
    with_session.close()
    assert source.read_bytes() == original
    reader = PdfReader(output)
    assert reader.is_encrypted
    assert reader.trailer['/Encrypt']['/V'] == 5
    assert reader.trailer['/Encrypt']['/Length'] == 256
    assert reader.decrypt(opening)
    assert 'Paperlight test page 1' in reader.pages[0].extract_text()
    assert reader.get_fields()['customer']['/V'] == 'Original customer'
    with fitz.open(output) as doc:
        if opening:
            assert not doc.authenticate('wrong')
        assert doc.authenticate(opening) & 2
        assert not doc.permissions & EDIT_PERMISSIONS
        assert bool(doc.permissions & fitz.PDF_PERM_PRINT) == print_copy
        assert bool(doc.permissions & fitz.PDF_PERM_COPY) == print_copy
    session = PdfSession(str(output), opening)
    assert session.encrypted and session.readonly
    assert 'Paperlight test page 1' in session.doc[0].get_text()
    assert next(session.doc[0].widgets()).field_value == 'Original customer'
    assert session.copy_allowed == print_copy
    with pytest.raises(ValueError, match='owner password'):
        session.rotate(0)
    with pytest.raises(ValueError, match='owner password'):
        session.save(tmp_path/'bypass.pdf')
    with pytest.raises(ValueError, match='owner password'):
        session.split([0], tmp_path/'bypass.pdf')
    with pytest.raises(ValueError, match='Incorrect owner'):
        session.unlock(opening)
    session.unlock('Owner-pass-中文')
    assert not session.readonly and session.copy_allowed
    session.rotate(0)
    session.save(tmp_path/'decrypted.pdf')
    session.close()
    with fitz.open(tmp_path/'decrypted.pdf') as doc:
        assert not doc.needs_pass
        assert not doc.metadata['encryption']
        assert doc[0].rotation == 90
        assert 'Paperlight test page 1' in doc[0].get_text()
    owner_session = PdfSession(str(output), 'Owner-pass-中文')
    assert not owner_session.readonly
    owner_session.close()


def test_protect_then_continue_editing_and_failed_export(source, tmp_path):
    session = PdfSession(str(source))
    session.save(tmp_path/'protected.pdf', Protection('owner', 'reader'))
    with pytest.raises(ValueError, match='owner password'):
        session.merge(str(tmp_path/'protected.pdf'), 0, 'reader')
    assert len(session.doc) == 3
    session.rotate(1)
    session.save(tmp_path/'edited.pdf')
    with fitz.open(tmp_path/'edited.pdf') as doc:
        assert 'Paperlight test page 2' in doc[1].get_text()
        assert doc[1].rotation == 90
    destination = tmp_path/'existing.pdf'
    destination.write_bytes(b'original destination')
    with pytest.raises(ValueError):
        session.save(destination, Protection('same', 'same'))
    assert destination.read_bytes() == b'original destination'
    session.merge(str(tmp_path/'protected.pdf'), 0, 'owner')
    assert len(session.doc) == 6
    session.close()


def test_redacted_protected_export(source, tmp_path):
    session = PdfSession(str(source))
    session.mark_redaction(0, fitz.Rect(50,100,580,130))
    output = tmp_path/'redacted.pdf'
    with pytest.raises(ValueError, match='redactions'):
        session.save(output, Protection('secret-owner', 'secret-reader'))
    assert not output.exists()
    session.apply_redactions()
    session.save(output, Protection('secret-owner', 'secret-reader'))
    reader = PdfReader(output)
    assert reader.decrypt('secret-reader')
    assert 'ALPHA-923' not in ''.join(p.extract_text() for p in reader.pages)
    session.close()


def test_dialog_validation_and_chinese(app):
    activate('zh_CN')
    dialog = ProtectionDialog()
    assert dialog.windowTitle() == '保护 PDF'
    assert not dialog.open_password.isEnabled()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert '所有者密码' in dialog.validation.text()
    dialog.owner_password.setText('owner')
    dialog.owner_confirm.setText('different')
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.owner_confirm.setText('owner')
    dialog.require_open.setChecked(True)
    assert dialog.open_password.isEnabled()
    dialog.open_password.setText('reader')
    dialog.open_confirm.setText('reader')
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.protection().open_password == 'reader'
    assert 'reader' not in repr(dialog.protection())
    with pytest.raises(ValueError, match='40 UTF-8'):
        Protection('中'*14).validate()
    with pytest.raises(ValueError, match='different'):
        Protection('same', 'same').validate()
    dialog.close()
    activate('en')


def test_readonly_ui_and_unlock(app, source, tmp_path, monkeypatch):
    output = tmp_path/'restricted.pdf'
    session = PdfSession(str(source))
    session.save(output, Protection('owner', allow_copy=False))
    session.close()
    window = Window()
    window.error = lambda exc: (_ for _ in ()).throw(exc)
    window.show()
    window.open_path(str(output))
    wait_for(lambda: window.job is None)
    assert len(window.records) == 3
    assert window.session.readonly
    assert window.unlock_action.isEnabled()
    assert not window.protect_action.isEnabled()
    assert not window.export_action.isEnabled()
    assert window.index_action.isEnabled()
    assert window.next_action.isEnabled()
    window.choose_tool('draw')
    assert window.canvas.mode == 'read'
    window.choose_tool('select')
    window.canvas.select_range(0, 10)
    assert not window.copy_action.isEnabled()
    assert window.tool_actions['select'].isEnabled()
    window.copy_selection()
    cache = window.cache_root
    # Protected documents index only in the session's temporary directory.
    assert (window.session._working.parent/'search-cache').exists()
    monkeypatch.setattr(QInputDialog, 'getText', lambda *a: ('owner', True))
    window.unlock_editing()
    assert not window.session.readonly
    assert window.tool_actions['draw'].isEnabled()
    assert window.protect_action.isEnabled()
    assert window.export_action.isEnabled()
    temporary = window.session._working.parent
    window.close()
    assert not temporary.exists()


def test_file_protect_action_exports_current_edits(app, source, tmp_path, monkeypatch):
    output = tmp_path/'protected-ui.pdf'
    window = Window()
    window.error = lambda exc: (_ for _ in ()).throw(exc)
    window.show()
    window.open_path(str(source))
    wait_for(lambda: window.job is None)
    window.mutate(lambda: window.session.rotate(0), pages_changed=True)
    monkeypatch.setattr(window, 'output_path', lambda *a: str(output))
    def fill():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, ProtectionDialog)
        dialog.owner_password.setText('Owner-secret')
        dialog.owner_confirm.setText('Owner-secret')
        dialog.require_open.setChecked(True)
        dialog.open_password.setText('Reader-secret')
        dialog.open_confirm.setText('Reader-secret')
        dialog.accept()
    QTimer.singleShot(30, fill)
    window.protect_action.trigger()
    assert output.exists()
    assert window.session.dirty  # The active source has not been saved.
    assert not window.session.readonly
    with fitz.open(output) as doc:
        assert doc.authenticate('Reader-secret') == 2
        assert doc[0].rotation == 90
        assert 'Paperlight test page 1' in doc[0].get_text()
    window.session.saved_position=window.session.position
    window.close()
