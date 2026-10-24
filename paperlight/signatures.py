"""Local reusable handwritten signatures and date formatting."""
from __future__ import annotations
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import uuid

from PySide6.QtCore import Qt, QPointF, QRectF, QStandardPaths, QSettings
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QDialogButtonBox)
from .i18n import t
from .local_protection import MAGIC,protect,unprotect,MAX_BLOB


DATE_FORMATS = ('yyyy-MM-dd','dd/MM/yyyy','MM/dd/yyyy','dd MMM yyyy','yyyy年MM月dd日')


def format_date(pattern, value=None):
    value = value or date.today()
    if pattern == 'dd/MM/yyyy':
        return f'{value.day:02}/{value.month:02}/{value.year:04}'
    if pattern == 'MM/dd/yyyy':
        return f'{value.month:02}/{value.day:02}/{value.year:04}'
    if pattern == 'dd MMM yyyy':
        month = ('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')[value.month-1]
        return f'{value.day:02} {month} {value.year:04}'
    if pattern == 'yyyy年MM月dd日':
        return f'{value.year:04}年{value.month:02}月{value.day:02}日'
    return value.isoformat()


def normalize_strokes(strokes):
    strokes = [s for s in strokes if len(s)>1]
    if not strokes:
        raise ValueError('Draw a signature before saving or placing it.')
    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    x,y = min(xs),min(ys)
    width,height = max(1,max(xs)-x),max(1,max(ys)-y)
    return dict(strokes=[[[float((a-x)/width),float((b-y)/height)] for a,b in s] for s in strokes],
                aspect=width/height)


class SignatureStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))/'signatures.json'

    def load(self):
        if not self.path.exists():
            return []
        if self.path.stat().st_size>MAX_BLOB:
            raise ValueError('The saved signature library could not be read.')
        raw = self.path.read_bytes()
        legacy = not raw.startswith(MAGIC)
        data = json.loads((raw if legacy else unprotect(raw,'signatures')).decode('utf-8'))
        if not isinstance(data,list):
            raise ValueError('The saved signature library could not be read.')
        validate_signatures(data)
        if legacy:
            self.write(data)
        return data

    def write(self, rows):
        validate_signatures(rows)
        payload = protect(json.dumps(rows,ensure_ascii=False).encode('utf-8'),'signatures')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.signatures-',suffix='.json',dir=self.path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(payload)
            os.replace(temporary,self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def save(self, name, signature, identity=None):
        name = name.strip()
        if not name:
            raise ValueError('Give this signature a name.')
        row = dict(id=identity or uuid.uuid4().hex, name=name, **signature)
        rows = self.load()
        rows = [r for r in rows if r['id'] != row['id']]
        rows.append(row)
        self.write(rows)
        return row

    def delete(self, identity):
        self.write([r for r in self.load() if r['id'] != identity])


def validate_signatures(rows):
    import math
    if not isinstance(rows,list) or len(rows)>200:
        raise ValueError('The saved signature library could not be read.')
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('name'),str):
            raise ValueError('The saved signature library could not be read.')
        aspect = row.get('aspect')
        strokes = row.get('strokes')
        if not isinstance(aspect,(float,int)) or not math.isfinite(aspect) or not 0<aspect<100000:
            raise ValueError('The saved signature library could not be read.')
        if not isinstance(strokes,list) or not 0<len(strokes)<=1000 or any(not isinstance(s,list) for s in strokes) or sum(len(s) for s in strokes)>100000:
            raise ValueError('The saved signature library could not be read.')
        for stroke in strokes:
            if not isinstance(stroke,list) or len(stroke)<2:
                raise ValueError('The saved signature library could not be read.')
            for point in stroke:
                if not isinstance(point,(list,tuple)) or len(point)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in point):
                    raise ValueError('The saved signature library could not be read.')


