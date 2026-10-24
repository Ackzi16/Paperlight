"""Styled paragraph drafts, laid out by Qt and written with PDF font programs."""
from dataclasses import replace
import pymupdf as fitz
from PySide6.QtGui import QColor,QFont,QFontDatabase,QTextCursor,QTextCharFormat,QTextFormat
from PySide6.QtCore import QByteArray
from .typography import normalized
CHOICE=QTextFormat.Property.UserProperty.value+1
SIZE=CHOICE+1


def qt_font(choice,size,widget):
    family=choice.name
    if choice.buffer:
        if not hasattr(choice,'qt_families'):
            handle=QFontDatabase.addApplicationFontFromData(QByteArray(choice.buffer))
            choice.qt_families=QFontDatabase.applicationFontFamilies(handle) if handle>=0 else []
        if choice.qt_families: family=choice.qt_families[0]
    family={'Helvetica':'Arial','Helvetica-Bold':'Arial','Times-Roman':'Times New Roman','Courier':'Courier New'}.get(family,family)
    font=QFont(family);font.setPointSizeF(size*widget.canvas.factor*72/widget.logicalDpiY())
    font.setBold(bool(choice.flags&16));font.setItalic(bool(choice.flags&2))
    return font


def load(box,obj):
    editor=box.editor;editor.blockSignals(True);editor.clear()
    cursor=editor.textCursor();line=None
    for span in obj.spans:
        if line is not None and span['line']!=line: cursor.insertText('\n')
        choice=box.catalog.by_name.get(normalized(span['font']),box.style.choice)
        fmt=QTextCharFormat();fmt.setFont(qt_font(choice,span['size'],box))
        fmt.setProperty(CHOICE,box.catalog.choices.index(choice));fmt.setProperty(SIZE,span['size'])
        color=span['color'];fmt.setForeground(QColor((color>>16)&255,(color>>8)&255,color&255))
        cursor.insertText(span['text'],fmt);line=span['line']
    editor.blockSignals(False)
    box.original_text=editor.toPlainText()
    box.initial_html=editor.toHtml()
    box.original_rect=fitz.Rect(box.rect)
    box.editor.document().setModified(False)
    box.rich_factor=box.canvas.factor
    box.update_layout()
    box.format_modified=False
    box.editor.document().setModified(False)


def apply_format(box,change='font'):
    if not hasattr(box,'format_changes'):box.format_changes=set()
    box.format_changes.add(change)
    if change=='layout': return
    cursor=QTextCursor(box.editor.document());cursor.select(QTextCursor.SelectionType.Document)
    fmt=QTextCharFormat()
    if change=='font':
        fmt.setFont(qt_font(box.style.choice,box.style.size,box))
        fmt.setProperty(CHOICE,box.catalog.choices.index(box.style.choice));fmt.setProperty(SIZE,box.style.size)
    elif change=='size':
        fmt.setFontPointSize(box.style.size*box.canvas.factor*72/box.logicalDpiY())
        fmt.setProperty(SIZE,box.style.size)
    elif change=='color': fmt.setForeground(QColor.fromRgbF(*box.style.color))
    cursor.mergeCharFormat(fmt)


def scale_formats(box):
    if getattr(box,'rich_factor',box.canvas.factor)==box.canvas.factor: return
    box.rich_factor=box.canvas.factor
    doc=box.editor.document();block=doc.begin();changes=[]
    while block.isValid():
        it=block.begin()
        while not it.atEnd():
            fragment=it.fragment()
            if fragment.isValid():
                fmt=fragment.charFormat();index=fmt.property(CHOICE)
                choice=box.catalog.choices[int(index)] if index is not None else box.style.choice
                size=float(fmt.property(SIZE) or box.style.size)
                fmt.setFont(qt_font(choice,size,box));changes.append((fragment.position(),fragment.length(),fmt))
            it+=1
        block=block.next()
    for start,length,fmt in changes:
        cursor=QTextCursor(doc);cursor.setPosition(start);cursor.setPosition(start+length,QTextCursor.MoveMode.KeepAnchor);cursor.mergeCharFormat(fmt)


def utf16_slice(text,start,end):
    return text.encode('utf-16-le')[start*2:end*2].decode('utf-16-le')


def layout(box):
    changes=getattr(box,'format_changes',set())
    if box.editor.toPlainText()==box.original_text and abs(box.rect.width-box.original_rect.width)<.01 and abs(box.rect.height-box.original_rect.height)<.01 and changes<= {'color'}:
        runs=[]
        for span in box.pdf_object.spans:
            choice=box.catalog.by_name.get(normalized(span['font']),box.style.choice)
            color=span['color'];color=box.style.color if 'color' in changes else (((color>>16)&255)/255,((color>>8)&255)/255,(color&255)/255)
            runs.append(dict(text=span['text'],x=span['origin'][0]-box.original_rect.x0,y=span['origin'][1]-box.original_rect.y0,size=span['size'],color=color,choice=choice))
        return runs
    doc=box.editor.document().clone()
    factor=box.canvas.factor
    doc.setDocumentMargin(0);doc.setTextWidth(box.rect.width*factor)
    doc.documentLayout().documentSize()
    result=[];first_baseline=None
    block=doc.begin()
    while block.isValid():
        text_layout=block.layout();origin=text_layout.position();it=block.begin();fragments=[]
        while not it.atEnd():
            fragment=it.fragment()
            if fragment.isValid(): fragments.append(fragment)
            it+=1
        for n in range(text_layout.lineCount()):
            line=text_layout.lineAt(n)
            baseline=(origin.y()+line.y()+line.ascent())/factor
            if first_baseline is None: first_baseline=baseline
            for fragment in fragments:
                start=max(line.textStart(),fragment.position()-block.position())
                end=min(line.textStart()+line.textLength(),fragment.position()-block.position()+fragment.length())
                if end<=start: continue
                text=utf16_slice(block.text(),start,end)
                fmt=fragment.charFormat();index=fmt.property(CHOICE)
                choice=box.catalog.choices[int(index)] if index is not None else box.style.choice
                size=float(fmt.property(SIZE) or box.style.size)
                color=fmt.foreground().color()
                font,_,_=choice.resolve(text)
                x=(origin.x()+line.cursorToX(start)[0])/factor
                # Reserve the original first baseline while allowing paragraph reflow.
                offset=(box.style.anchor[1]-box.original_rect.y0-first_baseline) if box.style.anchor else 0
                y=baseline+offset
                if y-font.descender*size>box.rect.height+1 or x+font.text_length(text,fontsize=size)>box.rect.width+1:
                    raise ValueError('The text does not fit. Resize the text box or reduce the font size.')
                result.append(dict(text=text,x=x,y=y,size=size,color=(color.redF(),color.greenF(),color.blueF()),choice=choice))
        block=block.next()
    doc.deleteLater()
    return result


def insert(page,rect,runs):
    for run in runs:
        font,_,_=run['choice'].resolve(run['text'])
        writer=fitz.TextWriter(page.rect*page.derotation_matrix)
        writer.append((rect.x0+run['x'],rect.y0+run['y']),run['text'],font=font,fontsize=run['size'])
        writer.write_text(page,color=run['color'])
