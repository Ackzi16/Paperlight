import ast
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel,QDialogButtonBox

from paperlight.app import Window,TextDialog
from paperlight.i18n import LanguageManager,STRINGS,t,activate
from .test_ui import app,wait_for
from .test_pdf import source


def manager_at(path):
    return LanguageManager(QSettings(str(path),QSettings.Format.IniFormat))


def test_static_and_dynamic_translations_preserve_document_values():
    for english,chinese in STRINGS.items():
        assert t(english,'zh_CN')==chinese
        # Several equivalent English errors intentionally share one Chinese text.
        assert t(t(chinese,'en'),'zh_CN')==chinese
    assert t('Page 12 of 300','zh_CN')=='第 12 页，共 300 页'
    assert t('第 12 页，共 300 页','en')=='Page 12 of 300'
    text='Page 12\nRead Search 添加文本 Invoice date 2026-10-16'
    chinese=t(text,'zh_CN')
    assert chinese=='第 12 页\nRead Search 添加文本 Invoice date 2026-10-16'
    assert t(chinese,'en')==text
    path='D:/项目/Saved Search.pdf'
    message=f'Saved {path}. Original preserved.'
    assert path in t(message,'zh_CN')
    assert t(t(message,'zh_CN'),'en')==message
    status='2 matches in 300 indexed pages · OCR still running'
    assert t(status,'zh_CN')=='在已索引的 300 页中找到 2 处匹配 · 仍在识别文本'
    assert t(t(status,'zh_CN'),'en')==status


def test_live_help_language_switch_preserves_open_document(app,source,tmp_path):
    path=tmp_path/'settings.ini'
    manager=manager_at(path)
    window=Window(language_manager=manager)
    window.show()
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    window.mutate(lambda:window.session.ink(0,[(55,300),(120,320)]),preserve=True)
    window.choose_tool('select')
    window.canvas.select_range(0,10)
    selected=window.canvas.selected_text
    session=window.session
    position=session.position
    document_text=session.doc[0].get_text()
    filename=window.document_label.text()
    window.language_actions['zh_CN'].trigger()
    assert manager.current=='zh_CN'
    assert window.tool_actions['select'].text()=='选择文本'
    assert window.tabs.tabText(0)=='缩略图'
    assert any(a.text()=='帮助(&H)' for a in window.menuBar().actions())
    assert window.document_detail.text()=='第 1 页，共 3 页'
    assert window.pages.item(0).text()=='第 1 页'
    assert window.canvas.selected_text==selected
    assert window.session is session and session.position==position and session.dirty
    assert session.doc[0].get_text()==document_text
    assert window.document_label.text()==filename
    assert manager_at(path).current=='zh_CN'
    window.language_actions['en'].trigger()
    assert window.tool_actions['select'].text()=='Select text'
    assert window.tabs.tabText(0)=='Thumbnails'
    assert window.document_detail.text()=='Page 1 of 3'
    assert window.canvas.selected_text==selected
    window.session.saved_position=window.session.position
    window.close()
    activate('en')


def test_saved_chinese_startup_and_text_dialog(app,source,tmp_path):
    path=tmp_path/'preferences.ini'
    manager=manager_at(path)
    manager.set_language('zh_CN')
    window=Window(language_manager=manager_at(path))
    window.show()
    assert window.tabs.tabText(0)=='缩略图'
    window.open_path(str(source))
    wait_for(lambda:window.job is None)
    catalog=window.session.font_catalog()
    original='Read Search Saved text 原文'
    dialog=TextDialog(window,original,'Correct text',catalog,catalog.style(0))
    assert dialog.windowTitle()=='修改文本'
    assert dialog.editor.toPlainText()==original
    assert dialog.alignment.itemText(0)=='左对齐'
    assert '最常用' in dialog.font_combo.itemText(0)
    assert dialog.font_combo.currentData().name in dialog.font_combo.currentText()
    assert '字体' in dialog.font_note.text()
    buttons=dialog.findChild(QDialogButtonBox)
    assert buttons.button(QDialogButtonBox.StandardButton.Ok).text()=='应用文本'
    assert '取消' in buttons.button(QDialogButtonBox.StandardButton.Cancel).text()
    dialog.close()
    window.close()
    activate('en')


def test_marked_static_ui_strings_have_chinese_translations():
    tree=ast.parse('\n'.join(Path(name).read_text(encoding='utf-8') for name in (
        'paperlight/app.py','paperlight/signatures.py','paperlight/protection_dialog.py')))
    allowed={'Paperlight','●','‹','›','/ 0','100%','Language / 语言'}
    missing=[]
    for call in ast.walk(tree):
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='t' and call.args:
            value=call.args[0]
            if isinstance(value,ast.Constant) and isinstance(value.value,str):
                text=value.value
                if text not in allowed and t(text,'zh_CN')==text:
                    missing.append(text)
    assert not missing
