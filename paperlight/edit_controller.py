"""Revision-checked GUI broker for the separate edit renderer."""
import json,sys,base64
from pathlib import Path
from dataclasses import asdict
from PySide6.QtCore import QObject,QProcess,QTimer,QByteArray
from PySide6.QtGui import QPixmap
from .objects import PageObject
from .i18n import t

class EditController(QObject):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.job=None;self.buffer=b''
        self.serial=0;self.request=None;self.pending=None;self.busy=False;self.generation=0
        self.layers={};self.watchdog=QTimer(self);self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self.timeout)

    def stop(self):
        self.generation+=1
        job=self.job;self.job=None;self.request=None;self.pending=None;self.busy=False;self.buffer=b''
        self.watchdog.stop()
        if job:
            job.blockSignals(True);job.kill();job.waitForFinished(2000);job.deleteLater()

    def timeout(self):
        self.stop();self.window.canvas.commit_pending=False
        self.window.status.setText(t('Edit preview timed out. Reading remains available.'))

    def send(self,task,**values):
        w=self.window
        if not w.session or w.canvas.mode!='edit':return
        config=dict(task=task,page=w.page_index,scale=w.canvas.factor,path=str(w.session._working),password=w.session._working_password,**values)
        revision=(id(w.session),w.page_index,w.session.position,w.session._revision,w.canvas.factor)
        if self.busy:
            self.pending=(task,values);return
        if self.job is None:
            self.job=QProcess(self);job=self.job
            job.readyReadStandardOutput.connect(self.receive)
            job.readyReadStandardError.connect(lambda:job.readAllStandardError())
            job.finished.connect(lambda *args:self.finished(job))
            args=['--edit-worker'] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parent.parent/'main.py'),'--edit-worker']
            job.start(sys.executable,args)
            if not job.waitForStarted(5000):self.timeout();return
        self.serial+=1;config['request']=self.serial
        self.request=dict(id=self.serial,revision=revision,task=task,object=values.get('object'))
        self.busy=True;self.layers={};self.watchdog.start(45000)
        self.job.write((json.dumps(config)+'\n').encode())

    def finished(self,job):
        if job is self.job:
            interrupted=self.busy
            self.job=None;self.request=None;self.busy=False;self.watchdog.stop()
            if interrupted:
                self.window.canvas.commit_pending=False
                self.window.page_object_key=None
                self.window.status.setText(t('The edit preview could not be prepared.'))
        job.deleteLater()

    def current(self,row):
        w=self.window;r=self.request
        return bool(r and row.get('request')==r['id'] and w.session and w.canvas.mode=='edit' and r['revision']==(id(w.session),w.page_index,w.session.position,w.session._revision,w.canvas.factor))

    def receive(self):
        if not self.job:return
        self.buffer+=bytes(self.job.readAllStandardOutput())
        if len(self.buffer)>52*1024*1024:self.timeout();return
        while b'\n' in self.buffer:
            data,self.buffer=self.buffer.split(b'\n',1)
            try:row=json.loads(data)
            except ValueError:self.timeout();return
            if not self.current(row):
                if row.get('kind') in ('done','error'):self.complete()
                continue
            kind=row.get('kind');w=self.window
            try:
                if kind in ('frame','layer'):
                    pix=QPixmap();raw=base64.b64decode(row['png'],validate=True)
                    if len(raw)>36*1024*1024 or not pix.loadFromData(QByteArray(raw),'PNG'):raise ValueError()
                    if pix.width()*pix.height()>9_000_000:raise ValueError()
                    if kind=='frame':w.canvas.accept_edit_frame(int(row['page']),pix,float(row['scale']))
                    else:self.layers[row['layer']]=dict(pixmap=pix,x=int(row['x']),y=int(row['y']),scale=float(row['scale']))
                elif kind=='objects':
                    objects=[]
                    for value in row['objects'][:3000]:
                        obj=PageObject(**value)
                        if len(obj.rect)!=4 or any(not __import__('math').isfinite(v) for v in obj.rect):raise ValueError()
                        objects.append(obj)
                    old=w.canvas.selected_object
                    w.canvas.set_page_objects(objects,self.request['revision'])
                    target=getattr(w.canvas,'reselect_target',None)
                    if target:
                        choices=[o for o in objects if o.kind==target[0]]
                        if choices:
                            rect=__import__('pymupdf').Rect(target[1]);w.canvas.selected_object=min(choices,key=lambda o:abs(__import__('pymupdf').Rect(o.rect).tl-rect.tl))
                            w.canvas.point_mode=getattr(w.canvas,'reselect_point_mode',False)
                            self.preview(w.canvas.selected_object)
                        w.canvas.reselect_target=None
                    w.canvas.commit_pending=False;w.canvas.paint_objects()
                elif kind=='error':
                    w.canvas.commit_pending=False;w.status.setText(t(row['message']));self.complete()
                elif kind=='done':
                    if self.request['task']=='preview' and set(self.layers)=={'before','selected','after'}:
                        w.canvas.accept_edit_preview(self.request['object'],self.layers)
                    self.complete()
            except (ValueError,TypeError,KeyError,RuntimeError):self.timeout();return

    def complete(self):
        self.busy=False;self.watchdog.stop();self.request=None
        pending=self.pending;self.pending=None;generation=self.generation
        if pending:QTimer.singleShot(0,self,lambda:self.send(pending[0],**pending[1]) if generation==self.generation else None)

    def refresh(self):
        canvas=self.window.canvas;pages=[]
        if canvas.continuous_doc is not None:
            visible=canvas.mapToScene(canvas.viewport().rect()).boundingRect()
            pages=[n for n,rect in enumerate(canvas.page_layout) if rect.intersects(visible)]
        self.send('refresh',pages=pages,ocr_words=self.window.records.get(self.window.page_index,{}).get('words',[]))

    def preview(self,obj):
        from .edit_worker import serial
        self.send('preview',object=serial(obj))
