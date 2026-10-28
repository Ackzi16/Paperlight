from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import bisect

import pymupdf as fitz
from PySide6.QtCore import Qt, QTimer, Signal, QProcess, QSize, QPointF, QRectF, QStandardPaths, QByteArray
from PySide6.QtGui import (QAction, QActionGroup, QColor, QFont, QIcon, QImage,
                           QKeySequence, QPainter, QPen, QPixmap, QBrush, QFontDatabase, QDoubleValidator)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QToolBar,
    QSplitter, QListWidget, QListWidgetItem, QAbstractItemView, QTabWidget,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QGraphicsView,
    QGraphicsScene, QInputDialog, QDialog, QDialogButtonBox, QPlainTextEdit,
    QColorDialog, QFrame, QProgressBar, QToolButton, QSizePolicy,
    QStyledItemDelegate, QStyle, QMenu)

from .core import PdfSession, page_range, insert_ocr_words, atomic_pdf_write
from .worker import search_words, word_rows, valid_record
from .theme import STYLE, icon, tool_cursor
from .typography import TextStyle
from .selection import PageText
from .inline_text import InlineTextBox
from .object_ui import ObjectCanvasMixin,ObjectWindowMixin
from .edit_controller import EditController
from .i18n import t,LanguageManager,activate
from .protection_dialog import ProtectionDialog
from .signatures import SignatureDialog, SignatureStore, format_date, normalize_strokes
from dataclasses import replace as replace_style





def pixmap_from_page(page, scale, annotations=True):
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False,
                          colorspace=fitz.csRGB, annots=annotations)
    image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(image)


