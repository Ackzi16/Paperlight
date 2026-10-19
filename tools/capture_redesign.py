import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QPA_FONTDIR','C:/Windows/Fonts')
from pathlib import Path
import sys
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
import pymupdf as fitz
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from paperlight.app import Window,TextDialog,STYLE

app=QApplication([])
app.setStyle('Fusion')
app.setStyleSheet(STYLE)
window=Window()
window.show()
window.open_path(str(root/'assets'/'Welcome to Paperlight.pdf'))
folder=root/'tmp'/'verification'


def capture():
    window.grab().save(str(folder/'redesign-reader.png'))
    window.choose_tool('correct')
    app.processEvents()
    window.render()
    window.grab().save(str(folder/'redesign-markup.png'))
    catalog=window.session.font_catalog()
    style=catalog.style(0,fitz.Rect(87,294,540,325))
    dialog=TextDialog(window,'Use the sidebar to move between pages. Ctrl+F searches text.',
                      'Correct text',catalog,style)
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(folder/'redesign-font-editor.png'))
    dialog.close()
    window.close()


QTimer.singleShot(2000,capture)
app.exec()
