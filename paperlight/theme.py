"""Original vector controls for a restrained desktop document workspace."""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QCursor


PATHS={
 'sidebar': 'sidebar', 'open':'open', 'save':'save', 'undo':'undo', 'redo':'redo',
 'ocr':'ocr','search':'search','previous':'previous','next':'next','minus':'minus',
 'plus':'plus','fit':'fit','markup':'markup','read':'read','draw':'draw',
 'text':'text','correct':'correct','image':'image','form':'form','redact':'redact',
 'rotate':'rotate','more':'more',
}


def paint_symbol(p,name,color='#55575c'):
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color),1.65,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    def line(x,y,a,b): p.drawLine(QPointF(x,y),QPointF(a,b))
    def rect(x,y,w,h,r=1.7): p.drawRoundedRect(QRectF(x,y,w,h),r,r)
    def ellipse(x,y,w,h): p.drawEllipse(QRectF(x,y,w,h))
    if name=='sidebar':
        rect(3,4,18,16);line(9,4,9,20);line(5.5,8,6.5,8);line(5.5,12,6.5,12)
    elif name=='open':
        path=QPainterPath(QPointF(3,19));path.lineTo(3,6);path.lineTo(9,6);path.lineTo(11,8);path.lineTo(21,8);path.lineTo(21,19);path.closeSubpath();p.drawPath(path)
    elif name=='save':
        rect(5,9,14,12);line(12,3,12,15);line(8,11,12,15);line(12,15,16,11)
    elif name in ('undo','redo'):
        if name=='redo': p.translate(24,0);p.scale(-1,1)
        path=QPainterPath(QPointF(5,9));path.cubicTo(22,3,24,22,9,20);p.drawPath(path);line(5,9,5,4);line(5,9,10,11)
    elif name=='search':
        ellipse(4,3,12,12);line(14,14,21,21)
    elif name in ('previous','next'):
        x=14 if name=='previous' else 10;a=8 if name=='previous' else 16
        line(x,6,a,12);line(a,12,x,18)
    elif name in ('minus','plus'):
        line(6,12,18,12)
        if name=='plus':line(12,6,12,18)
    elif name=='fit':
        rect(6,3,12,18);line(2,8,2,16);line(22,8,22,16)
    elif name in ('draw','markup','correct'):
        path=QPainterPath(QPointF(5,18));path.lineTo(7,12);path.lineTo(17,3);path.lineTo(21,7);path.lineTo(11,17);path.closeSubpath();p.drawPath(path);line(15,5,19,9);line(5,18,10,17)
        if name=='correct':line(4,22,19,22)
    elif name=='text':
        line(5,5,19,5);line(12,5,12,20);line(8,20,16,20);line(5,5,5,8);line(19,5,19,8)
    elif name=='select':
        line(9,4,15,4);line(12,4,12,20);line(9,20,15,20)
        for x,y,sx,sy in [(3,4,1,1),(21,4,-1,1),(3,20,1,-1),(21,20,-1,-1)]:
            line(x,y,x+2*sx,y);line(x,y,x,y+4*sy)
    elif name=='signature':
        path=QPainterPath(QPointF(4,17));path.cubicTo(14,3,17,0,10,13);path.cubicTo(4,23,7,19,14,13);path.cubicTo(10,21,15,13,17,15);path.cubicTo(15,19,19,16,21,14);p.drawPath(path)
        line(3,21,21,21)
    elif name=='image':
        rect(3,4,18,16);ellipse(7,7,3,3);line(4,18,10,12);line(10,12,14,16);line(14,16,17,13);line(17,13,21,17)
    elif name=='form':
        rect(3,5,18,14);line(6,10,11,10);line(6,14,15,14);line(17,8,17,16)
    elif name=='redact':
        rect(3,5,18,14);p.fillRect(QRectF(6,9,12,6),QColor(color))
    elif name=='read':
        path=QPainterPath(QPointF(7,12));path.lineTo(7,8);path.cubicTo(7,5,10,5,10,8);path.lineTo(10,4);path.cubicTo(10,1,13,1,13,4);path.lineTo(13,7);path.cubicTo(15,3,17,5,17,8);path.cubicTo(20,6,21,8,20,12);path.lineTo(18,20);path.lineTo(10,21);path.lineTo(4,14);path.cubicTo(2,11,5,9,7,12);p.drawPath(path)
    elif name=='ocr':
        for x,y,sx,sy in [(3,3,1,1),(21,3,-1,1),(3,21,1,-1),(21,21,-1,-1)]:
            line(x,y,x+4*sx,y);line(x,y,x,y+4*sy)
        line(7,16,12,7);line(12,7,17,16);line(9,13,15,13)
    elif name=='rotate':
        path=QPainterPath(QPointF(6,7));path.cubicTo(20,-1,27,20,12,21);path.cubicTo(6,21,3,16,4,12);p.drawPath(path);line(6,7,6,2);line(6,7,11,8)
    elif name=='more':
        for x in [5,12,19]:
            p.setBrush(QColor(color));ellipse(x-1,11,2,2)