class Canvas(ObjectCanvasMixin,QGraphicsView):
    gesture = Signal(str, object)
    object_chosen=Signal(object)
    object_changed=Signal(object)
    object_menu=Signal(object)
    object_deleted=Signal()
    preview_requested=Signal(object)
    edit_refresh_requested=Signal()
    clicked = Signal(object)
    text_clicked = Signal(object)
    remove_at = Signal(object)
    zoom_request = Signal(int)
    viewport_changed=Signal()
    selection_changed=Signal(str)
    selection_menu=Signal(object)
    page_activated=Signal(int)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.object_init()
        self.setBackgroundBrush(QColor('#d3d3d8'))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.mode = 'read'
        self.factor = 1
        self.points = []
        self.preview = None
        self.highlights = []
        self.pen_color = QColor('#245fae')
        self.pen_width = 2
        self.page_transform = fitz.Matrix(1, 1)
        self.page_bounds = fitz.Rect()
        self.form_rects=[]
        self.text_model=PageText()
        self.selection_items=[]
        self.selection_start=self.selection_end=0
        self.selection_key=None
        self.select_dragging=False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.page_origin = QPointF()
        self.continuous_doc = None
        self.page_layout = []
        self.page_starts = []
        self.page_images = {}
        self.layout_key = None
        self.active_page = 0
        self.scroll_refresh = QTimer(self)
        self.scroll_refresh.setSingleShot(True)
        self.scroll_refresh.timeout.connect(self.refresh_visible_pages)
        self.verticalScrollBar().valueChanged.connect(lambda: self.scroll_refresh.start(0))
        self.horizontalScrollBar().valueChanged.connect(lambda: self.scroll_refresh.start(0))

    def set_mode(self, mode):
        self.mode = mode
        self.select_dragging=False
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode == 'read' else QGraphicsView.DragMode.NoDrag)
        self.setCursor(tool_cursor(mode))
        self.paint_objects()

    def show_page(self, page, scale):
        self.continuous_doc = None
        self.layout_key = None
        self.page_layout = []
        self.page_images = {}
        self.page_origin = QPointF()
        self.scene().clear()
        self.highlights = []
        self.selection_items=[]
        self.preview = None
        self.factor = scale
        self.page_transform = page.derotation_matrix
        self.page_bounds = page.rect * page.derotation_matrix
        self.form_rects=[fitz.Rect(w.rect) for w in page.widgets() or []]
        self.active_page=page.number
        self.edit_source_path=str(page.parent.name)
        pixmap = self.edit_placeholder(page,scale) if self.mode=='edit' else pixmap_from_page(page, scale)
        if self.mode!='edit':self.remember_edit_raster(page,pixmap,scale)
        self.scene().addRect(3,5,pixmap.width(),pixmap.height(),QPen(Qt.PenStyle.NoPen),QBrush(QColor(0,0,0,24)))
        self.single_page_image=self.scene().addPixmap(pixmap)
        self.scene().setSceneRect(-32, -24, pixmap.width()+64, pixmap.height()+48)

    def show_document(self, doc, scale, key, current):
        self.continuous_doc = doc
        if key != self.layout_key:
            self.layout_key = key
            self.scene().clear()
            self.highlights = []
            self.selection_items = []
            self.preview = None
            self.page_images = {}
            self.factor = scale
            sizes = [(page.rect.width*scale, page.rect.height*scale) for page in doc]
            width = max(w for w,h in sizes)
            self.page_layout = []
            self.page_starts = []
            y = 0
            for w,h in sizes:
                rect = QRectF((width-w)/2, y, w, h)
                self.page_layout.append(rect)
                self.page_starts.append(y)
                shadow = self.scene().addRect(rect.translated(3,5), QPen(Qt.PenStyle.NoPen), QBrush(QColor(0,0,0,24)))
                shadow.setZValue(-2)
                background = self.scene().addRect(rect, QPen(Qt.PenStyle.NoPen), QBrush(QColor('white')))
                background.setZValue(-1)
                y += h+20
            self.scene().setSceneRect(-32,-24,width+64,y+28)
        self.activate_page(current, notify=False)
        self.refresh_visible_pages(activate=False)

    def activate_page(self, index, notify=True):
        if self.continuous_doc is None or self.continuous_doc.is_closed:
            return
        changed = index != self.active_page
        self.active_page = index
        page = self.continuous_doc[index]
        self.page_origin = self.page_layout[index].topLeft()
        self.page_transform = page.derotation_matrix
        self.page_bounds = page.rect * page.derotation_matrix
        self.form_rects = [fitz.Rect(w.rect) for w in page.widgets() or []]
        if changed and notify:
            self.page_activated.emit(index)

    def page_at(self, point):
        y = self.mapToScene(point).y()
        return max(0,min(len(self.page_layout)-1,bisect.bisect_right(self.page_starts,y)-1))

    def refresh_visible_pages(self, activate=True):
        doc = self.continuous_doc
        if doc is None or doc.is_closed or not self.page_layout:
            return
        visible = self.mapToScene(self.viewport().rect()).boundingRect().adjusted(0,-250,0,250)
        wanted = {n for n,r in enumerate(self.page_layout) if r.intersects(visible)}
        for n in set(self.page_images)-wanted:
            self.scene().removeItem(self.page_images.pop(n))
        for n in sorted(wanted-set(self.page_images)):
            page = doc[n]
            raster_scale = min(self.factor,4096/max(page.rect.width,page.rect.height))
            pix = self.edit_placeholder(page,raster_scale) if self.mode=='edit' else pixmap_from_page(page,raster_scale)
            if self.mode!='edit':self.remember_edit_raster(page,pix,raster_scale)
            item = self.scene().addPixmap(pix)
            item.setScale(self.factor/raster_scale)
            item.setPos(self.page_layout[n].topLeft())
            self.page_images[n] = item
        if self.mode=='edit' and wanted!=getattr(self,'edit_visible_pages',None):
            self.edit_visible_pages=wanted;self.edit_refresh_requested.emit()
        if activate and not self.points and not self.select_dragging:
            self.activate_page(self.page_at(self.viewport().rect().center()))

    def remember_edit_raster(self,page,pixmap,scale):
        if not hasattr(self,'edit_raster_cache'):self.edit_raster_cache={}
        self.edit_raster_cache[(str(page.parent.name),page.number)]=(pixmap,scale)
        while len(self.edit_raster_cache)>6:self.edit_raster_cache.pop(next(iter(self.edit_raster_cache)))

    def edit_placeholder(self,page,scale):
        cache=getattr(self,'edit_raster_cache',{})
        cached=cache.get((str(page.parent.name),page.number))
        if cached:
            return cached[0].scaled(max(1,round(page.rect.width*scale)),max(1,round(page.rect.height*scale)),Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
        pixmap=QPixmap(max(1,round(page.rect.width*scale)),max(1,round(page.rect.height*scale)));pixmap.fill(QColor('white'));return pixmap

    def scroll_to_page(self, index):
        if not self.page_layout:
            return
        rect = self.page_layout[index]
        self.verticalScrollBar().setValue(round(rect.top()-18))
        self.activate_page(index,notify=False)
        self.refresh_visible_pages(activate=False)

    @property
    def selected_text(self):
        return self.text_model.text(self.selection_start,self.selection_end)

    def set_text_model(self,model,key):
        if key!=self.selection_key or len(model.units)!=len(self.text_model.units):
            self.selection_start=self.selection_end=0
        self.text_model=model
        self.selection_key=key
        self.paint_selection()

    def select_range(self,start,end):
        self.selection_start=max(0,min(start,len(self.text_model.units)))
        self.selection_end=max(0,min(end,len(self.text_model.units)))
        self.paint_selection()

    def paint_selection(self):
        for item in self.selection_items:
            self.scene().removeItem(item)
        self.selection_items=[]
        for rect in self.text_model.rectangles(self.selection_start,self.selection_end):
            r=rect * ~self.page_transform
            item=self.scene().addRect(r.x0*self.factor+self.page_origin.x(),r.y0*self.factor+self.page_origin.y(),r.width*self.factor,r.height*self.factor,
                                      QPen(Qt.PenStyle.NoPen),QBrush(QColor(45,123,235,75)))
            item.setZValue(10)
            self.selection_items.append(item)
        self.selection_changed.emit(self.selected_text)

    def pdf_point(self, point):
        scene = self.mapToScene(point)
        p = fitz.Point((scene.x()-self.page_origin.x())/self.factor, (scene.y()-self.page_origin.y())/self.factor) * self.page_transform
        return fitz.Point(max(self.page_bounds.x0, min(p.x,self.page_bounds.x1)),
                          max(self.page_bounds.y0, min(p.y,self.page_bounds.y1)))

    def set_highlights(self, rects, rotation):
        for item in self.highlights:
            self.scene().removeItem(item)
        self.highlights = []
        for rect in rects:
            r = fitz.Rect(rect) * rotation
            item = self.scene().addRect(r.x0*self.factor+self.page_origin.x(), r.y0*self.factor+self.page_origin.y(),
                                       r.width*self.factor, r.height*self.factor,
                                       QPen(Qt.PenStyle.NoPen), QBrush(QColor(255, 209, 55, 105)))
            self.highlights.append(item)

    def mousePressEvent(self, event):
        if self.continuous_doc is not None:
            index = self.page_at(event.position().toPoint())
            if not self.page_layout[index].contains(self.mapToScene(event.position().toPoint())):
                super().mousePressEvent(event)
                return
            self.activate_page(index)
        if self.object_press(event): return
        if self.scene().items() and event.button() == Qt.MouseButton.RightButton:
            if self.mode in ('read','select'):
                self.selection_menu.emit(event.globalPosition().toPoint())
                return
            self.remove_at.emit(self.pdf_point(event.position().toPoint()))
            return
        p = self.pdf_point(event.position().toPoint())
        automatic_select = self.mode=='read' and self.text_model.contains(p)
        if (self.mode == 'read' and not automatic_select) or not self.scene().items():
            super().mousePressEvent(event)
            if self.mode=='read' and event.button()==Qt.MouseButton.LeftButton:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.pdf_point(event.position().toPoint())
            if self.mode=='select' or automatic_select:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.setFocus()
                self.select_dragging=True
                caret=self.text_model.caret(p)
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.select_range(self.selection_start,caret)
                else:
                    self.select_range(caret,caret)
                return
            if self.mode == 'text':
                self.text_clicked.emit(p)
                return
            if self.mode == 'form':
                self.clicked.emit(p)
                return
            self.points = [p]
            self.start_scene = self.mapToScene(event.position().toPoint())
            self.preview = None

    def mouseMoveEvent(self, event):
        if self.object_move(event): return
        if self.continuous_doc is not None and self.mode in ('read','select') and not event.buttons():
            index=self.page_at(event.position().toPoint())
            if self.page_layout[index].contains(self.mapToScene(event.position().toPoint())):
                self.activate_page(index)
        if self.select_dragging:
            self.select_range(self.selection_start,self.text_model.caret(self.pdf_point(event.position().toPoint())))
            return
        if not self.points:
            scene_point=self.mapToScene(event.position().toPoint())
            rotated=fitz.Point((scene_point.x()-self.page_origin.x())/self.factor,(scene_point.y()-self.page_origin.y())/self.factor)*self.page_transform
            inside=self.page_bounds.contains(rotated)
            if not inside:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            elif self.mode=='form':
                self.setCursor(Qt.CursorShape.PointingHandCursor if any(r.contains(rotated) for r in self.form_rects)
                               else Qt.CursorShape.ArrowCursor)
            elif self.mode in ('read','select') and not event.buttons():
                self.setCursor(Qt.CursorShape.IBeamCursor if self.text_model.contains(rotated) else Qt.CursorShape.ArrowCursor)
            elif self.mode=='read' and event.buttons() & Qt.MouseButton.LeftButton:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                self.setCursor(tool_cursor(self.mode))
            super().mouseMoveEvent(event)
            return
        p = self.pdf_point(event.position().toPoint())
        current = self.mapToScene(event.position().toPoint())
        if self.mode == 'draw':
            previous = self.points[-1] * ~self.page_transform
            self.scene().addLine(previous.x*self.factor+self.page_origin.x(), previous.y*self.factor+self.page_origin.y(),
                                 current.x(), current.y(), QPen(self.pen_color, self.pen_width*self.factor,
                                 Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            self.points.append(p)
        else:
            if self.preview:
                self.scene().removeItem(self.preview)
            x, y = min(self.start_scene.x(), current.x()), min(self.start_scene.y(),current.y())
            w, h = abs(current.x()-self.start_scene.x()), abs(current.y()-self.start_scene.y())
            fill = QColor(20,20,20,90) if self.mode == 'redact' else QColor(38,100,170,30)
            self.preview = self.scene().addRect(x,y,w,h,QPen(QColor('#346fa9'),1.3,Qt.PenStyle.DashLine),QBrush(fill))

    def mouseReleaseEvent(self, event):
        if self.object_release(event): return
        if self.select_dragging:
            self.select_dragging=False
            if self.mode=='read':
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.select_range(self.selection_start,self.text_model.caret(self.pdf_point(event.position().toPoint())))
            return
        if not self.points:
            super().mouseReleaseEvent(event)
            return
        points = self.points
        self.points = []
        end = self.pdf_point(event.position().toPoint())
        if self.mode == 'draw':
            if len(points) > 1:
                self.gesture.emit(self.mode, points)
        else:
            rect = fitz.Rect(points[0], end)
            rect.normalize()
            if rect.width > 3 and rect.height > 3:
                self.gesture.emit(self.mode, rect)
            elif self.preview:
                self.scene().removeItem(self.preview)
                self.preview = None

    def mouseDoubleClickEvent(self,event):
        if self.mode=='edit' and event.button()==Qt.MouseButton.LeftButton:
            obj=self.object_hit(self.pdf_point(event.position().toPoint()))
            if obj and obj.kind in ('text','ocr','annotation'):
                self.object_drag=None;self.selected_object=obj;self.paint_objects();self.object_chosen.emit(obj)
                return
        if self.mode in ('read','select') and self.text_model.contains(self.pdf_point(event.position().toPoint())) and event.button()==Qt.MouseButton.LeftButton:
            self.select_dragging=False
            caret=self.text_model.caret(self.pdf_point(event.position().toPoint()))
            self.select_range(*self.text_model.word_range(caret))
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self,event):
        if self.object_keypress(event):return
        if self.mode=='edit' and event.key()==Qt.Key.Key_Escape and self.object_drag:
            obj=self.object_drag['obj'];self.object_drag=None
            if obj.kind in ('text','ocr','annotation'):self.object_changed.emit(dict(obj=obj,transform=tuple(fitz.Identity),cancel=True))
            self.apply_preview_transform(fitz.Identity);self.paint_objects();return
        if self.mode=='edit' and event.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace):
            self.object_deleted.emit();return
        if event.key()==Qt.Key.Key_Escape and self.selected_text:
            self.select_range(0,0)
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_request.emit(1 if event.angleDelta().y() > 0 else -1)
        else:
            super().wheelEvent(event)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.viewport_changed.emit()


class ThumbnailDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save()
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        image=index.data(Qt.ItemDataRole.DecorationRole)
        box=option.rect.adjusted(10,7,-10,-26)
        if image:
            pix=image.pixmap(QSize(130,164))
            x=box.center().x()-pix.width()/2
            y=box.center().y()-pix.height()/2
            painter.fillRect(QRectF(x+2,y+3,pix.width(),pix.height()),QColor(0,0,0,24))
            painter.drawPixmap(round(x),round(y),pix)
            painter.setPen(QPen(QColor('#1671e7') if selected else QColor('#c5c5cb'),2.5 if selected else .6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(x-2,y-2,pix.width()+4,pix.height()+4),2,2)
        else:
            painter.fillRect(box.adjusted(25,2,-25,-2),QColor('#fafafa'))
        label=option.rect.adjusted(0,option.rect.height()-25,0,-3)
        painter.setPen(QColor('#1265ca') if selected else QColor('#777780'))
        font=painter.font();font.setPointSizeF(9);font.setBold(selected);painter.setFont(font)
        painter.drawText(label,Qt.AlignmentFlag.AlignCenter,str(index.data()))
        painter.restore()


class NumberEdit(QLineEdit):
    """Compact numeric field without platform-specific spin-button chrome."""
    valueChanged=Signal(object)

    def __init__(self,parent=None):
        super().__init__(parent)
        self._minimum=0
        self._maximum=100000
        self._decimals=0
        self._value=0
        self._step=1
        self.units=QLabel(self)
        self.units.setStyleSheet('background:transparent;color:#96969e;border:0;padding:0;')
        self.units.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.editingFinished.connect(self.commit)

    def setRange(self,minimum,maximum):
        self._minimum,self._maximum=minimum,maximum
        self.setValidator(QDoubleValidator(minimum,maximum,self._decimals,self))
        self.setValue(self._value)

    def setDecimals(self,value):
        self._decimals=value
        self.setRange(self._minimum,self._maximum)

    def setSuffix(self,value):
        self.units.setText(value.strip())
        self.units.adjustSize()
        self.setTextMargins(0,0,self.units.width()+5,0)
        self.resizeEvent(None)

    def setSingleStep(self,value):
        self._step=value

    def setKeyboardTracking(self,value):
        pass

    def setButtonSymbols(self,value):
        pass

    def value(self):
        try:
            value=max(self._minimum,min(float(self.text()),self._maximum))
            return int(value) if self._decimals==0 else value
        except ValueError:
            return self._value

    def setValue(self,value):
        value=max(self._minimum,min(float(value),self._maximum))
        value=int(value) if self._decimals==0 else round(value,self._decimals)
        changed=value!=self._value
        self._value=value
        self.setText(f'{value:.{self._decimals}f}'.rstrip('0').rstrip('.') if self._decimals else str(value))
        if changed:
            self.valueChanged.emit(value)

    def commit(self):
        self.setValue(self.value())

    def resizeEvent(self,event):
        if event is not None:
            super().resizeEvent(event)
        if hasattr(self,'units'):
            self.units.move(self.width()-self.units.width()-8,(self.height()-self.units.height())//2)

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Up,Qt.Key.Key_Down):
            self.setValue(self.value()+self._step*(1 if event.key()==Qt.Key.Key_Up else -1))
        else:
            super().keyPressEvent(event)


class ChoiceCombo(QComboBox):
    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#85858f'),1.4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        x,y=self.width()-15,self.height()/2
        painter.drawLine(QPointF(x-3,y-2),QPointF(x,y+1))
        painter.drawLine(QPointF(x,y+1),QPointF(x+3,y-2))
        painter.end()


class TextDialog(QDialog):
    def __init__(self, parent, text='', title='Place text',catalog=None,style=None):
        super().__init__(parent)
        self.setWindowTitle(t(title))
        self.resize(600, 440)
        if style is None:
            from .typography import FontChoice
            style=TextStyle(FontChoice('Helvetica'))
        self.original_style=style
        self.choices=catalog.choices if catalog else [style.choice]
        self.color=QColor.fromRgbF(*style.color)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22,20,22,18)
        layout.setSpacing(14)
        heading=QLabel(t('Match the document'))
        heading.setStyleSheet('font-size:18px;font-weight:600;')
        layout.addWidget(heading)
        description=QLabel(t('Selected text style' if style.matched else
                           ('Most frequently used document style' if style.choice.count else
                            'No native font metadata · standard font fallback')))
        description.setObjectName('muted')
        layout.addWidget(description)
        row = QHBoxLayout()
        self.font_combo=ChoiceCombo()
        self.font_combo.setMinimumWidth(250)
        for n,choice in enumerate(self.choices):
            self.font_combo.addItem(choice.name+(t('  ·  most used' if choice.count else '  ·  default') if n==0 else ''),choice)
        if style.choice in self.choices:
            self.font_combo.setCurrentIndex(self.choices.index(style.choice))
        row.addWidget(self.font_combo,1)
        self.size = NumberEdit()
        self.size.setRange(3,300)
        self.size.setDecimals(2)
        self.size.setSuffix(' pt')
        self.size.setFixedWidth(100)
        self.size.setValue(style.size)
        row.addWidget(self.size)
        self.color_button=QPushButton(t('Color'))
        self.color_button.clicked.connect(self.choose_color)
        row.addWidget(self.color_button)
        layout.addLayout(row)
        self.editor = QPlainTextEdit(text)
        self.editor.setMinimumHeight(165)
        layout.addWidget(self.editor,1)
        formatting=QHBoxLayout()
        formatting.addWidget(QLabel(t('Alignment')))
        self.alignment=ChoiceCombo()
        for value in ['left','center','right']:
            self.alignment.addItem(t(value.title()),value)
        self.alignment.setCurrentIndex(max(0,self.alignment.findData(style.align)))
        formatting.addWidget(self.alignment)
        formatting.addStretch()
        formatting.addWidget(QLabel(t('Line spacing')))
        self.line_spacing=NumberEdit()
        self.line_spacing.setRange(3,1000)
        self.line_spacing.setDecimals(2)
        self.line_spacing.setSuffix(' pt')
        self.line_spacing.setValue(style.line_height)
        self.line_spacing.setFixedWidth(100)
        formatting.addWidget(self.line_spacing)
        layout.addLayout(formatting)
        self.font_note=QLabel()
        self.font_note.setWordWrap(True)
        self.font_note.setObjectName('muted')
        layout.addWidget(self.font_note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(t('Apply text'))
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName('primary')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.preview_timer=QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_preview)
        self.font_combo.currentIndexChanged.connect(self.update_preview)
        self.size.valueChanged.connect(self.size_changed)
        self.editor.textChanged.connect(lambda:self.preview_timer.start(120))
        self.update_preview()

    def size_changed(self,value):
        self.line_spacing.setValue(max(value,self.original_style.line_height*value/self.original_style.size))
        self.update_preview()

    def choose_color(self):
        value=QColorDialog.getColor(self.color,self,t('Text color'))
        if value.isValid():
            self.color=value
            self.update_preview()

    def update_preview(self,*args):
        choice=self.font_combo.currentData()
        if not choice:
            return
        font,source,substitute=choice.resolve(self.editor.toPlainText())
        family=choice.name
        if choice.buffer:
            if not hasattr(choice,'qt_families'):
                handle=QFontDatabase.addApplicationFontFromData(QByteArray(choice.buffer))
                choice.qt_families=QFontDatabase.applicationFontFamilies(handle) if handle>=0 else []
            if choice.qt_families:
                family=choice.qt_families[0]
        family={'Helvetica':'Arial','Times-Roman':'Times New Roman','Courier':'Courier New'}.get(family,family)
        preview=QFont(family)
        preview.setPointSizeF(self.size.value())
        preview.setBold(bool(choice.flags & 16))
        preview.setItalic(bool(choice.flags & 2))
        self.editor.setFont(preview)
        self.editor.setStyleSheet(f'QPlainTextEdit {{color:{self.color.name()};padding:12px;}}')
        self.color_button.setStyleSheet(f'color:{self.color.name()};')
        self.font_note.setText(t(source+'. Font choice, size, color and spacing apply to this text box.'))

    def selected_style(self):
        return replace_style(self.original_style,choice=self.font_combo.currentData(),
                             size=self.size.value(),color=(self.color.redF(),self.color.greenF(),self.color.blueF()),
                             line_height=self.line_spacing.value(),align=self.alignment.currentData())


class Window(ObjectWindowMixin,QMainWindow):
    def __init__(self,language_manager=None,signature_store=None):
        super().__init__()
        self.language_manager=language_manager if language_manager is not None else LanguageManager()
        activate(self.language_manager.current)
        self.resize(1280, 880)
        self.setMinimumSize(960, 640)
        self.setWindowTitle(t('Paperlight'))
        self.session = None
        self.inline_text = None
        self.ocr_apply_requested = False
        self.page_index = 0
        self.zoom = 1.0
        self.fit_mode = True
        self.password = ''
        self.signature_path = ''
        self.signature_store = signature_store if signature_store is not None else SignatureStore()
        self.signature_stamp = None
        self.drawn_signature_strokes = []
        self.drawn_signature_page = None
        self.continuous = self.language_manager.settings.value('view/pageMode','single') == 'continuous'
        self.rendering = False
        self.records = {}
        self.current_key = None
        self.session_keys = set()
        self.job = None
        self.job_buffer = b''
        self.job_failed = False
        self.ocr_complete = False
        self.job_temp = None
        self.cache_root = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)) / 'search-v4'
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.legacy_cache_warning = False
        legacy_cache = self.cache_root.parent/'search-v3'
        if legacy_cache.exists():
            try:
                if legacy_cache.resolve().parent!=self.cache_root.parent.resolve() or legacy_cache.is_symlink():
                    raise OSError('Legacy cache path is not an owned directory.')
                shutil.rmtree(legacy_cache)
            except OSError:
                self.legacy_cache_warning = True
        self.loaded_thumbs = set()
        self.rebuilding = False
        self.search_hits = []
        self.document_actions = []
        self.build_ui()
        self.edit_controller=EditController(self)
        self.language_manager.changed.connect(self.apply_language)
        self.apply_language(self.language_manager.current)
        self.thumbnail_timer = QTimer(self)
        self.thumbnail_timer.timeout.connect(self.load_visible_thumbnails)
        self.thumbnail_timer.start(90)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.begin_search)
        self.search_step = QTimer(self)
        self.search_step.timeout.connect(self.search_chunk)
        self.job_watchdog = QTimer(self)
        self.job_watchdog.setSingleShot(True)
        self.job_watchdog.timeout.connect(self.index_timeout)
        self.update_actions()
        self.setAcceptDrops(True)
        if self.legacy_cache_warning:
            self.status.setText(t('Old search caches could not be removed. Clear local search cache before processing sensitive documents.'))
        if self.signature_store.path.exists():
            try:
                self.signature_store.load()
            except (OSError,ValueError,TypeError,KeyError):
                self.status.setText(t('Saved signatures could not be protected. Review the signature library before use.'))

    def action(self, text, slot, shortcut=None, document=True, view=False):
        action = QAction(t(text), self)
        action.setProperty('view', view)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(shortcut)
        if document:
            self.document_actions.append(action)
        return action

    def build_ui(self):
        file_menu = self.menuBar().addMenu(t('&File'))
        edit_menu = self.menuBar().addMenu(t('&Edit'))
        view_menu = self.menuBar().addMenu(t('&View'))
        page_menu = self.menuBar().addMenu(t('&Pages'))
        tools_menu = self.menuBar().addMenu(t('&Tools'))
        help_menu = self.menuBar().addMenu(t('&Help'))
        self.view_group = QActionGroup(self)
        self.view_actions = {}
        for mode,label in [('single','Single page'),('continuous','Continuous scroll')]:
            action = self.action(t(label), lambda checked=False,m=mode:self.set_page_mode(m), document=False)
            action.setCheckable(True)
            action.setChecked(self.continuous == (mode=='continuous'))
            self.view_group.addAction(action)
            self.view_actions[mode] = action
            view_menu.addAction(action)
        toolbar = QToolBar(t('Document'))
        toolbar.setIconSize(QSize(21,21))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        def control(bar,action,symbol,label=False):
            action.setIcon(icon(symbol))
            bar.addAction(action)
            if label:
                bar.widgetForAction(action).setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            return action
        sidebar=self.action(t('Show or hide sidebar'),lambda:self.tabs.setVisible(not self.tabs.isVisible()),'Ctrl+Shift+L',False)
        control(toolbar,sidebar,'sidebar')
        toolbar.addSeparator()
        open_action = self.action(t('Open PDF'), self.open_dialog, 'Ctrl+O', False)
        self.save_action = self.action(t('Save'), self.save_current, QKeySequence.StandardKey.Save)
        save_copy_action = self.action(t('Save copy'), self.save_copy, 'Ctrl+Shift+S')
        control(toolbar,open_action,'open')
        control(toolbar,self.save_action,'save')
        file_menu.addActions([open_action, self.save_action, save_copy_action])
        self.export_action = self.action(t('Export searchable copy'), self.export_searchable)
        file_menu.addAction(self.export_action)
        self.protect_action = self.action(t('Protect PDF…'), self.protect_pdf)
        self.unlock_action = self.action(t('Unlock editing…'), self.unlock_editing, view=True)
        file_menu.addActions([self.protect_action, self.unlock_action])
        toolbar.addSeparator()
        self.undo_action = self.action(t('Undo'), self.undo, QKeySequence.StandardKey.Undo)
        self.redo_action = self.action(t('Redo'), self.redo, QKeySequence.StandardKey.Redo)
        edit_menu.addActions([self.undo_action,self.redo_action])
        self.copy_action=self.action(t('Copy selected text'),self.copy_selection,QKeySequence.StandardKey.Copy,view=True)
        self.select_all_action=self.action(t('Select all text on page'),self.select_all_text,QKeySequence.StandardKey.SelectAll,view=True)
        self.clear_selection_action=self.action(t('Clear text selection'),lambda:self.canvas.select_range(0,0),view=True)
        for a in (self.copy_action,self.select_all_action):
            a.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        edit_menu.addSeparator()
        edit_menu.addActions([self.copy_action,self.select_all_action,self.clear_selection_action])
        title_panel=QWidget()
        title_panel.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        title_layout=QVBoxLayout(title_panel)
        title_layout.setContentsMargins(15,0,15,0)
        title_layout.setSpacing(1)
        self.document_label=QLabel(t('Paperlight'))
        self.document_label.setProperty('i18n_ignore',True)
        self.document_label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.document_label.setStyleSheet('font-weight:600;font-size:13px;')
        self.document_detail=QLabel(t('PDF workspace'))
        self.document_detail.setStyleSheet('color:#90909a;font-size:10px;')
        title_layout.addWidget(self.document_label)
        title_layout.addWidget(self.document_detail)
        toolbar.addWidget(title_panel)
        self.index_action = self.action(t('Recognize text'), self.recognize_document, view=True)
        tools_menu.addAction(self.index_action)
        self.toolbox_action=self.action(t('PDF tools'),self.open_toolbox,'Ctrl+Shift+P',document=False)
        tools_menu.addAction(self.toolbox_action)
        control(toolbar,self.toolbox_action,'form',True)
        self.stop_action = self.action(t('Stop OCR'), self.stop_index)
        tools_menu.addAction(self.stop_action)
        tools_menu.addAction(self.action(t('Clear local search cache'), self.clear_cache, document=False))
        self.remember_cache_action = self.action(t('Remember encrypted search cache'),self.set_remember_cache,document=False)
        self.remember_cache_action.setCheckable(True)
        self.remember_cache_action.setChecked(self.language_manager.settings.value('privacy/rememberCache',False,type=bool))
        self.remember_cache_action.setToolTip(t('Session-only by default. Enable to reuse encrypted indexes between sessions. Password-protected PDFs always use session-only indexes.'))
        tools_menu.addAction(self.remember_cache_action)
        find_action = self.action(t('Find'), self.focus_find, 'Ctrl+F', view=True)
        edit_menu.addAction(find_action)
        self.prev_action = self.action(t('‹'), lambda: self.go_page(self.page_index-1), 'Alt+Left', view=True)
        self.next_action = self.action(t('›'), lambda: self.go_page(self.page_index+1), 'Alt+Right', view=True)
        self.prev_action.setToolTip(t('Previous page · Alt+Left'))
        self.next_action.setToolTip(t('Next page · Alt+Right'))
        control(toolbar,self.prev_action,'previous')
        self.page_number = NumberEdit()
        self.page_number.setRange(1,1)
        self.page_number.setFixedWidth(48)
        self.page_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_number.setToolTip(t('Go to page'))
        self.page_number.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.page_number.setKeyboardTracking(False)
        self.page_number.valueChanged.connect(lambda n: self.go_page(n-1))
        toolbar.addWidget(self.page_number)
        self.page_total = QLabel(t('/ 0'))
        toolbar.addWidget(self.page_total)
        control(toolbar,self.next_action,'next')
        toolbar.addSeparator()
        control(toolbar,self.action(t('Zoom out'),lambda:self.change_zoom(-1),'Ctrl+-',view=True),'minus')
        self.zoom_label = QLabel(t('100%'))
        self.zoom_label.setMinimumWidth(42)
        toolbar.addWidget(self.zoom_label)
        control(toolbar,self.action(t('Zoom in'),lambda:self.change_zoom(1),'Ctrl+=',view=True),'plus')
        self.fit_action=self.action(t('Fit page'), self.fit_page, 'Ctrl+0',view=True)
        control(toolbar,self.fit_action,'fit')
        toolbar.addSeparator()
        control(toolbar,find_action,'search')
        control(toolbar,self.index_action,'ocr')

        self.addToolBarBreak()
        markup = QToolBar(t('Markup'))
        self.markup_bar=markup
        markup.setObjectName('markupBar')
        markup.setIconSize(QSize(20,20))
        markup.setMovable(False)
        self.basic_bar = QToolBar(t('Edit'))
        self.basic_bar.setMovable(False)
        self.basic_bar.setIconSize(QSize(20,20))
        self.addToolBar(self.basic_bar)
        self.tool_group = QActionGroup(self)
        self.tool_actions = {}
        tools = [('edit','Edit PDF'),('read','Read'),('select','Select text'),('draw','Draw / sign'),('text','Add text'),
                 ('correct','Correct text'),('signature','Saved signature'),('image','Signature image'),
                 ('form','Fill form'),('redact','Redact')]
        for mode, label in tools:
            a = QAction(t(label),self)
            a.setProperty('view', mode in ('read', 'select'))
            a.setCheckable(True)
            a.triggered.connect(lambda checked=False,m=mode:self.choose_tool(m))
            self.tool_group.addAction(a)
            control(self.basic_bar,a,mode,mode=='edit')
            self.tool_actions[mode]=a
            self.document_actions.append(a)
        tools_menu.addAction(self.tool_actions['signature'])
        tools_menu.addAction(self.action(t('Create / manage signatures…'),self.open_signature_manager,document=False))
        self.capture_signature_action = self.action(t('Save current drawing as signature…'),self.capture_drawn_signature)
        tools_menu.addAction(self.capture_signature_action)
        self.tool_actions['read'].setChecked(True)
        self.tool_actions['select'].setShortcut('Ctrl+Shift+T')
        edit_menu.addAction(self.tool_actions['select'])
        self.basic_bar.addSeparator()
        self.color_button = QPushButton(t('●'))
        self.color_button.setFixedWidth(34)
        self.color_button.setStyleSheet('color:#245fae;font-size:18px;padding:0;')
        self.color_button.setToolTip(t('Ink color'))
        self.color_button.clicked.connect(self.pick_color)
        self.basic_bar.addWidget(self.color_button)
        self.pen_width = NumberEdit()
        self.pen_width.setDecimals(1)
        self.pen_width.setRange(.5,12)
        self.pen_width.setSingleStep(.5)
        self.pen_width.setValue(2)
        self.pen_width.setSuffix(' pt')
        self.pen_width.setFixedWidth(80)
        self.pen_width.setToolTip(t('Stroke width'))
        self.basic_bar.addWidget(self.pen_width)
        self.apply_action = self.action(t('Apply redactions'),self.apply_redactions)
        self.basic_bar.addSeparator()
        control(self.basic_bar,self.undo_action,'undo')
        control(self.basic_bar,self.redo_action,'redo')
        control(self.basic_bar,self.apply_action,'redact',True)
        tools_menu.addAction(self.apply_action)
        spacer=QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        self.basic_bar.addWidget(spacer)
        self.active_tool_label=QLabel(t('Read'))
        self.active_tool_label.setFixedWidth(135)
        self.active_tool_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.active_tool_label.setStyleSheet('color:#82828c;padding:0 10px;')
        self.basic_bar.addWidget(self.active_tool_label)
        markup.hide()

        for title, slot, key in [('Rotate right',self.rotate,'Ctrl+R'),
                                 ('Move page earlier',lambda:self.move_page(-1),None),
                                 ('Move page later',lambda:self.move_page(1),None),
                                 ('Delete selected pages',self.delete_pages,None),
                                 ('Extract / split pages',self.split_pages,None),
                                 ('Insert / merge PDF',self.merge_pdf,None)]:
            page_menu.addAction(self.action(t(title),slot,key))
        help_menu.addAction(self.action(t('Quick guide'),self.guide, document=False))
        help_menu.addAction(self.action(t('About Paperlight'),self.about, document=False))
        help_menu.addSeparator()
        self.language_menu=help_menu.addMenu(t('Language / 语言'))
        self.language_menu.menuAction().setProperty('i18n_ignore',True)
        self.language_group=QActionGroup(self)
        self.language_actions={}
        for code,label in [('en','English'),('zh_CN','简体中文')]:
            action=QAction(t(label),self)
            action.setProperty('i18n_ignore',True)
            action.setCheckable(True)
            action.setChecked(self.language_manager.current==code)
            action.triggered.connect(lambda checked=False,code=code:self.language_manager.set_language(code))
            self.language_group.addAction(action)
            self.language_menu.addAction(action)
            self.language_actions[code]=action

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.splitter = QSplitter()
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(180)
        self.pages = QListWidget()
        self.pages.setIconSize(QSize(130,164))
        self.pages.setItemDelegate(ThumbnailDelegate(self.pages))
        self.pages.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.pages.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.pages.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.pages.setMovement(QListWidget.Movement.Snap)
        self.pages.currentRowChanged.connect(self.thumbnail_chosen)
        self.pages.model().rowsMoved.connect(lambda *args:QTimer.singleShot(0,self.pages_reordered))
        self.pages.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        for a in page_menu.actions():
            self.pages.addAction(a)
        self.tabs.addTab(self.pages,t('Thumbnails'))
        search_panel = QWidget()
        search_layout = QVBoxLayout(search_panel)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(t('Find text in this PDF'))
        self.search_box.textChanged.connect(lambda:self.search_timer.start(180))
        search_layout.addWidget(self.search_box)
        self.search_status = QLabel(t('Open a PDF to search.'))
        self.search_status.setWordWrap(True)
        self.search_status.setObjectName('muted')
        search_layout.addWidget(self.search_status)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.currentItemChanged.connect(self.result_chosen)
        search_layout.addWidget(self.results)
        self.tabs.addTab(search_panel,t('Search'))
        self.splitter.addWidget(self.tabs)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0,0,0,0)
        content_layout.setSpacing(0)
        self.canvas = Canvas()
        self.canvas.gesture.connect(self.handle_gesture)
        self.canvas.clicked.connect(self.fill_form)
        self.canvas.remove_at.connect(self.remove_annotation)
        self.canvas.zoom_request.connect(self.change_zoom)
        self.canvas.page_activated.connect(self.continuous_page_changed)
        self.canvas.selection_changed.connect(self.selection_updated)
        self.canvas.selection_menu.connect(self.show_selection_menu)
        self.canvas.commit_draft=self.commit_inline_text
        self.canvas.object_chosen.connect(self.choose_object)
        self.canvas.object_changed.connect(self.transform_object)
        self.canvas.object_menu.connect(self.object_context_menu)
        self.canvas.object_deleted.connect(self.delete_selected_object)
        self.canvas.preview_requested.connect(lambda obj:self.edit_controller.preview(obj))
        self.canvas.edit_refresh_requested.connect(lambda:QTimer.singleShot(0,self.update_page_objects))
        self.canvas.text_clicked.connect(self.start_inline_text)
        self.canvas.verticalScrollBar().valueChanged.connect(self.position_inline_text)
        self.canvas.horizontalScrollBar().valueChanged.connect(self.position_inline_text)
        self.canvas.addActions([self.copy_action,self.select_all_action])
        self.canvas.viewport_changed.connect(lambda:QTimer.singleShot(0,lambda:self.render(self.continuous)) if self.session and self.fit_mode else None)
        content_layout.addWidget(self.canvas,1)
        self.welcome = QWidget()
        welcome_layout = QVBoxLayout(self.welcome)
        welcome_layout.addStretch()
        welcome_icon=QLabel()
        welcome_icon.setPixmap(QIcon(str(Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'/'paperlight.ico')).pixmap(64,64))
        welcome_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(welcome_icon)
        welcome_title = QLabel(t('Paperlight'))
        welcome_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_title.setStyleSheet('font-size:25px;font-weight:600;color:#34343b;padding-top:12px;')
        welcome_layout.addWidget(welcome_title)
        welcome_subtitle = QLabel(t('Read, mark up, organize and search PDFs.\nEnglish and Chinese OCR works offline.'))
        welcome_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_subtitle.setStyleSheet('font-size:13px;color:#898994;padding:10px;')
        welcome_layout.addWidget(welcome_subtitle)
        open_button = QPushButton(t('Open a PDF'))
        open_button.setObjectName('primary')
        open_button.clicked.connect(self.open_dialog)
        welcome_layout.addWidget(open_button,0,Qt.AlignmentFlag.AlignCenter)
        drop_label = QLabel(t('or drop a PDF here'))
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_label.setStyleSheet('color:#7a8794;padding:14px;')
        welcome_layout.addWidget(drop_label)
        welcome_layout.addStretch()
        content_layout.addWidget(self.welcome,1)
        self.canvas.hide()
        self.splitter.addWidget(self.content)
        self.splitter.setSizes([205,1075])
        self.splitter.setStretchFactor(1,1)
        layout.addWidget(self.splitter)
        self.setCentralWidget(central)
        self.status = QLabel(t('Open a PDF to get started'))
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.statusBar().addWidget(self.status,1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(130)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        self.offline_label = QLabel(t('On your computer  ·  Offline'))
        self.offline_label.setObjectName('muted')
        self.statusBar().addPermanentWidget(self.offline_label)
        for label in self.findChildren(QLabel):
            label.setTextFormat(Qt.TextFormat.PlainText)

    def apply_language(self,language):
        # Translate UI controls only. Editors, clipboard contents, font families,
        # document titles, field values and search excerpts are never traversed.
        for action in self.findChildren(QAction):
            if not action.property('i18n_ignore'):
                action.setText(t(action.text(),language))
                action.setToolTip(t(action.toolTip(),language))
        for label in self.findChildren(QLabel):
            if not label.property('i18n_ignore'):
                label.setText(t(label.text(),language))
        for button in self.findChildren(QPushButton):
            button.setText(t(button.text(),language))
            button.setToolTip(t(button.toolTip(),language))
        for field in self.findChildren(QLineEdit):
            field.setPlaceholderText(t(field.placeholderText(),language))
            field.setToolTip(t(field.toolTip(),language))
        for bar in self.findChildren(QToolBar):
            bar.setWindowTitle(t(bar.windowTitle(),language))
        for n in range(self.tabs.count()):
            self.tabs.setTabText(n,t(self.tabs.tabText(n),language))
        for n in range(self.pages.count()):
            item=self.pages.item(n)
            item.setText(t(item.text(),language))
        for n in range(self.results.count()):
            item=self.results.item(n)
            item.setText(t(item.text(),language))
        for code,action in self.language_actions.items():
            action.setChecked(code==language)
        self.active_tool_label.setText(self.tool_actions[self.canvas.mode].text())
        self.document_detail.setStyleSheet('color:#90909a;font-size:12px;' if language=='zh_CN' else 'color:#90909a;font-size:11px;')

    def error(self, exc):
        box = QMessageBox(self)
        box.setWindowTitle(t('Paperlight'))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(t(str(exc)))
        box.exec()

    def guard(self, fn):
        try:
            return fn()
        except Exception as exc:
            self.error(exc)
            return None

    def update_actions(self):
        active = self.session is not None
        self.fit_action.setText(t('Fit width' if self.continuous else 'Fit page'))
        editable = active and not self.session.readonly
        for action in self.document_actions:
            action.setEnabled(active and (editable or bool(action.property('view'))))
        self.unlock_action.setEnabled(active and self.session.readonly)
        draft=False
        if self.inline_text:
            box=self.inline_text
            draft=(box.editor.toPlainText()!=box.original_text or box.rect!=box.original_rect or getattr(box,'format_modified',False)) if hasattr(box,'pdf_object') else bool(box.editor.toPlainText().strip())
        self.save_action.setEnabled(editable and (self.session.dirty or draft))
        self.capture_signature_action.setEnabled(editable and bool(self.drawn_signature_strokes) and self.drawn_signature_page==(id(self.session),self.page_index))
        self.pages.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove if editable else QAbstractItemView.DragDropMode.NoDragDrop)
        if active:
            can = self.session.can_do()
            self.undo_action.setEnabled(editable and can['undo'])
            self.redo_action.setEnabled(editable and can['redo'])
            self.prev_action.setEnabled(self.page_index>0)
            self.next_action.setEnabled(self.page_index<len(self.session.doc)-1)
            self.apply_action.setEnabled(editable and bool(self.session.pending_redactions()))
        self.stop_action.setEnabled(self.job is not None)
        self.page_number.setEnabled(active)
        self.export_action.setEnabled(editable and bool(self.records))
        self.copy_action.setEnabled(active and self.session.copy_allowed and bool(self.canvas.selected_text))
        self.clear_selection_action.setEnabled(active and bool(self.canvas.selected_text))
        if active:
            star = ' *' if self.session.dirty or draft else ''
            security_label = ' · ' + t('Read-only') if self.session.readonly else ''
            self.setWindowTitle(f'{Path(self.session.path).name}{star}{security_label} · Paperlight')

    def confirm_discard(self):
        if not self.commit_inline_text():
            return False
        if self.session and self.session.dirty:
            answer = QMessageBox.question(self,t('Unsaved changes'),t('Save changes to this document before continuing?'),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Save:
                return self.save_current()
        return True

    def open_dialog(self):
        path,_ = QFileDialog.getOpenFileName(self,t('Open PDF'),'',t('PDF documents (*.pdf)'))
        if path:
            self.open_path(path)

    def open_path(self,path):
        if not self.confirm_discard():
            return
        password = ''
        try:
            with fitz.open(path) as check:
                if check.needs_pass:
                    password,ok = QInputDialog.getText(self,t('Password'),t('PDF password'),QLineEdit.EchoMode.Password)
                    if not ok:
                        return
            candidate = PdfSession(path,password)
        except Exception as exc:
            self.error(exc)
            return
        self.stop_index()
        self.edit_controller.stop()
        if self.session:
            self.session.close()
        self.session = candidate
        self.drawn_signature_strokes = []
        self.drawn_signature_page = None
        self.password = password
        self.records = {}
        self.session_keys = set()
        self.current_key = None
        self.page_index = 0
        self.fit_mode = True
        self.ocr_complete = False
        self.search_hits = []
        self.results.clear()
        self.welcome.hide()
        self.canvas.show()
        self.document_label.setText(f'  {Path(path).name}')
        self.refresh_pages()
        self.render()
        self.choose_tool('read')
        self.status.setText(t('Read with the hand tool. Choose a markup tool to edit.'))
        if self.session.readonly:
            self.status.setText(t('Read-only PDF. Use File > Unlock editing with the owner password.'))
        self.start_index(False)

    def refresh_pages(self):
        self.rebuilding = True
        self.pages.clear()
        self.loaded_thumbs.clear()
        for n in range(len(self.session.doc)):
            item=QListWidgetItem(t(f'Page {n+1}'))
            item.setData(Qt.ItemDataRole.UserRole,n)
            item.setSizeHint(QSize(165,204))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self.pages.addItem(item)
        self.page_index = max(0,min(self.page_index,len(self.session.doc)-1))
        self.pages.setCurrentRow(self.page_index)
        self.page_number.blockSignals(True)
        self.page_number.setRange(1,len(self.session.doc))
        self.page_number.setValue(self.page_index+1)
        self.page_number.blockSignals(False)
        self.page_total.setText(f'/ {len(self.session.doc)}')
        self.rebuilding = False

    def load_visible_thumbnails(self):
        if not self.session or self.tabs.currentIndex()!=0 or self.rebuilding:
            return
        loaded=0
        for n in range(self.pages.count()):
            if n in self.loaded_thumbs:
                continue
            item=self.pages.item(n)
            if not self.pages.visualItemRect(item).intersects(self.pages.viewport().rect()):
                continue
            try:
                page=self.session.doc[n]
                item.setIcon(QIcon(pixmap_from_page(page,min(130/page.rect.width,164/page.rect.height))))
                self.loaded_thumbs.add(n)
            except Exception:
                self.loaded_thumbs.add(n)
            loaded+=1
            if loaded>=3:
                break

    def render(self,keep_scroll=False):
        if not self.session or self.session.doc.is_closed or self.rendering:
            return
        self.rendering = True
        page=self.session.doc[self.page_index]
        if self.fit_mode:
            if self.continuous:
                geometry_key = (id(self.session.doc),self.session.position,self.session._revision)
                if getattr(self,'geometry_key',None) != geometry_key:
                    self.geometry_key = geometry_key
                    self.document_width = max(p.rect.width for p in self.session.doc)
                self.zoom = max(.15,min((self.canvas.viewport().width()-88)/self.document_width,3))
            else:
                self.zoom=max(.15,min((self.canvas.viewport().width()-88)/page.rect.width,
                                      (self.canvas.viewport().height()-72)/page.rect.height,3))
        # Bound raster memory for huge page dimensions and extreme zoom.
        scale=self.zoom if self.continuous else min(self.zoom,4096/max(page.rect.width,page.rect.height))
        scroll=self.canvas.verticalScrollBar().value()
        old_height = self.canvas.sceneRect().height()
        try:
            if self.continuous:
                key=(id(self.session),id(self.session.doc),self.session.position,self.session._revision,scale)
                self.canvas.show_document(self.session.doc,scale,key,self.page_index)
            else:
                self.canvas.show_page(page,scale)
            self.canvas.set_text_model(PageText.from_page(page,self.records.get(self.page_index,{}).get('words',[])),
                                       (id(self.session),self.page_index,self.session.position))
            self.zoom_label.setText(f'{round(scale*100)}%')
            self.document_detail.setText(t(f'Page {self.page_index+1} of {len(self.session.doc)}'))
            self.highlight_page()
            if self.continuous:
                if keep_scroll:
                    self.canvas.verticalScrollBar().setValue(round(scroll*self.canvas.sceneRect().height()/max(1,old_height)))
                else:
                    self.canvas.scroll_to_page(self.page_index)
            else:
                self.canvas.verticalScrollBar().setValue(scroll if keep_scroll else 0)
            self.page_number.blockSignals(True)
            self.page_number.setValue(self.page_index+1)
            self.page_number.blockSignals(False)
            self.update_actions()
        except Exception as exc:
            self.error(exc)
        finally:
            self.rendering = False
            self.position_inline_text()
            if self.canvas.mode=='edit':self.page_object_key=None
            self.update_page_objects()

    def set_page_mode(self, mode):
        self.continuous = mode == 'continuous'
        self.language_manager.settings.setValue('view/pageMode',mode)
        self.language_manager.settings.sync()
        self.view_actions[mode].setChecked(True)
        self.fit_mode = True
        self.update_actions()
        self.render()

    def continuous_page_changed(self, index):
        if self.rendering or not self.session or not self.continuous:
            return
        self.page_index = index
        self.pages.blockSignals(True)
        self.pages.setCurrentRow(index)
        self.pages.scrollToItem(self.pages.item(index))
        self.pages.blockSignals(False)
        self.render(True)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'canvas') and self.session and self.fit_mode:
            QTimer.singleShot(0,lambda:self.render(self.continuous))

    def go_page(self,n):
        if n!=self.page_index and not self.commit_inline_text():
            return
        if not self.session or not 0<=n<len(self.session.doc):
            return
        self.page_index=n
        self.pages.blockSignals(True)
        self.pages.setCurrentRow(n)
        self.pages.scrollToItem(self.pages.item(n))
        self.pages.blockSignals(False)
        self.render()
        self.ensure_edit_ocr()

    def thumbnail_chosen(self,n):
        if not self.rebuilding and n>=0:
            self.go_page(n)

    def change_zoom(self,direction):
        if self.session:
            self.fit_mode=False
            self.zoom=max(.15,min(4,self.zoom*(1.2 if direction>0 else 1/1.2)))
            self.render(True)

    def fit_page(self):
        self.fit_mode=True
        self.render()

    def choose_tool(self,mode,prompt=True):
        if not self.commit_inline_text():
            self.tool_actions[self.canvas.mode].setChecked(True)
            return
        if self.session and self.session.readonly and mode not in ('read', 'select'):
            return
        if mode=='draw' and self.canvas.mode!='draw':
            self.drawn_signature_strokes = []
            self.drawn_signature_page = None
            self.update_actions()
        if mode=='signature' and prompt:
            if not self.manage_signatures():
                self.tool_actions[self.canvas.mode].setChecked(True)
                return
        if mode=='image':
            path,_=QFileDialog.getOpenFileName(self,t('Choose signature image'),'',t('Images (*.png *.jpg *.jpeg *.bmp *.webp)'))
            if not path:
                self.tool_actions[self.canvas.mode].setChecked(True)
                return
            self.signature_path=path
        self.canvas.set_mode(mode)
        if mode=='select':
            self.canvas.setFocus()
        self.tool_actions[mode].setChecked(True)
        self.active_tool_label.setText(self.tool_actions[mode].text())
        self.update_page_objects()
        if mode=='edit': self.ensure_edit_ocr()
        hints={'edit':'Click to select a text box, shape or image. Drag to move; drag a corner to resize. Double-click text to type. Only this page is analyzed.',
               'read':'Drag text to select; drag blank space to pan.',
               'signature':"Drag a box to place your saved signature. Today's date is added if selected.",
               'select':'Drag across text to select. Ctrl+C copies. Double-click selects a word. Ctrl+A selects this page.',
               'draw':'Draw with the mouse. Use this tool for a handwritten signature.',
               'text':'Click to create a text box. Type on the page; use the three dots to format.',
               'correct':'Drag a box around the word or paragraph to replace. Scan pixels inside it will be removed.',
               'image':'Drag a box for the signature image.',
               'form':'Click an existing form field. Use Add text for a paper form.',
               'redact':'Drag over sensitive content, then choose Apply redactions.'}
        self.status.setText(t(hints[mode]))

    def start_inline_text(self, point):
        if not self.session or self.session.readonly or not self.commit_inline_text():
            return
        self.stop_index()
        page=self.session.doc[self.page_index]
        display_point=point*page.rotation_matrix
        bounds=page.rect
        width=min(260,bounds.x1-display_point.x)
        height=min(100,bounds.y1-display_point.y)
        if width<30 or height<25:
            self.status.setText(t('Click farther from the page edge to add text.'))
            return
        catalog=self.session.font_catalog()
        style=replace_style(catalog.style(self.page_index),rotation=page.rotation,anchor=None)
        rect=fitz.Rect(display_point.x,display_point.y,display_point.x+width,display_point.y+height)*page.derotation_matrix
        self.inline_text=InlineTextBox(self.canvas,rect,catalog,style)
        self.inline_text.page_index=self.page_index
        self.inline_text.commit_requested.connect(self.commit_inline_text)
        self.inline_text.cancel_requested.connect(self.cancel_inline_text)
        self.inline_text.editor.textChanged.connect(self.update_actions)
        self.inline_text.draft_changed.connect(self.update_actions)
        self.status.setText(t('Type on the page. Three dots: formatting. Done or Ctrl+Enter: apply. Escape: cancel.'))

    def position_inline_text(self,*args):
        if self.inline_text is not None:
            self.inline_text.update_layout()

    def cancel_inline_text(self):
        box=self.inline_text
        self.inline_text=None
        self.canvas.text_draft_identity=None
        if self.canvas.mode=='edit':self.canvas.apply_preview_transform(fitz.Identity)
        if box:
            box.hide()
            box.deleteLater()
        self.canvas.setFocus()
        self.update_actions()

    def commit_inline_text(self):
        box=self.inline_text
        if box is None:
            return True
        value=box.editor.toPlainText()
        if hasattr(box,'pdf_object'):
            obj=box.pdf_object
            unchanged=(value==box.original_text and box.rect==box.original_rect and not getattr(box,'format_modified',False))
            if unchanged:
                self.cancel_inline_text();return True
            self.inline_text=None
            page_index=self.page_index;self.page_index=box.page_index
            try:
                from .richtext import layout
                runs=layout(box) if box.rich and value else []
                success=self.mutate(lambda:self.session.object_text(box.page_index,obj,box.rect,runs=runs,text=value,style=box.style),purge=obj.kind in ('text','ocr'),preserve=True,drop_rect=fitz.Rect(obj.rect))
            except Exception as exc:
                self.error(exc);success=False
            self.page_index=page_index
            if success:
                self.canvas.text_draft_identity=None;box.hide();box.deleteLater();self.render(True)
            else: self.inline_text=box;box.editor.setFocus();self.update_actions()
            return success
        if not value.strip():
            self.cancel_inline_text()
            return True
        self.inline_text=None
        # Commit on its original page even if continuous scrolling activated another.
        page_index=self.page_index
        self.page_index=box.page_index
        success=self.mutate(lambda:self.session.text(box.page_index,box.rect,value,replace=box.replacement,style=box.style),purge=box.replacement,preserve=True,drop_rect=box.rect if box.replacement else None)
        self.page_index=page_index
        if success:
            box.hide()
            box.deleteLater()
            self.render(True)
        else:
            self.inline_text=box
            box.editor.setFocus()
        return success

    def recognize_document(self):
        self.start_index(True,apply_ocr=True)

    def apply_recognized_text(self):
        if not self.session:
            return
        if self.session.readonly:
            self.status.setText(t('OCR is selectable for reading. Unlock editing to add the text layer to this PDF.'))
            return
        records=self.records
        converted=[]
        def convert():
            with self.session.operation('Recognize scan text'):
                for n,row in sorted(records.items()):
                    page=self.session.doc[n]
                    native=[fitz.Rect(w[:4]) for w in page.get_text('words')]
                    words=[w for w in row['words'] if w.get('source')=='ocr' and not any(
                        (fitz.Rect(w['rect']) & r).get_area()>fitz.Rect(w['rect']).get_area()*.45 for r in native)]
                    if words:
                        insert_ocr_words(page,words)
                        converted.append(n)
        if not any(w.get('source')=='ocr' for row in records.values() for w in row['words']):
            self.status.setText(t('No new scan text found. Existing text remains selectable; unreadable scans may need another OCR pass.'))
            return
        if self.mutate(convert):
            self.records={n:dict(page=n,words=word_rows(self.session.doc[n]),ocr=False,complete=row['complete']) for n,row in records.items()}
            self.ocr_complete=all(row['complete'] for row in self.records.values())
            self.render(True)
            self.begin_search()
            self.status.setText(t('OCR text added. Select or copy it, or use Correct text to replace scan text. Save to keep the text layer.'))

    def manage_signatures(self,initial_signature=None):
        dialog = SignatureDialog(self,self.signature_store,self.language_manager.settings,initial_signature=initial_signature)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.signature_stamp = dialog.stamp()
            return True
        return False

    def open_signature_manager(self,initial_signature=None):
        if self.manage_signatures(initial_signature) and self.session and not self.session.readonly:
            self.choose_tool('signature',prompt=False)

    def capture_drawn_signature(self):
        if self.drawn_signature_strokes:
            self.open_signature_manager(normalize_strokes(self.drawn_signature_strokes))

    def selection_updated(self,text):
        self.copy_action.setEnabled(bool(text) and bool(self.session) and self.session.copy_allowed)
        self.clear_selection_action.setEnabled(bool(text))
        if self.canvas.mode in ('read','select'):
            if text:
                self.status.setText(t(f'{len(text)} characters selected · Ctrl+C to copy'))
            elif not self.canvas.text_model.units:
                self.status.setText(t('No selectable text on this page. Choose Recognize text to read a scan.'))
            else:
                self.status.setText(t('Drag across text to select. Ctrl+C copies. Double-click selects a word.'))

    def copy_selection(self):
        if self.session and self.session.copy_allowed and self.canvas.selected_text:
            QApplication.clipboard().setText(self.canvas.selected_text)
            self.status.setText(t(f'Copied {len(self.canvas.selected_text)} characters'))

    def select_all_text(self):
        if self.session:
            self.choose_tool('select')
            self.canvas.setFocus()
            self.canvas.select_range(0,len(self.canvas.text_model.units))

    def show_selection_menu(self,position):
        menu=QMenu(self)
        menu.addActions([self.copy_action,self.select_all_action,self.clear_selection_action])
        menu.exec(position)

    def open_toolbox(self):
        from .toolbox import ToolboxDialog
        if not self.commit_inline_text():return
        self.stop_index();self.edit_controller.stop()
        dialog=ToolboxDialog(self);dialog.exec()
        self.page_object_key=None;self.update_page_objects()

    def pick_color(self):
        color=QColorDialog.getColor(self.canvas.pen_color,self,t('Ink color'))
        if color.isValid():
            self.canvas.pen_color=color
            self.color_button.setStyleSheet(f'color:{color.name()};font-weight:600;')

    def mutate(self,fn,pages_changed=False, purge=False, preserve=False, drop_rect=None):
        if self.edit_controller.busy:self.edit_controller.stop()
        self.canvas.clear_edit_preview()
        if not self.commit_inline_text():
            return False
        self.stop_index()
        previous=self.records
        old_complete=self.ocr_complete
        try:
            fn()
        except Exception as exc:
            self.error(exc)
            self.render(True)
            return False
        self.invalidate_search(purge)
        if preserve and previous:
            # Geometry is unchanged by markup and form edits. Keep expensive OCR
            # and refresh native text only on the edited page.
            self.records=previous
            if self.page_index in self.records:
                row=dict(self.records[self.page_index])
                ocr_words=[w for w in row['words'] if w.get('source')=='ocr']
                if drop_rect is not None:
                    ocr_words=[w for w in ocr_words if not fitz.Rect(w['rect']).intersects(drop_rect)]
                row['words']=word_rows(self.session.doc[self.page_index])+ocr_words
                self.records[self.page_index]=row
            self.ocr_complete=old_complete
            self.begin_search()
        if pages_changed:
            self.refresh_pages()
        else:
            self.loaded_thumbs.discard(self.page_index)
        self.render(True)
        return True

    def handle_gesture(self,mode,data):
        if not self.session:
            return
        if mode=='draw':
            color=self.canvas.pen_color
            key=(id(self.session),self.page_index)
            if self.mutate(lambda:self.session.ink(self.page_index,data,
                (color.redF(),color.greenF(),color.blueF()),self.pen_width.value()),preserve=True):
                if self.drawn_signature_page != key:
                    self.drawn_signature_strokes = []
                self.drawn_signature_page = key
                self.drawn_signature_strokes.append([(p[0],p[1]) for p in data])
                self.update_actions()
        elif mode=='image':
            self.mutate(lambda:self.session.image(self.page_index,data,self.signature_path),preserve=True)
        elif mode=='signature' and self.signature_stamp:
            stamp = self.signature_stamp
            date_text = format_date(stamp['date_format']) if stamp['include_date'] else ''
            self.mutate(lambda:self.session.signature(self.page_index,data,stamp['signature'],date_text),preserve=True)
        elif mode=='redact':
            self.mutate(lambda:self.session.mark_redaction(self.page_index,data))
            self.status.setText(t('Redaction marked. Apply redactions before saving, or Undo to remove the mark.'))
        elif mode=='correct':
            if not self.commit_inline_text():
                return
            old=self.session.doc[self.page_index].get_textbox(data)
            words=[w for w in self.records.get(self.page_index,{}).get('words',[]) if fitz.Rect(w['rect']).intersects(data)]
            if not old.strip():
                old=' '.join(w['text'] for w in words)
            self.stop_index()
            catalog=self.session.font_catalog()
            style=catalog.style(self.page_index,data)
            if not style.matched and words:
                import statistics
                size=max(3,min(50,statistics.median(fitz.Rect(w['rect']).height for w in words)*.78))
                style=replace_style(style,size=size,line_height=size*1.2)
            self.inline_text=InlineTextBox(self.canvas,data,catalog,style,old,replacement=True)
            self.inline_text.page_index=self.page_index
            self.inline_text.commit_requested.connect(self.commit_inline_text)
            self.inline_text.cancel_requested.connect(self.cancel_inline_text)
            self.inline_text.editor.textChanged.connect(self.update_actions)
            self.inline_text.draft_changed.connect(self.update_actions)

    def fill_form(self,point):
        if not self.session:
            return
        for widget in self.session.doc[self.page_index].widgets() or []:
            if not widget.rect.contains(point):
                continue
            if widget.field_type==fitz.PDF_WIDGET_TYPE_SIGNATURE:
                self.error('Certificate signatures are not supported. Use Draw / sign or Signature image.')
                return
            title=widget.field_label or widget.field_name or t('Form field')
            if widget.field_type==fitz.PDF_WIDGET_TYPE_CHECKBOX:
                value=widget.on_state() if widget.field_value=='Off' else 'Off'
                ok=True
            elif widget.field_type in (fitz.PDF_WIDGET_TYPE_COMBOBOX,fitz.PDF_WIDGET_TYPE_LISTBOX):
                value,ok=QInputDialog.getItem(self,t('Fill form'),title,widget.choice_values or [],0,False)
            elif widget.field_type in (fitz.PDF_WIDGET_TYPE_BUTTON,fitz.PDF_WIDGET_TYPE_RADIOBUTTON):
                self.error('This button type is not supported by the field editor. Use Add text if needed.')
                return
            else:
                value,ok=QInputDialog.getMultiLineText(self,t('Fill form'),title,str(widget.field_value or ''))
            if ok:
                xref=widget.xref
                self.mutate(lambda:self.session.fill(self.page_index,xref,value),preserve=True)
            return
        self.status.setText(t('No interactive field here. Choose Add text and click on the page to type.'))

    def remove_annotation(self,point):
        if not self.session:
            return
        for annot in self.session.doc[self.page_index].annots() or []:
            if annot.rect.contains(point):
                if QMessageBox.question(self,t('Remove annotation'),t('Remove this annotation?'))==QMessageBox.StandardButton.Yes:
                    xref=annot.xref
                    def remove():
                        with self.session.operation('Remove annotation'):
                            page=self.session.doc[self.page_index]
                            page.delete_annot(page.load_annot(xref))
                    self.mutate(remove)
                return

    def rotate(self):
        if self.session:
            self.mutate(lambda:self.session.rotate(self.page_index),True)

    def move_page(self,delta):
        if not self.session:
            return
        n=self.page_index
        target=n+delta
        if 0<=target<len(self.session.doc):
            order=list(range(len(self.session.doc)))
            order[n],order[target]=order[target],order[n]
            if self.mutate(lambda:self.session.reorder(order),True):
                self.go_page(target)

    def pages_reordered(self):
        if self.rebuilding or not self.session:
            return
        order=[self.pages.item(n).data(Qt.ItemDataRole.UserRole) for n in range(self.pages.count())]
        if order!=list(range(len(self.session.doc))):
            self.page_index=order.index(self.page_index)
            self.mutate(lambda:self.session.reorder(order),True)

    def delete_pages(self):
        if not self.session:
            return
        selected=sorted(self.pages.row(item) for item in self.pages.selectedItems()) or [self.page_index]
        if QMessageBox.question(self,t('Delete pages'),t(f'Delete {len(selected)} selected page(s)? You can undo this change.'))==QMessageBox.StandardButton.Yes:
            self.mutate(lambda:self.session.delete(selected),True)

    def split_pages(self):
        if not self.session:
            return
        selected=sorted(self.pages.row(item)+1 for item in self.pages.selectedItems()) or [self.page_index+1]
        value,ok=QInputDialog.getText(self,t('Extract / split pages'),t('Pages to save in a separate PDF, such as 1-5, 9, 12-20'),
                                     text=','.join(map(str,selected)))
        if not ok:
            return
        try:
            pages=page_range(value,len(self.session.doc))
            if self.session.pending_redactions():
                raise ValueError('Apply or undo pending redactions before extracting pages.')
            path=self.output_path('Save extracted pages','-pages.pdf')
            if path:
                self.session.split(pages,path)
                self.status.setText(t(f'Extracted {len(pages)} pages to {Path(path).name}'))
        except Exception as exc:
            self.error(exc)

    def merge_pdf(self):
        if not self.session:
            return
        path,_=QFileDialog.getOpenFileName(self,t('Insert PDF after current page'),'',t('PDF documents (*.pdf)'))
        if not path:
            return
        try:
            password=''
            with fitz.open(path) as doc:
                if doc.needs_pass or (doc.metadata and doc.metadata.get('encryption')):
                    password,ok=QInputDialog.getText(self,t('Password'),t('Inserted PDF password (owner password if editing is restricted)'),QLineEdit.EchoMode.Password)
                    if not ok:
                        return
            self.mutate(lambda:self.session.merge(path,self.page_index,password),True)
        except Exception as exc:
            self.error(exc)

    def undo(self):
        if self.session:
            self.mutate(self.session.undo,True,purge=self.session.redaction_applied)

    def redo(self):
        if self.session:
            self.mutate(self.session.redo,True,purge=self.session.redaction_applied)

    def apply_redactions(self):
        if not self.session or not self.session.pending_redactions():
            return
        answer=QMessageBox.warning(self,t('Apply permanent redactions'),
            t('Remove the marked text, image pixels, intersecting form fields and annotations?\n\n'
            'Saved files cannot recover removed content. Save updates the current file; Save copy preserves the original. '
            'Undo remains available only in this editing session.'),
            QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Apply:
            if self.mutate(self.session.apply_redactions,True,purge=True):
                self.status.setText(t('Redactions applied. Save the document or a copy to write the sanitized PDF.'))

    def output_path(self,title,suffix='-edited.pdf'):
        proposed=Path(self.session.path).with_name(Path(self.session.path).stem+suffix)
        path,_=QFileDialog.getSaveFileName(self,t(title),str(proposed),t('PDF documents (*.pdf)'))
        if not path:
            return ''
        if not path.lower().endswith('.pdf'):
            path+='.pdf'
        if Path(path).resolve()==Path(self.session.path):
            raise ValueError('Choose a new filename. Paperlight preserves the original PDF.')
        return path

    def save_copy(self):
        if not self.commit_inline_text():
            return False
        if not self.session:
            return False
        try:
            self.session.require_edit()
            if self.session.pending_redactions():
                raise ValueError('Apply or undo your marked redactions before saving.')
            if self.session.encrypted:
                answer = QMessageBox.question(self, t('Save without protection?'),
                    t('Save copy creates an unencrypted PDF. Use File > Protect PDF to set passwords and editing restrictions.'),
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel)
                if answer != QMessageBox.StandardButton.Save:
                    return False
            path=self.output_path('Save edited copy')
            if not path:
                return False
            self.session.save(path)
            self.status.setText(t(f'Saved {Path(path).name}. Original preserved.'))
            self.update_actions()
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def save_current(self):
        if not self.commit_inline_text():
            return False
        if not self.session:
            return False
        try:
            self.session.require_edit()
            if not self.session.dirty:
                return True
            if self.session.pending_redactions():
                raise ValueError('Apply or undo your marked redactions before saving.')
            # The indexing child may still hold the source open on Windows.
            # Stop it before the atomic replacement; keep completed search data.
            self.stop_index()
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.session.save_in_place()
            finally:
                QApplication.restoreOverrideCursor()
            self.status.setText(t('Saved changes to the current document.'))
            self.update_actions()
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def protect_pdf(self):
        if not self.commit_inline_text():
            return False
        if not self.session:
            return
        try:
            self.session.require_edit()
            if self.session.pending_redactions():
                raise ValueError('Apply or undo your marked redactions before saving.')
            dialog = ProtectionDialog(self)
            try:
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                protection = dialog.protection()
                path = self.output_path('Save protected copy', '-protected.pdf')
                if not path:
                    return
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    self.session.save(path, protection=protection)
                finally:
                    QApplication.restoreOverrideCursor()
                self.status.setText(t('Protected copy saved. The current editing session remains unlocked.'))
                self.update_actions()
            finally:
                dialog.open_password.clear()
                dialog.open_confirm.clear()
                dialog.owner_password.clear()
                dialog.owner_confirm.clear()
                dialog.deleteLater()
        except Exception as exc:
            self.error(exc)

    def unlock_editing(self):
        if not self.session or not self.session.readonly:
            return
        password, ok = QInputDialog.getText(self, t('Unlock editing'), t('Owner password for editing'), QLineEdit.EchoMode.Password)
        if not ok:
            return
        try:
            self.session.unlock(password)
            self.update_actions()
            self.status.setText(t('Editing unlocked. Save copy exports without protection; Protect PDF creates a protected copy.'))
        except Exception as exc:
            self.error(exc)

    def export_searchable(self):
        if not self.commit_inline_text():
            return
        if not self.session:
            return
        try:
            self.session.require_edit()
            if self.session.pending_redactions():
                raise ValueError('Apply or undo pending redactions before exporting.')
            incomplete=sum(not r.get('complete') for r in self.records.values())+len(self.session.doc)-len(self.records)
            if incomplete:
                if QMessageBox.question(self,t('OCR is incomplete'),t(f'{incomplete} pages have not completed OCR. Export the recognized pages so far?'))!=QMessageBox.StandardButton.Yes:
                    return
            path=self.output_path('Export searchable PDF','-searchable.pdf')
            if not path:
                return
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                with fitz.open(stream=self.session.doc.tobytes(),filetype='pdf') as output:
                    for n,row in self.records.items():
                        insert_ocr_words(output[n],row['words'])
                    atomic_pdf_write(output,path,sanitize=self.session.redaction_applied,clean_content=self.session.native_object_edited)
            finally:
                QApplication.restoreOverrideCursor()
            self.status.setText(t(f'Exported searchable copy: {Path(path).name}'))
        except Exception as exc:
            self.error(exc)

    def invalidate_search(self,purge=False):
        self.search_step.stop()
        self.search_timer.stop()
        self.records={}
        self.search_hits=[]
        self.results.clear()
        self.ocr_complete=False
        self.current_key=None
        self.search_status.setText(t('Document changed. Choose Recognize text to refresh OCR and search.'))
        if purge:
            for key in self.session_keys:
                for root in (self.cache_root,Path(self.session._temporary.name)/'search-cache'):
                    if len(key)==64 and all(c in '0123456789abcdef' for c in key):
                        shutil.rmtree(root/key,ignore_errors=True)
            self.session_keys.clear()

    def session_cache_root(self):
        if self.session and (self.session.encrypted or not self.remember_cache_action.isChecked()):
            return Path(self.session._temporary.name) / 'search-cache'
        return self.cache_root

    def set_remember_cache(self,checked):
        self.language_manager.settings.setValue('privacy/rememberCache',checked)
        self.language_manager.settings.sync()
        if self.session:
            self.start_index(False)

    def index_timeout(self):
        self.stop_index()
        self.status.setText(t('Recognition timed out. Completed pages remain available.'))

    def start_index(self,ocr=True,apply_ocr=False,pages=None):
        if not self.session:
            return
        if not self.commit_inline_text():
            return
        self.stop_index()
        self.ocr_apply_requested=apply_ocr
        seed=self.records
        self.records={}
        self.search_hits=[]
        self.results.clear()
        self.ocr_complete=False
        self.job_failed=False
        self.job_buffer=b''
        try:
            # Index original bytes until edits occur. Edited documents get an isolated
            # temporary snapshot, removed as soon as the process finishes or stops.
            path=self.session.path
            password=self.password
            if self.session.position != 0:
                fd,path=tempfile.mkstemp(prefix='paperlight-index-',suffix='.pdf')
                os.close(fd)
                self.job_temp=path
                self.session.write_index_snapshot(path)
                password=self.session._working_password
            self.job=QProcess(self)
            job=self.job
            job.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
            job.readyReadStandardOutput.connect(self.receive_index)
            job.readyReadStandardError.connect(lambda:self.receive_stderr(job))
            job.finished.connect(self.index_finished)
            job.errorOccurred.connect(lambda err:self.index_process_error(job,err))
            if getattr(sys,'frozen',False):
                arguments=['--index']
            else:
                arguments=[str(Path(__file__).resolve().parent.parent/'main.py'),'--index']
            job.start(sys.executable,arguments)
            if not job.waitForStarted(5000):
                raise ValueError('Could not start the OCR process.')
            cache_root = self.session_cache_root()
            config=dict(path=path,cache_root=str(cache_root),password=password,ocr=ocr,seed=seed,pages=pages)
            job.write((json.dumps(config)+'\n').encode())
            job.closeWriteChannel()
            self.job_watchdog.start(90000)
            self.progress.setRange(0,0)
            self.progress.show()
            self.status.setText(t('Reading searchable text…' if not ocr else 'Indexing text, then recognizing scanned pages…'))
            self.search_status.setText(t('Reading text. Results will appear as pages become available.'))
            self.update_actions()
        except Exception as exc:
            self.stop_index()
            self.error(exc)

    def receive_stderr(self,job):
        # Drain diagnostic output so it cannot block the child process. Keep it local.
        data=bytes(job.readAllStandardError()).decode('utf-8',errors='replace')
        if data:
            self.last_worker_diagnostic=data[-2000:]

    def index_process_error(self,job,error):
        if job is self.job:
            self.job_failed=True
            self.status.setText(t('OCR process could not run. You can keep reading and editing.'))

    def receive_index(self):
        if not self.job:
            return
        self.job_watchdog.start(90000)
        chunk=bytes(self.job.readAllStandardOutput())
        if len(self.job_buffer)+len(chunk)>32*1024*1024:
            self.stop_index()
            self.status.setText(t('Invalid recognition data. The worker was stopped.'))
            return
        self.job_buffer+=chunk
        while b'\n' in self.job_buffer:
            line,self.job_buffer=self.job_buffer.split(b'\n',1)
            if not line.strip():
                continue
            try:
                row=json.loads(line)
            except ValueError:
                continue
            if not isinstance(row,dict):
                self.stop_index()
                self.status.setText(t('Invalid recognition data. The worker was stopped.'))
                return
            kind=row.get('kind')
            if kind=='meta':
                key=row.get('key')
                if not isinstance(key,str) or len(key)!=64 or any(c not in '0123456789abcdef' for c in key):
                    self.stop_index()
                    self.status.setText(t('Invalid recognition data. The worker was stopped.'))
                    return
                self.current_key=row['key']
                self.session_keys.add(row['key'])
            elif kind=='page':
                page=row.get('page')
                if not self.session or not isinstance(page,int) or not 0<=page<len(self.session.doc) or not valid_record(row,page):
                    self.stop_index()
                    self.status.setText(t('Invalid recognition data. The worker was stopped.'))
                    return
                self.records[row['page']]=row
                if row['page']==self.page_index and row.get('ocr') and self.session:
                    self.canvas.set_text_model(PageText.from_page(self.session.doc[self.page_index],row['words']),
                                               (id(self.session),self.page_index,self.session.position))
                # Do not restart a partially completed scan for every page arrival.
                if self.search_box.text() and not self.search_timer.isActive() and not self.search_step.isActive():
                    self.search_timer.start(250)
            elif kind=='native_done':
                self.search_status.setText(t(f"Text available from {row['pages']} pages. {row['pending']} may need OCR."))
                self.begin_search()
            elif kind=='progress':
                self.progress.setRange(0,row['total'])
                self.progress.setValue(row['current']-1)
                self.status.setText(t(f"Recognizing page {row['page']+1} · {row['current']} of {row['total']} scanned pages"))
            elif kind=='warning':
                self.status.setText(t(f"OCR could not read page {row['page']+1}. Other pages will continue."))
            elif kind=='error':
                self.job_failed=True
                self.status.setText(t(f"OCR stopped: {row['message']}"))
            elif kind=='done':
                self.ocr_complete=not row['pending'] and not row['failures']
                if row['failures']:
                    self.status.setText(t(f"OCR finished with {len(row['failures'])} unreadable pages. Retry Recognize text if needed."))
                elif row['pending']:
                    self.status.setText(t(f"Text indexed · {row['pending']} pages may need OCR. Choose Recognize text."))
                else:
                    self.status.setText(t(f"Search ready · {row['pages']} pages · {row['seconds']:.2f}s · local index cached"))
                self.begin_search()
        self.update_actions()

    def index_finished(self,code,status):
        self.job_watchdog.stop()
        self.receive_index()
        job=self.job
        self.job=None
        if job:
            job.deleteLater()
        self.remove_job_temp()
        self.progress.hide()
        if code!=0 and not self.job_failed:
            self.status.setText(t('Recognition stopped unexpectedly. Text indexed so far is available.'))
        self.update_actions()
        if code==0 and self.ocr_apply_requested and not self.job_failed:
            self.ocr_apply_requested=False
            self.apply_recognized_text()
        self.ensure_edit_ocr()

    def remove_job_temp(self):
        if self.job_temp:
            try:
                os.unlink(self.job_temp)
            except OSError:
                pass
            self.job_temp=None

    def stop_index(self):
        if hasattr(self,'job_watchdog'):
            self.job_watchdog.stop()
        if self.job:
            job=self.job
            job.blockSignals(True)
            job.kill()
            job.waitForFinished(5000)
            self.job=None
            job.deleteLater()
            self.progress.hide()
            self.status.setText(t('Recognition stopped. Pages indexed so far remain searchable.'))
        self.remove_job_temp()
        if hasattr(self,'stop_action'):
            self.stop_action.setEnabled(False)

    def clear_cache(self):
        self.stop_index()
        if self.session:
            shutil.rmtree(Path(self.session._temporary.name)/'search-cache',ignore_errors=True)
        shutil.rmtree(self.cache_root,ignore_errors=True)
        # Only include the known legacy sibling when this is the real app cache.
        expected = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)).resolve()
        if self.cache_root.resolve().parent==expected and self.cache_root.name=='search-v4':
            shutil.rmtree(expected/'search-v3',ignore_errors=True)
        self.cache_root.mkdir(parents=True,exist_ok=True)
        self.invalidate_search()
        self.render(True)
        self.status.setText(t('Local search cache cleared. Documents are unchanged.'))

    def focus_find(self):
        self.tabs.setCurrentIndex(1)
        self.search_box.setFocus()
        self.search_box.selectAll()
        if not self.records and not self.job and self.session:
            self.start_index(False)

    def begin_search(self):
        self.search_step.stop()
        self.results.clear()
        self.search_hits=[]
        self.search_query=self.search_box.text().strip()
        self.search_pages=sorted(self.records)
        self.search_cursor=0
        if not self.search_query:
            self.highlight_page()
            self.search_status.setText(t(f'{len(self.records)} pages indexed. Choose Recognize text to read scans.' if not self.ocr_complete else f'{len(self.records)} pages indexed, including recognized scans.'))
            return
        self.search_step.start(0)

    def search_chunk(self):
        for n in self.search_pages[self.search_cursor:self.search_cursor+12]:
            for hit in search_words(self.records[n]['words'],self.search_query):
                hit['page']=n
                self.search_hits.append(hit)
                item=QListWidgetItem(t(f"Page {n+1}\n{hit['text'][:140]}"))
                item.setData(Qt.ItemDataRole.UserRole,hit)
                self.results.addItem(item)
                if len(self.search_hits)>=2000:
                    break
            if len(self.search_hits)>=2000:
                break
        self.search_cursor+=12
        if self.search_cursor>=len(self.search_pages) or len(self.search_hits)>=2000:
            self.search_step.stop()
            qualifier=' · OCR still running' if self.job else (' · some scans need OCR' if not self.ocr_complete else '')
            self.search_status.setText(t(f'{len(self.search_hits)} matches in {len(self.records)} indexed pages{qualifier}'))
            self.highlight_page()

    def result_chosen(self,item,previous):
        if item:
            hit=item.data(Qt.ItemDataRole.UserRole)
            self.go_page(hit['page'])
            if hit['rects']:
                r=fitz.Rect(hit['rects'][0])*self.session.doc[self.page_index].rotation_matrix
                self.canvas.centerOn(r.x0*self.canvas.factor+self.canvas.page_origin.x(),r.y0*self.canvas.factor+self.canvas.page_origin.y())

    def highlight_page(self):
        if self.session:
            rects=[r for hit in self.search_hits if hit['page']==self.page_index for r in hit['rects']]
            self.canvas.set_highlights(rects,self.session.doc[self.page_index].rotation_matrix)

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and any(url.toLocalFile().lower().endswith('.pdf') for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self,event):
        for url in event.mimeData().urls():
            path=url.toLocalFile()
            if path.lower().endswith('.pdf'):
                self.open_path(path)
                event.acceptProposedAction()
                break

    def guide(self):
        QMessageBox.information(self,t('Quick guide'),
            t('OPEN & READ\nOpen or drop a PDF. Use thumbnails or Alt+Left / Alt+Right. Ctrl+wheel zooms; Ctrl+0 fits the page.\n\n'
            'SELECT TEXT\nThe read cursor selects text automatically. Drag across text, double-click a word, '
            'or Ctrl+A for the current page. Ctrl+C copies; Escape clears. Recognize text first for scans.\n\n'
            'SEARCH\nCtrl+F finds existing text immediately. Recognize text runs English + Simplified/Traditional Chinese OCR offline. '
            'The first OCR pass takes time. Search caches are encrypted and session-only by default; Tools can enable reuse between sessions. Stop OCR preserves completed pages. '
            'Recognize text adds a selectable text layer to the current PDF. Save to keep it; Correct text replaces scan text.\n\n'
            'EDIT\nDraw / sign writes with your mouse. Click with Add text to type live on the page. Use the three-dot button to format, Done or Ctrl+Enter to apply, and Escape to cancel. All editing tools are visible on the toolbar. Drag a rectangle with Correct text to edit it on the page. '
            'Correct text removes the original contents inside that rectangle; it does not reflow surrounding paragraphs. '
            'Signature image places a PNG/JPEG in a rectangle. Fill form edits existing text, checkbox and choice fields. '
            'Right-click an annotation to remove it. Ctrl+Z / Ctrl+Y undo and redo.\n\n'
            'PAGES\nDrag thumbnails to reorder, or use Pages menu commands. Ctrl/Shift selects multiple thumbnails. '
            'Extract / split saves the chosen range separately. Insert / merge adds a PDF after the current page.\n\n'
            'REDACT & SAVE\nMark areas, then Apply redactions. Ctrl+S saves the current document; Save copy preserves the original. Redacted exports discard unused objects and metadata. '
            'Search caches for the current session are removed when redactions or corrections are applied. '
            'Tools > Clear local search cache removes all cached OCR text.\n\n'
            'OCR accuracy depends on scan quality. Existing cryptographic signatures are not preserved by editing. '
            'Save preserves existing password protection. Use File > Protect PDF to create a copy with new protection. Save copy creates an unencrypted edited copy after owner unlock.'))

    def about(self):
        QMessageBox.information(self,t('About Paperlight'),
            t('Paperlight 1.1.1\nAn offline PDF workspace for Windows.\n\n'
            'Built with PySide6 / Qt, PyMuPDF / MuPDF, and Tesseract. '
            'This source project is distributed under AGPL-3.0-or-later. '
            'Third-party notices are included with the application.\n\n'
            'Preview workflow references: Apple documentation. REA diagnostics were run on Windows; no Mac Preview binary was inspected.'))

    def closeEvent(self,event):
        if not self.confirm_discard():
            event.ignore()
            return
        self.stop_index()
        self.edit_controller.stop()
        if self.session:
            self.session.close()
            self.session=None
        self.thumbnail_timer.stop()
        self.search_timer.stop()
        self.search_step.stop()
        event.accept()


def run(path=None,smoke=None):
    app=QApplication(sys.argv[:1])
    app.setApplicationName('Paperlight')
    app.setOrganizationName('Paperlight')
    if smoke:
        # Verification must not migrate a user's real signature/cache storage.
        app.setApplicationName('Paperlight-Verification')
    resources=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
    app.setWindowIcon(QIcon(str(resources/'assets'/'paperlight.ico')))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window=Window()
    window.show()
    if path:
        QTimer.singleShot(80,lambda:window.open_path(path))
    if smoke:
        def smoke_error(exc):
            raise RuntimeError(str(exc))
        window.error=smoke_error
        def capture():
            window.grab().save(smoke)
            if window.session:
                window.session.saved_position=window.session.position
            window.close()
        QTimer.singleShot(2500,capture)
    return app.exec()
