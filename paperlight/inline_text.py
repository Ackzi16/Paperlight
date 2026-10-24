"""An in-page draft. PDF bytes change only when the user commits the box."""
from dataclasses import replace
import re
import pymupdf as fitz
from PySide6.QtCore import Qt, Signal, QEvent, QByteArray
from PySide6.QtGui import QFont, QFontDatabase, QColor, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QToolButton, QPushButton, QDialog, QFormLayout, QComboBox, QDoubleSpinBox, QColorDialog, QTextEdit)
from .i18n import t


class ResizeCorner(QToolButton):
    def __init__(self,box):
        super().__init__(box);self.box=box
        self.setText('↘');self.setToolTip(t('Resize'));self.setFixedWidth(22);self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setStyleSheet('padding:2px;min-height:20px;font-size:10px;')
    def mousePressEvent(self,event):
        self.origin=event.globalPosition();self.size_start=self.box.size()
    def mouseMoveEvent(self,event):
        if not event.buttons() & Qt.MouseButton.LeftButton: return
        delta=event.globalPosition()-self.origin;box=self.box;canvas=box.canvas
        width=max(70,self.size_start.width()+round(delta.x()))
        height=max(60,self.size_start.height()+round(delta.y()))
        p=canvas.mapToScene(box.pos());right=p.x()+(width-2);bottom=p.y()+(height-31)
        if canvas.continuous_doc is not None:
            page=canvas.continuous_doc[box.page_index];origin=canvas.page_layout[box.page_index].topLeft();matrix=page.derotation_matrix
        else: origin=canvas.page_origin;matrix=canvas.page_transform
        a=fitz.Point((p.x()-origin.x())/canvas.factor,(p.y()-origin.y())/canvas.factor)*matrix
        b=fitz.Point((right-origin.x())/canvas.factor,(bottom-origin.y())/canvas.factor)*matrix
        rect=fitz.Rect(a,b);rect.normalize();bounds=canvas.page_bounds
        rect &= bounds
        if rect.width>8 and rect.height>8: box.rect=rect;box.update_layout()


class MoveCorner(QToolButton):
    def __init__(self,box):
        super().__init__(box);self.box=box
        self.setText('↔');self.setToolTip(t('Move text box'));self.setFixedWidth(22)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setStyleSheet('padding:2px;min-height:20px;min-width:0;')
    def mousePressEvent(self,event):
        self.origin=event.globalPosition();self.start_rect=fitz.Rect(self.box.rect)
    def mouseMoveEvent(self,event):
        if not event.buttons()&Qt.MouseButton.LeftButton:return
        delta=event.globalPosition()-self.origin;box=self.box
        a=fitz.Point(0,0)*box.canvas.page_transform
        b=fitz.Point(delta.x()/box.canvas.factor,delta.y()/box.canvas.factor)*box.canvas.page_transform
        offset=b-a;rect=self.start_rect+(offset.x,offset.y,offset.x,offset.y)
        if box.canvas.page_bounds.contains(rect):box.rect=rect;box.update_layout()