class SignaturePad(QWidget):
    def __init__(self):
        super().__init__()
        self.strokes = []
        self.drawing = False
        self.setMinimumSize(510,190)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def clear(self):
        self.strokes = []
        self.update()

    def signature(self):
        return normalize_strokes(self.strokes)

    def set_signature(self, signature):
        width = min(self.width()-60,(self.height()-48)*signature['aspect'])
        height = width/max(.01,signature['aspect'])
        x,y = (self.width()-width)/2,(self.height()-height)/2
        self.strokes = [[(x+a*width,y+b*height) for a,b in s] for s in signature['strokes']]
        self.update()

    def resizeEvent(self,event):
        if self.strokes and not self.drawing:
            self.set_signature(self.signature())
        super().resizeEvent(event)

    def paintEvent(self,event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor('white'))
        painter.setPen(QPen(QColor('#d7d7df'),1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),8,8)
        painter.setPen(QPen(QColor('#e3e6ec'),1,Qt.PenStyle.DashLine))
        painter.drawLine(25,self.height()-42,self.width()-25,self.height()-42)
        painter.setPen(QPen(QColor('#202a3a'),2.3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        for stroke in self.strokes:
            for first,second in zip(stroke,stroke[1:]):
                painter.drawLine(QPointF(*first),QPointF(*second))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.drawing = True
            self.strokes.append([(event.position().x(),event.position().y())])
            self.grabMouse()

    def mouseMoveEvent(self,event):
        if self.drawing:
            self.strokes[-1].append((max(2,min(self.width()-2,event.position().x())),
                                     max(2,min(self.height()-2,event.position().y()))))
            self.update()

    def mouseReleaseEvent(self,event):
        if self.drawing:
            self.drawing = False
            self.releaseMouse()
            self.update()


class SignatureDialog(QDialog):
    def __init__(self,parent=None,store=None,settings=None,initial_signature=None):
        super().__init__(parent)
        self.store = store or SignatureStore()
        self.settings = settings if settings is not None else QSettings('Paperlight','Paperlight')
        self.setWindowTitle(t('Saved signatures'))
        self.resize(620,490)
        layout = QVBoxLayout(self)
        intro = QLabel(t('Draw with your mouse, then save for reuse or place it in this PDF.'))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        line = QHBoxLayout()
        self.saved = QComboBox()
        self.saved.setMinimumWidth(260)
        self.saved.currentIndexChanged.connect(self.load_selected)
        line.addWidget(self.saved,1)
        new = QPushButton(t('New signature'))
        new.clicked.connect(self.new_signature)
        line.addWidget(new)
        self.delete_button = QPushButton(t('Delete signature'))
        self.delete_button.clicked.connect(self.delete_signature)
        line.addWidget(self.delete_button)
        layout.addLayout(line)
        self.pad = SignaturePad()
        layout.addWidget(self.pad,1)
        line = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText(t('Signature name'))
        line.addWidget(self.name,1)
        clear = QPushButton(t('Clear drawing'))
        clear.clicked.connect(self.pad.clear)
        line.addWidget(clear)
        save = QPushButton(t('Save signature'))
        save.clicked.connect(self.save_signature)
        line.addWidget(save)
        layout.addLayout(line)
        line = QHBoxLayout()
        self.include_date = QCheckBox(t("Include today's date"))
        self.include_date.setChecked(self.settings.value('signature/includeDate',False,type=bool))
        line.addWidget(self.include_date)
        self.date_format = QComboBox()
        for pattern in DATE_FORMATS:
            self.date_format.addItem(pattern,pattern)
        pattern = str(self.settings.value('signature/dateFormat',DATE_FORMATS[0]))
        self.date_format.setCurrentIndex(max(0,self.date_format.findData(pattern)))
        line.addWidget(QLabel(t('Date format')))
        line.addWidget(self.date_format)
        line.addStretch()
        layout.addLayout(line)
        self.date_preview = QLabel()
        layout.addWidget(self.date_preview)
        self.include_date.toggled.connect(self.update_preview)
        self.date_format.currentIndexChanged.connect(self.update_preview)
        note = QLabel(t('Saved signatures are encrypted for your Windows account. This is a visual signature, not a certificate-based digital signature.'))
        note.setWordWrap(True)
        note.setObjectName('muted')
        layout.addWidget(note)
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton(t('Place signature'),QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()
        if initial_signature:
            self.pad.set_signature(initial_signature)
        self.update_preview()

    def refresh(self, identity=None):
        self.saved.blockSignals(True)
        self.saved.clear()
        self.saved.addItem(t('New unsaved signature'),None)
        try:
            for row in self.store.load():
                self.saved.addItem(row['name'],row)
        except Exception:
            self.message.setText(t('The saved signature library could not be read.'))
        index = next((n for n in range(1,self.saved.count()) if self.saved.itemData(n)['id']==identity),0)
        self.saved.setCurrentIndex(index)
        self.saved.blockSignals(False)
        self.delete_button.setEnabled(index>0)
        if index:
            self.load_selected()

    def load_selected(self,*args):
        row = self.saved.currentData()
        self.delete_button.setEnabled(bool(row))
        if row:
            self.pad.set_signature(row)
            self.name.setText(row['name'])
        else:
            self.pad.clear()
            self.name.clear()

    def new_signature(self):
        self.saved.setCurrentIndex(0)
        self.load_selected()
        self.name.setFocus()

    def save_signature(self):
        try:
            current = self.saved.currentData()
            row = self.store.save(self.name.text(),self.pad.signature(),current['id'] if current else None)
            self.refresh(row['id'])
            self.message.setText(t('Signature saved on this computer.'))
        except Exception as exc:
            self.message.setText(t(str(exc)))

    def delete_signature(self):
        current = self.saved.currentData()
        if current:
            try:
                self.store.delete(current['id'])
                self.refresh()
                self.load_selected()
            except Exception as exc:
                self.message.setText(t(str(exc)))

    def update_preview(self,*args):
        self.date_format.setEnabled(self.include_date.isChecked())
        self.date_preview.setText(t('Date at placement')+' · '+format_date(self.date_format.currentData()) if self.include_date.isChecked() else '')

    def stamp(self):
        return dict(signature=self.pad.signature(),include_date=self.include_date.isChecked(),
                    date_format=self.date_format.currentData())

    def accept(self):
        try:
            self.stamp()
        except ValueError as exc:
            self.message.setText(t(str(exc)))
            return
        self.settings.setValue('signature/includeDate',self.include_date.isChecked())
        self.settings.setValue('signature/dateFormat',self.date_format.currentData())
        self.settings.sync()
        super().accept()
