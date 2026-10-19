import json
from pathlib import Path
import socket
import pymupdf as fitz
import pytest
from PySide6.QtCore import QSettings,Qt,QStandardPaths
from PySide6.QtWidgets import QLabel
from paperlight.local_protection import protect,unprotect,MAGIC
from paperlight.core import PdfSession
from paperlight.worker import index_document,cache_purpose,valid_record,MAX_OCR_PIXELS
from paperlight.signatures import SignatureStore,normalize_strokes
from paperlight.i18n import LanguageManager
from paperlight.app import Window
from .test_ui import app,wait_for
from .test_pdf import source


def test_windows_dpapi_roundtrip_binding_and_tamper_detection():
    secret=b'Highly-sensitive-document-SENTINEL-13579'
    blob=protect(secret,'audit-purpose')
    assert blob.startswith(MAGIC) and secret not in blob
    assert unprotect(blob,'audit-purpose')==secret
    with pytest.raises(OSError):
        unprotect(blob,'different-purpose')
    tampered=blob[:-1]+bytes([blob[-1]^1])
    with pytest.raises(OSError):
        unprotect(tampered,'audit-purpose')
    with pytest.raises(ValueError):
        unprotect(secret,'audit-purpose')


def test_signature_legacy_migration_and_no_plaintext_fallback(tmp_path,monkeypatch):
    path=tmp_path/'signatures.json'
    row=dict(id='test-id',name='SENSITIVE-SIGNATURE-NAME',**normalize_strokes([[(0,0),(20,12),(40,1)]]))
    path.write_text(json.dumps([row]),encoding='utf-8')
    store=SignatureStore(path)
    assert store.load()==[row]
    payload=path.read_bytes()
    assert payload.startswith(MAGIC) and b'SENSITIVE-SIGNATURE-NAME' not in payload
    assert not list(tmp_path.glob('.signatures-*'))
    def fail(*args):
        raise OSError('Protection unavailable')
    monkeypatch.setattr('paperlight.signatures.protect',fail)
    with pytest.raises(OSError):
        store.write([row])
    assert path.read_bytes()==payload


def test_working_pdf_and_index_snapshot_are_encrypted(source,tmp_path):
    original=source.read_bytes()
    session=PdfSession(str(source))
    session.rotate(0)
    snapshot=tmp_path/'index-snapshot.pdf'
    session.write_index_snapshot(snapshot)
    for path in (session._working,snapshot):
        with fitz.open(path) as doc:
            assert doc.needs_pass
            assert not doc.authenticate('')
            assert doc.authenticate(session._working_password)
            assert 'ALPHA-923' in doc[0].get_text()
        assert session._working_password.encode() not in path.read_bytes()
    assert source.read_bytes()==original
    session.close()