def icon(name):
    result=QIcon()
    for mode,color in [(QIcon.Mode.Normal,'#52545a'),(QIcon.Mode.Disabled,'#b7b8bd'),(QIcon.Mode.Active,'#202126')]:
        for state in [QIcon.State.Off,QIcon.State.On]:
            pix=QPixmap(48,48);pix.fill(Qt.GlobalColor.transparent);pix.setDevicePixelRatio(2)
            p=QPainter(pix);paint_symbol(p,name,'#1671e7' if state==QIcon.State.On else color);p.end()
            result.addPixmap(pix,mode,state)
    return result


def tool_cursor(mode):
    if mode=='read':return QCursor(Qt.CursorShape.OpenHandCursor)
    if mode in ('text','select'):return QCursor(Qt.CursorShape.IBeamCursor)
    if mode=='form':return QCursor(Qt.CursorShape.PointingHandCursor)
    pix=QPixmap(36,36);pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix)
    p.setPen(QPen(QColor('white'),3))
    p.drawLine(1,4,9,4);p.drawLine(5,0,5,8)
    p.setPen(QPen(QColor('#242529'),1));p.drawLine(1,4,9,4);p.drawLine(5,0,5,8)
    p.translate(9,9)
    paint_symbol(p,{'draw':'draw','signature':'signature','correct':'correct','image':'image','redact':'redact'}.get(mode,'text'),'#202126')
    p.end()
    return QCursor(pix,5,4)


STYLE='''
QWidget {font-family:"Segoe UI"; font-size:12px; color:#303136;}
QMainWindow,QDialog {background:#f5f5f7;}
QMenuBar {background:#f5f5f7; color:#66666e; padding:1px 8px; font-size:11px;}
QMenuBar::item {padding:3px 9px; border-radius:4px;}
QMenuBar::item:selected {background:#e4e4e8;}
QToolBar {background:#f5f5f7; border:0; border-bottom:1px solid #d9d9de; padding:8px 12px; spacing:5px;}
QToolBar#markupBar {background:#fafafb; padding:6px 12px;}
QToolBar::separator {background:#d9d9df; width:1px; margin:5px 8px;}
QToolButton {border:1px solid transparent; border-radius:6px; padding:6px; min-width:24px; min-height:23px;}
QToolButton:hover {background:#e8e8ed;}
QToolButton:checked {background:#e0eafa; border-color:#d4e1f4; color:#1265ca;}
QToolButton:disabled {color:#b8b8bd;}
QToolButton::menu-indicator {image:none;}
QPushButton {border:1px solid #d5d5dc; border-radius:6px; background:white; padding:6px 13px;}
QPushButton:hover {background:#eeeef2;}
QPushButton:checked {background:#e0eafa;color:#1265ca;border-color:#c6dafa;}
QPushButton#primary {background:#1671e7; border-color:#1264d4; color:white; font-weight:600;}
QPushButton#primary:hover {background:#1264cf;}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QPlainTextEdit {background:#fff; border:1px solid #d7d7df; border-radius:5px; padding:5px 7px; selection-background-color:#bdd8fc;}
QLineEdit:focus,QPlainTextEdit:focus {border-color:#6faaf3;}
QSpinBox::up-button,QSpinBox::down-button,QDoubleSpinBox::up-button,QDoubleSpinBox::down-button {width:0; border:0;}
QComboBox::drop-down {border:0; width:24px;}
QComboBox::down-arrow {image:none;}
QListWidget {background:#eeeef1; border:0; outline:0; padding:10px;}
QListWidget::item {border:0; border-radius:6px; padding:8px; margin:4px 0;}
QListWidget::item:selected {background:#d9e6f8; color:#15569c;}
QTabWidget::pane {border:0; background:#eeeef1;}
QTabBar {background:#eeeef1;}
QTabBar::tab {background:#eeeef1; color:#7a7b83; padding:10px 20px; border:0;}
QTabBar::tab:selected {color:#33343a; font-weight:600;}
QTabBar::tab:hover {color:#1671e7;}
QSplitter::handle {background:#d4d4da; width:1px;}
QStatusBar {background:#f5f5f7; border-top:1px solid #d9d9df; padding:2px 10px;}
QStatusBar QLabel {color:#85858f; font-size:11px;}
QStatusBar::item {border:0;}
QMenu {background:#fcfcfd; border:1px solid #d4d4dc; border-radius:7px; padding:6px;}
QMenu::item {padding:7px 26px; border-radius:4px;}
QMenu::item:selected {background:#1671e7;color:white;}
QToolTip {background:#303136; color:white; border:0; border-radius:4px; padding:5px 8px;}
QProgressBar {border:0; background:#e2e2e9; border-radius:2px; max-height:4px;}
QProgressBar::chunk {background:#1671e7;border-radius:2px;}
QLabel#muted {color:#82828c;}
QScrollBar:vertical {background:transparent;width:10px;margin:3px;}
QScrollBar::handle:vertical {background:#bcbcc4;border-radius:3px;min-height:35px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
'''


def interface_style(language='en'):
    if language != 'zh_CN':
        return STYLE
    return STYLE.replace('font-family:"Segoe UI"; font-size:12px;',
        'font-family:"Microsoft YaHei UI","Microsoft YaHei","Segoe UI"; font-size:13px;') + '''
QMenuBar {font-size:12px;}
QStatusBar QLabel {font-size:12px;}
QTabBar::tab:selected {font-weight:500;}
'''
