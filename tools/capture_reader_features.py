import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QPA_FONTDIR','C:/Windows/Fonts')
from pathlib import Path
import sys
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from PySide6.QtCore import QSettings,QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from paperlight.app import Window
from paperlight.i18n import LanguageManager
from paperlight.signatures import SignatureDialog,SignatureStore,normalize_strokes

folder=root/'tmp'/'verification'
app=QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
app.setStyle('Fusion')
settings=QSettings(str(folder/'reader-features-screenshot.ini'),QSettings.Format.IniFormat)
manager=LanguageManager(settings)
manager.set_language('zh_CN')
window=Window(manager)
window.show()
window.open_path(str(root/'assets'/'Welcome to Paperlight.pdf'))
sample=normalize_strokes([[(10,65),(32,15),(22,64),(57,42),(45,65),(76,35),(67,67),(108,45),(98,67),(136,38),(127,67),(173,47)],
                          [(12,77),(175,70)]])

def capture():
    window.set_page_mode('continuous')
    window.canvas.verticalScrollBar().setValue(round(window.canvas.page_layout[0].bottom()-window.canvas.viewport().height()/2))
    QTimer.singleShot(180,capture_dialogs)

def capture_dialogs():
    window.grab().save(str(folder/'chinese-continuous.png'))
    for language in ('zh_CN','en'):
        manager.set_language(language)
        dialog=SignatureDialog(window,SignatureStore(folder/'screenshot-signatures.json'),settings,initial_signature=sample)
        dialog.include_date.setChecked(True)
        dialog.date_format.setCurrentIndex(4 if language=='zh_CN' else 0)
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(folder/f'signature-dialog-{language}.png'))
        dialog.close()
    window.close()

QTimer.singleShot(1500,capture)
app.exec()