def test_cache_is_encrypted_tampering_rebuilds_and_schema_is_checked(source,tmp_path,capsys):
    cache=tmp_path/'cache'
    index_document(str(source),str(cache),ocr=False)
    capsys.readouterr()
    path=next(cache.rglob('0.bin'))
    blob=path.read_bytes()
    assert b'ALPHA-923' not in blob and blob.startswith(MAGIC)
    row=json.loads(unprotect(blob,cache_purpose(path)))
    assert valid_record(row,0)
    row['words'][0]['rect'][0]=float('nan')
    assert not valid_record(row,0)
    path.write_bytes(blob[:-1]+bytes([blob[-1]^1]))
    index_document(str(source),str(cache),ocr=False)
    results=[json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(r.get('kind')=='page' and r['page']==0 and not r['cached'] for r in results)


def test_session_only_cache_default_cleanup_and_worker_timeout(app,source,tmp_path):
    settings=LanguageManager(QSettings(str(tmp_path/'prefs.ini'),QSettings.Format.IniFormat))
    window=Window(settings,SignatureStore(tmp_path/'library.bin'))
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    assert not window.remember_cache_action.isChecked()
    cache=window.session_cache_root()
    assert cache.parent==window.session._working.parent and list(cache.rglob('*.bin'))
    window.start_index(False)
    assert window.job is not None
    window.index_timeout()
    assert window.job is None
    assert all(label.textFormat()==Qt.TextFormat.PlainText for label in window.findChildren(QLabel))
    window.close()
    assert not cache.exists()


def test_startup_diagnostic_omits_document_names_and_secrets(tmp_path,monkeypatch):
    from main import record_startup_error
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    record_startup_error(ValueError('SECRET-PASSWORD D:/Clients/Medical-PRIVATE.pdf'))
    log=(tmp_path/'Paperlight'/'startup-error.log').read_text()
    assert 'ValueError' in log
    assert 'SECRET-PASSWORD' not in log and 'PRIVATE' not in log and 'Clients' not in log


def test_huge_ocr_page_is_rejected_before_rasterization(tmp_path,capsys,monkeypatch):
    path=tmp_path/'huge.pdf'
    with fitz.open() as doc:
        doc.new_page(width=19000,height=19000)
        doc.save(path)
    called=[]
    def unsafe_ocr(*args,**kwargs):
        called.append(True)
        raise AssertionError('Oversized page must not reach rasterization')
    monkeypatch.setattr(fitz.Page,'get_textpage_ocr',unsafe_ocr)
    index_document(str(path),str(tmp_path/'cache'))
    rows=[json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert not called
    assert any(r.get('kind')=='done' and r['failures']==[0] for r in rows)


def test_quote_operator_redaction_is_removed_or_fails_closed(tmp_path):
    path=tmp_path/'quote-text.pdf'
    secret='SECRET-QUOTE-987'
    with fitz.open() as doc:
        page=doc.new_page()
        page.insert_font(fontname='helv')
        xref=doc.get_new_xref()
        doc.update_object(xref,'<<>>')
        doc.update_stream(xref,b"BT /helv 12 Tf 14 TL 55 700 Td (SECRET-QUOTE-987) ' ET")
        page.set_contents(xref)
        doc.save(path)
    session=PdfSession(str(path))
    rect=session.doc[0].search_for(secret)[0]
    session.mark_redaction(0,rect+(-1,-1,1,1))
    try:
        session.apply_redactions()
    except ValueError as exc:
        assert 'verification failed' in str(exc)
        assert session.pending_redactions()
        with pytest.raises(ValueError):
            session.save_in_place()
    else:
        session.save_in_place()
        with fitz.open(path) as output:
            assert secret not in output[0].get_text()
    session.close()


def test_offline_document_processing_with_python_socket_guard(source,tmp_path,capsys,monkeypatch):
    def deny(*args,**kwargs):
        raise AssertionError('Document processing attempted a Python network connection')
    monkeypatch.setattr(socket,'create_connection',deny)
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.setattr(socket.socket,'connect_ex',deny)
    session=PdfSession(str(source))
    session.rotate(0)
    session.save(tmp_path/'copy.pdf')
    session.close()
    index_document(str(source),str(tmp_path/'cache'),ocr=False)
    assert 'done' in capsys.readouterr().out


def test_legacy_plaintext_cache_is_removed_only_from_owned_cache(app,tmp_path,monkeypatch):
    cache=tmp_path/'owned-cache'
    legacy=cache/'search-v3'
    legacy.mkdir(parents=True)
    (legacy/'old.json').write_text('SENSITIVE-OLD-CACHE')
    unrelated=tmp_path/'unrelated.txt'
    unrelated.write_text('keep')
    original=QStandardPaths.writableLocation
    monkeypatch.setattr(QStandardPaths,'writableLocation',lambda location:str(cache) if location==QStandardPaths.StandardLocation.CacheLocation else original(location))
    prefs=LanguageManager(QSettings(str(tmp_path/'prefs.ini'),QSettings.Format.IniFormat))
    window=Window(prefs,SignatureStore(tmp_path/'signatures.bin'))
    assert not legacy.exists()
    assert unrelated.read_text()=='keep'
    window.close()


def test_oversized_document_geometry_is_rejected(tmp_path):
    path=tmp_path/'oversized.pdf'
    with fitz.open() as doc:
        doc.new_page(width=21000,height=842)
        doc.save(path)
    with pytest.raises(ValueError,match='page dimensions'):
        PdfSession(str(path))


def test_pdf_launch_actions_are_not_dispatched_by_app(app,tmp_path,monkeypatch):
    import os,subprocess
    from PySide6.QtGui import QDesktopServices
    def deny(*args,**kwargs):
        raise AssertionError('A PDF-controlled launch action was dispatched')
    monkeypatch.setattr(os,'startfile',deny)
    monkeypatch.setattr(subprocess,'Popen',deny)
    monkeypatch.setattr(QDesktopServices,'openUrl',deny)
    path=tmp_path/'launch-action.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((55,75),'Harmless action test')
        action=doc.get_new_xref()
        doc.update_object(action,'<< /S /Launch /F (paperlight-audit-sentinel-never.exe) >>')
        doc.xref_set_key(doc.pdf_catalog(),'OpenAction',f'{action} 0 R')
        doc.save(path)
    prefs=LanguageManager(QSettings(str(tmp_path/'prefs.ini'),QSettings.Format.IniFormat))
    window=Window(prefs,SignatureStore(tmp_path/'signatures.bin'))
    window.show()
    window.open_path(str(path))
    wait_for(lambda:window.job is None)
    assert window.session and window.session.doc[0].get_text().strip()=='Harmless action test'
    window.close()


def test_worker_cache_path_traversal_message_is_rejected(app,source,tmp_path,monkeypatch):
    prefs=LanguageManager(QSettings(str(tmp_path/'prefs.ini'),QSettings.Format.IniFormat))
    window=Window(prefs,SignatureStore(tmp_path/'signatures.bin'))
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    class FakeWorker:
        def readAllStandardOutput(self):
            return b'{"kind":"meta","key":"../../unrelated"}\n'
    stopped=[]
    def stop():
        stopped.append(True)
        window.job=None
    monkeypatch.setattr(window,'stop_index',stop)
    window.job=FakeWorker()
    window.receive_index()
    assert stopped and '../../unrelated' not in window.session_keys
    window.close()