class InlineTextBox(QFrame):
    commit_requested = Signal()
    cancel_requested = Signal()
    draft_changed = Signal()

    def __init__(self, canvas, rect, catalog, style, text='', replacement=False,rich=False):
        super().__init__(canvas.viewport())
        self.canvas, self.rect, self.style = canvas, fitz.Rect(rect), style
        self.catalog, self.replacement = catalog, replacement
        self.rich=rich
        self._layout_updating=False
        self.page_index = canvas.active_page
        self.setObjectName('inlineTextBox')
        self.setStyleSheet('QFrame#inlineTextBox {background:white;border:1px solid #4285d4;border-radius:3px;}')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1,1,1,1)
        layout.setSpacing(0)
        self.editor = QTextEdit() if rich else QPlainTextEdit()
        if rich: self.editor.setAcceptRichText(False)
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setPlainText(text)
        self.editor.document().setDocumentMargin(0)
        self.editor.setTabChangesFocus(False)
        self.editor.installEventFilter(self)
        layout.addWidget(self.editor,1)
        row = QHBoxLayout()
        row.setContentsMargins(4,0,4,2)
        self.cancel_button = QPushButton(t('Cancel'))
        self.done_button = QPushButton(t('Done'))
        for button in (self.cancel_button,self.done_button):
            button.setStyleSheet('padding:2px 7px;min-height:20px;font-size:11px;')
        row.addWidget(self.cancel_button)
        row.addStretch()
        row.addWidget(self.done_button)
        self.resize_corner=ResizeCorner(self)
        row.addWidget(self.resize_corner)
        self.move_corner=MoveCorner(self)
        row.addWidget(self.move_corner)
        layout.addLayout(row)
        self.more_button = QToolButton(canvas.viewport())
        self.destroyed.connect(self.more_button.deleteLater)
        self.more_button.setText('...')
        self.more_button.setToolTip(t('Text formatting'))
        self.more_button.setStyleSheet('QToolButton {background:#eef4ff;border:0;border-radius:4px;font-size:16px;padding:0;min-width:0;min-height:0;}')
        self.more_button.setFixedSize(27,23)
        self.more_button.clicked.connect(self.format_text)
        self.done_button.clicked.connect(self.commit_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.editor.textChanged.connect(self.update_layout)
        self.update_layout()
        self.show()
        self.raise_()
        self.editor.setFocus()
        if text:
            self.editor.selectAll()

    def showEvent(self,event):
        super().showEvent(event)
        if hasattr(self,'more_button'):self.more_button.show();self.more_button.raise_()

    def hideEvent(self,event):
        if hasattr(self,'more_button'):self.more_button.hide()
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        if event.type()==QEvent.Type.KeyPress:
            if event.key()==Qt.Key.Key_Escape:
                self.cancel_requested.emit()
                return True
            if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.commit_requested.emit()
                return True
        return super().eventFilter(obj,event)

    def update_layout(self):
        if self._layout_updating: return
        self._layout_updating=True
        canvas=self.canvas
        # Keep the draft bound to its page when continuous scrolling activates another page.
        if canvas.continuous_doc is not None:
            page=canvas.continuous_doc[self.page_index]
            origin=canvas.page_layout[self.page_index].topLeft()
            rotation=page.rotation_matrix
        else:
            origin=canvas.page_origin
            rotation=~canvas.page_transform
        box=self.rect*rotation
        point=canvas.mapFromScene(box.x0*canvas.factor+origin.x(),box.y0*canvas.factor+origin.y())
        self.move(point)
        width=max(45,round(box.width*canvas.factor))
        height=max(30,round(box.height*canvas.factor))
        self.resize(width,height+29)
        self.more_button.move(self.x()+max(0,width-29),self.y()-24 if self.y()>=24 else self.y()+height+29)
        self.more_button.raise_()
        choice=self.style.choice
        background=self.readable_background()
        style_key=(id(choice),self.style.size,self.style.line_height,self.style.align,self.style.color,canvas.factor,any(ord(c)>127 for c in self.editor.toPlainText()),background)
        if style_key==getattr(self,'_layout_style_key',None):
            self._layout_updating=False;self.draft_changed.emit();return
        self._layout_style_key=style_key
        font,_,substitute=choice.resolve(self.editor.toPlainText())
        family=choice.name
        if choice.buffer and not substitute:
            if not hasattr(choice,'qt_families'):
                handle=QFontDatabase.addApplicationFontFromData(QByteArray(choice.buffer))
                choice.qt_families=QFontDatabase.applicationFontFamilies(handle) if handle>=0 else []
            if choice.qt_families: family=choice.qt_families[0]
        if substitute: family=font.name
        family={'Helvetica':'Arial','Times-Roman':'Times New Roman','Courier':'Courier New','Droid Sans Fallback Regular':'Microsoft YaHei'}.get(family,family)
        preview=QFont(family)
        preview.setPointSizeF(max(1,self.style.size*canvas.factor*72/self.logicalDpiY()))
        preview.setBold(bool(choice.flags & 16))
        preview.setItalic(bool(choice.flags & 2))
        self.editor.setFont(preview)
        color=QColor.fromRgbF(*self.style.color).name()
        safe_family=re.sub(r'["\\\r\n;{}]','',family)
        pixels=max(1,round(self.style.size*canvas.factor))
        weight=700 if choice.flags & 16 else 400
        italic='italic' if choice.flags & 2 else 'normal'
        self.editor.setStyleSheet(f'QPlainTextEdit,QTextEdit {{background:{background};color:{color};border:0;padding:0;margin:0;font-family:"{safe_family}";font-size:{pixels}px;font-weight:{weight};font-style:{italic};selection-background-color:#c4dcff;selection-color:#15171b;}}')
        cursor=QTextCursor(self.editor.document())
        cursor.select(QTextCursor.SelectionType.Document)
        block=QTextBlockFormat()
        block.setLineHeight(self.style.line_height*canvas.factor,QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        block.setAlignment({'left':Qt.AlignmentFlag.AlignLeft,'center':Qt.AlignmentFlag.AlignHCenter,'right':Qt.AlignmentFlag.AlignRight}[self.style.align])
        self.editor.blockSignals(True)
        cursor.mergeBlockFormat(block)
        self.editor.blockSignals(False)
        if self.rich:
            from .richtext import scale_formats
            scale_formats(self)
        self._layout_updating=False
        self.draft_changed.emit()

    def readable_background(self):
        colors=[QColor.fromRgbF(*self.style.color)]
        if self.rich:
            block=self.editor.document().begin()
            while block.isValid():
                fragment=block.begin()
                while not fragment.atEnd():
                    value=fragment.fragment()
                    if value.isValid() and value.text().strip():
                        brush=value.charFormat().foreground()
                        if brush.style()!=Qt.BrushStyle.NoBrush:colors.append(brush.color())
                    fragment+=1
                block=block.next()
        def luminance(color):
            values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in (color.redF(),color.greenF(),color.blueF())]
            return sum(a*b for a,b in zip(values,(.2126,.7152,.0722)))
        light=any(luminance(color)>.55 for color in colors)
        dark=any(luminance(color)<.18 for color in colors)
        # Editing-only contrast; retain the actual run colors in the PDF.
        return '#767676' if light and dark else '#202124' if light else '#ffffff'

    def format_text(self):
        panel=QDialog(self,Qt.WindowType.Popup)
        self.format_panel=panel
        panel.setWindowTitle(t('Text formatting'))
        layout=QFormLayout(panel)
        fonts=QComboBox()
        for choice in self.catalog.choices: fonts.addItem(choice.name,choice)
        fonts.setCurrentIndex(max(0,fonts.findData(self.style.choice)))
        size=QDoubleSpinBox(); size.setRange(3,300); size.setValue(self.style.size)
        spacing=QDoubleSpinBox(); spacing.setRange(3,1000); spacing.setValue(self.style.line_height)
        align=QComboBox()
        for value in ('left','center','right'): align.addItem(t(value.title()),value)
        align.setCurrentIndex(max(0,align.findData(self.style.align)))
        color=QPushButton(t('Color'))
        note=QPlainTextEdit(); note.setReadOnly(True); note.setMaximumHeight(55)
        def apply(*args,change='layout'):
            self.style=replace(self.style,choice=fonts.currentData(),size=size.value(),line_height=spacing.value(),align=align.currentData())
            _,source,_=self.style.choice.resolve(self.editor.toPlainText())
            note.setPlainText(t(source))
            if self.rich and getattr(self,'_format_ready',False): self.format_modified=True
            self.update_layout()
            if self.rich and getattr(self,'_format_ready',False):
                from .richtext import apply_format
                self.format_modified=True
                apply_format(self,change)
        def choose_color():
            value=QColorDialog.getColor(QColor.fromRgbF(*self.style.color),panel,t('Text color'))
            if value.isValid():
                self.style=replace(self.style,color=(value.redF(),value.greenF(),value.blueF()))
                apply(change='color')
        fonts.currentIndexChanged.connect(lambda *args:apply(change='font'))
        def resize_font(value):
            spacing.blockSignals(True)
            spacing.setValue(self.style.line_height*value/max(1,self.style.size))
            spacing.blockSignals(False)
            apply(change='size')
        size.valueChanged.connect(resize_font)
        spacing.valueChanged.connect(apply)
        align.currentIndexChanged.connect(apply)
        color.clicked.connect(choose_color)
        layout.addRow(t('Font'),fonts); layout.addRow(t('Size'),size)
        layout.addRow(t('Line spacing'),spacing); layout.addRow(t('Alignment'),align)
        layout.addRow(color); layout.addRow(note)
        done=QPushButton(t('Done')); done.clicked.connect(panel.accept); layout.addRow(done)
        self._format_ready=False
        apply()
        self._format_ready=True
        panel.finished.connect(lambda:self.editor.setFocus())
        panel.adjustSize()
        panel.move(self.more_button.mapToGlobal(self.more_button.rect().bottomRight()))
        panel.show()
