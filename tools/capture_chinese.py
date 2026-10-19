import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QPA_FONTDIR','C:/Windows/Fonts')
from pathlib import Path
import sys
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from PySide6.QtCore import QSettings,QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from paperlight.app import Window,TextDialog,STYLE
from paperlight.i18n import LanguageManager

folder=root/'tmp'/'verification'
app=QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
app.setStyle('Fusion')
app.setStyleSheet(STYLE)
manager=LanguageManager(QSettings(str(folder/'chinese-screenshot.ini'),QSettings.Format.IniFormat))
manager.set_language('zh_CN')
window=Window(language_manager=manager)
window.show()
window.open_path(str(root/'assets'/'Welcome to Paperlight.pdf'))


def capture():
    window.choose_tool('select')
    app.processEvents()
    window.render()
    window.grab().save(str(folder/'chinese-interface.png'))
    catalog=window.session.font_catalog()
    dialog=TextDialog(window,'PDF text remains unchanged 原文保持不变','Correct text',catalog,catalog.style(0))
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(folder/'chinese-text-editor.png'))
    dialog.close()
    window.close()


QTimer.singleShot(1700,capture)
app.exec()
