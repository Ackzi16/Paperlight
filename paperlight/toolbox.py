"""Searchable offline tools and reusable export workflows."""
import json,os,sys,tempfile
from pathlib import Path
from PySide6.QtCore import Qt,QProcess,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,
    QPushButton,QCheckBox,QComboBox,QDoubleSpinBox,QPlainTextEdit,QFileDialog,QWidget,QSplitter,QScrollArea,QProgressBar,QMessageBox)
from .tool_catalog import TOOLS,BY_KEY,options_for
from .core import file_version
from .i18n import t

def validate_worker_message(row,planned,received):
    """Validate child-process data before updating widgets or opening a result."""
    if not isinstance(row,dict):raise ValueError('Invalid worker message')
    kind=row.get('kind')
    def number(value,low,high):return type(value) is int and low<=value<=high
    def message(value):return isinstance(value,str) and len(value)<=2048
    if kind=='progress':
        valid=number(row.get('total'),1,10000) and number(row.get('current'),0,row['total']) and message(row.get('message'))
    elif kind=='result':
        valid=isinstance(row.get('path'),str) and row['path'] in planned and row['path'] not in received and number(row.get('bytes'),0,2**63-1)
    elif kind in ('error','fatal'):valid=message(row.get('message'))
    elif kind=='done':
        valid=isinstance(row.get('outputs'),list) and row['outputs']==received and number(row.get('failures'),0,len(planned)) and len(received)+row['failures']==len(planned)
    else:valid=False
    if not valid:raise ValueError('Invalid worker message')
    return row

class ToolboxDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.job=None;self.stage=None;self.buffer=b'';self.results=[];self.steps=[];self.done_received=False
        self.setWindowTitle(t('Offline PDF tools'));self.resize(1020,780)
        root=QVBoxLayout(self)
        heading=QLabel(t('Offline PDF tools'));heading.setStyleSheet('font-size:20px;font-weight:600;');root.addWidget(heading)
        note=QLabel(t('Everything runs on this computer. Tools export copies and leave input files unchanged.'));note.setWordWrap(True);root.addWidget(note)
        self.search=QLineEdit();self.search.setPlaceholderText(t('Search PDF tools'));root.addWidget(self.search)
        split=QSplitter();root.addWidget(split,1)
        self.tools=QListWidget();self.tools.setMinimumWidth(240);split.addWidget(self.tools)
        for tool in TOOLS:
            item=QListWidgetItem(t(tool.title)+'\n'+t(tool.group));item.setData(Qt.ItemDataRole.UserRole,tool.key);self.tools.addItem(item)
        right=QWidget();body=QVBoxLayout(right);split.addWidget(right);split.setStretchFactor(1,1)
        self.description=QLabel();self.description.setWordWrap(True);body.addWidget(self.description)
        scroll=QScrollArea();self.options_scroll=scroll;scroll.setWidgetResizable(True);body.addWidget(scroll,1)
        self.parameters=QWidget();self.form=QFormLayout(self.parameters);scroll.setWidget(self.parameters);self.fields={}
        self.pages=QLineEdit();self.pages.setPlaceholderText(t('All pages, or 1-3, 7, 10-12'));self.pages_label=QLabel(t('Pages'));body.addWidget(self.pages_label);body.addWidget(self.pages)
        input_row=QHBoxLayout();self.current=QCheckBox(t('Use current document, including unsaved edits'));self.current.setChecked(bool(window.session));self.current.setEnabled(bool(window.session));input_row.addWidget(self.current)
        self.add_inputs=QPushButton(t('Add input files'));input_row.addWidget(self.add_inputs);body.addLayout(input_row)
        self.inputs=QListWidget();self.inputs.setMaximumHeight(78);self.inputs.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection);self.inputs.setDragDropMode(QListWidget.DragDropMode.InternalMove);body.addWidget(self.inputs)
        self.remove_inputs=QPushButton(t('Remove selected inputs'));body.addWidget(self.remove_inputs)
        self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);self.password.setPlaceholderText(t('Password for input PDFs, if needed'));body.addWidget(self.password)
        self.other_password=QLineEdit();self.other_password.setEchoMode(QLineEdit.EchoMode.Password);self.other_password.setPlaceholderText(t('Password for the other PDF, if needed'));body.addWidget(self.other_password)
        self.plain=QCheckBox(t('Allow unencrypted text, image or report exports from protected PDFs'));body.addWidget(self.plain)
        flow_row=QHBoxLayout();self.add_step=QPushButton(t('Add tool to workflow'));self.update_step=QPushButton(t('Update selected step'));self.save_flow=QPushButton(t('Save workflow'));self.load_flow=QPushButton(t('Load workflow'))
        for button in (self.add_step,self.update_step,self.save_flow,self.load_flow):flow_row.addWidget(button)
        body.addLayout(flow_row)
        self.workflow=QListWidget();self.workflow.setMaximumHeight(82);body.addWidget(self.workflow)
        flow_controls=QHBoxLayout();self.up=QPushButton(t('Move up'));self.down=QPushButton(t('Move down'));self.remove_step=QPushButton(t('Remove step'));self.use_workflow=QCheckBox(t('Run workflow'))
        for button in (self.up,self.down,self.remove_step,self.use_workflow):flow_controls.addWidget(button)
        body.addLayout(flow_controls)
        body.addStretch(1)
        self.progress=QProgressBar();self.progress.setRange(0,100);root.addWidget(self.progress)
        self.status=QLabel(t('Ready'));self.status.setWordWrap(True);root.addWidget(self.status)
        buttons=QHBoxLayout();self.run_button=QPushButton(t('Export'));self.open_result=QPushButton(t('Open result PDF'));self.open_result.setEnabled(False);self.close_button=QPushButton(t('Close'))
        buttons.addWidget(self.run_button);buttons.addWidget(self.open_result);buttons.addStretch();buttons.addWidget(self.close_button);root.addLayout(buttons)
        self.tools.currentItemChanged.connect(self.change_tool);self.search.textChanged.connect(self.filter_tools)
        self.add_inputs.clicked.connect(self.pick_inputs);self.remove_inputs.clicked.connect(self.remove_selected_inputs)
        self.current.toggled.connect(self.input_mode)
        self.add_step.clicked.connect(self.append_step);self.remove_step.clicked.connect(self.delete_step)
        self.update_step.clicked.connect(self.replace_step);self.workflow.itemClicked.connect(self.select_step)
        self.up.clicked.connect(lambda:self.move_step(-1));self.down.clicked.connect(lambda:self.move_step(1))
        self.save_flow.clicked.connect(self.save_recipe);self.load_flow.clicked.connect(self.load_recipe)
        self.use_workflow.toggled.connect(self.input_mode)
        self.run_button.clicked.connect(self.start);self.close_button.clicked.connect(self.reject);self.open_result.clicked.connect(self.open_pdf_result)
        self.watchdog=QTimer(self);self.watchdog.setSingleShot(True);self.watchdog.timeout.connect(self.timed_out)
        self.tools.setCurrentRow(0);self.input_mode();self.refresh_steps()

    def selected_tool(self):
        return BY_KEY[self.tools.currentItem().data(Qt.ItemDataRole.UserRole)]

    def filter_tools(self,text):
        text=text.casefold();first=None
        for n in range(self.tools.count()):
            item=self.tools.item(n);tool=BY_KEY[item.data(Qt.ItemDataRole.UserRole)]
            item.setHidden(text not in (item.text()+' '+tool.description+' '+tool.key).casefold())
            if not item.isHidden() and first is None:first=n
        if self.tools.currentItem().isHidden() and first is not None:self.tools.setCurrentRow(first)

    def change_tool(self,*args):
        if not self.tools.currentItem():return
        while self.form.rowCount():self.form.removeRow(0)
        self.fields={};tool=self.selected_tool();self.description.setText(t(tool.description));self.pages.setEnabled(tool.pages);self.pages.setVisible(tool.pages);self.pages_label.setVisible(tool.pages);self.options_scroll.setVisible(bool(tool.options))
        for option in tool.options:
            if option.kind=='number':
                widget=QDoubleSpinBox();widget.setRange(option.minimum,option.maximum);widget.setDecimals(0 if option.key in ('dpi','quality','start','count','before','columns','rows','opacity','contrast') else 1);widget.setValue(option.default)
            elif option.kind=='choice':
                widget=QComboBox()
                for value in option.choices:widget.addItem(t(str(value)),value)
                widget.setCurrentIndex(max(0,widget.findData(option.default)))
            elif option.kind=='check':widget=QCheckBox();widget.setChecked(option.default)
            elif option.kind=='multiline':
                widget=QPlainTextEdit();widget.setMaximumHeight(115);widget.setPlaceholderText('1 | 1 | Introduction')
                if tool.key=='bookmarks' and self.window.session:widget.setPlainText('\n'.join(f'{level} | {page} | {title}' for level,title,page in self.window.session.doc.get_toc()))
            else:
                widget=QLineEdit(str(option.default))
                if tool.key=='metadata' and self.window.session:widget.setText(self.window.session.doc.metadata.get(option.key,''))
            self.fields[option.key]=widget
            if option.kind=='file':
                row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.addWidget(widget);pick=QPushButton(t('Browse'));layout.addWidget(pick)
                pick.clicked.connect(lambda checked=False,w=widget:self.pick_other(w));self.form.addRow(t(option.label),row)
            else:self.form.addRow(t(option.label),widget)
        self.options_scroll.setMaximumHeight(max(90,min(300,self.form.sizeHint().height()+20)))
        self.add_step.setEnabled(tool.workflow);self.other_password.setVisible(tool.key in ('compare','overlay'));self.input_mode()

    def input_mode(self,*args):
        images=bool(self.tools.currentItem() and self.selected_tool().key=='images_pdf')
        self.current.setEnabled(bool(self.window.session) and not images)
        external=images or not self.current.isChecked()
        self.inputs.setEnabled(external);self.inputs.setVisible(external);self.add_inputs.setEnabled(external);self.remove_inputs.setEnabled(external);self.remove_inputs.setVisible(external);self.password.setVisible(external and not images)
        self.plain.setVisible(self.selected_tool().output!='pdf' and not self.use_workflow.isChecked())

    def pick_inputs(self):
        images=self.selected_tool().key=='images_pdf'
        names,_=QFileDialog.getOpenFileNames(self,t('Choose input files'),'',t('Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp)') if images else 'PDF (*.pdf)')
        if names:
            for n in reversed(range(self.inputs.count())):
                is_pdf=Path(self.inputs.item(n).data(Qt.ItemDataRole.UserRole)).suffix.lower()=='.pdf'
                if is_pdf==images:self.inputs.takeItem(n)
        for name in names:
            if not any(self.inputs.item(n).data(Qt.ItemDataRole.UserRole)==name for n in range(self.inputs.count())):
                item=QListWidgetItem(Path(name).name);item.setData(Qt.ItemDataRole.UserRole,name);item.setToolTip(name);self.inputs.addItem(item)

    def remove_selected_inputs(self):
        for item in self.inputs.selectedItems():self.inputs.takeItem(self.inputs.row(item))

    def pick_other(self,field):
        name,_=QFileDialog.getOpenFileName(self,t('Choose another PDF'),'','PDF (*.pdf)')
        if name:field.setText(name)

    def values(self):
        values={}
        for option in self.selected_tool().options:
            widget=self.fields[option.key]
            values[option.key]=widget.value() if option.kind=='number' else widget.currentData() if option.kind=='choice' else widget.isChecked() if option.kind=='check' else widget.toPlainText() if option.kind=='multiline' else widget.text()
        return options_for(self.selected_tool(),values)

    def refresh_steps(self):
        self.workflow.clear()
        for n,step in enumerate(self.steps):self.workflow.addItem(f'{n+1}. '+t(BY_KEY[step['tool']].title))
        self.workflow.setVisible(bool(self.steps))
        for button in (self.up,self.down,self.remove_step,self.update_step):button.setVisible(bool(self.steps))

    def append_step(self):
        if len(self.steps)>=30:self.status.setText(t('A workflow supports at most 30 steps.'));return
        tool=self.selected_tool()
        if tool.workflow:
            self.steps.append(dict(tool=tool.key,options=self.values(),pages=self.pages.text().strip() if tool.pages else ''));self.refresh_steps();self.use_workflow.setChecked(True)

    def delete_step(self):
        row=self.workflow.currentRow()
        if 0<=row<len(self.steps):self.steps.pop(row);self.refresh_steps()

    def select_step(self,item):
        row=self.workflow.row(item)
        if not 0<=row<len(self.steps):return
        step=self.steps[row];self.tools.setCurrentRow(next(n for n,tool in enumerate(TOOLS) if tool.key==step['tool']))
        for option in self.selected_tool().options:
            widget=self.fields[option.key];value=step['options'].get(option.key,option.default)
            if option.kind=='number':widget.setValue(value)
            elif option.kind=='choice':widget.setCurrentIndex(max(0,widget.findData(value)))
            elif option.kind=='check':widget.setChecked(value)
            elif option.kind=='multiline':widget.setPlainText(value)
            else:widget.setText(value)
        self.pages.setText(step.get('pages',''))

    def replace_step(self):
        row=self.workflow.currentRow();tool=self.selected_tool()
        if 0<=row<len(self.steps) and tool.workflow:
            self.steps[row]=dict(tool=tool.key,options=self.values(),pages=self.pages.text().strip() if tool.pages else '')
            self.refresh_steps();self.workflow.setCurrentRow(row)

    def move_step(self,delta):
        row=self.workflow.currentRow();target=row+delta
        if 0<=row<len(self.steps) and 0<=target<len(self.steps):self.steps[row],self.steps[target]=self.steps[target],self.steps[row];self.refresh_steps();self.workflow.setCurrentRow(target)

    def save_recipe(self):
        if not self.steps:return
        name,_=QFileDialog.getSaveFileName(self,t('Save workflow'),'Paperlight-workflow.json','JSON (*.json)')
        if name:
            # File-specific paths and passwords are deliberately not portable.
            steps=[dict(s,options={k:v for k,v in s['options'].items() if k!='other'}) for s in self.steps]
            try:Path(name).write_text(json.dumps(dict(version=1,steps=steps),ensure_ascii=False,indent=2),encoding='utf-8');self.status.setText(t('Workflow saved without PDF paths or passwords.'))
            except OSError:self.status.setText(t('Could not save the workflow.'))

    def load_recipe(self):
        name,_=QFileDialog.getOpenFileName(self,t('Load workflow'),'','JSON (*.json)')
        if not name:return
        try:
            if Path(name).stat().st_size>1024*1024:raise ValueError()
            data=json.loads(Path(name).read_text(encoding='utf-8'))
            if data.get('version')!=1 or not isinstance(data.get('steps'),list) or not 1<=len(data['steps'])<=30:raise ValueError()
            steps=[]
            for step in data['steps']:
                tool=BY_KEY[step['tool']]
                if not tool.workflow or not isinstance(step.get('pages',''),str) or len(step.get('pages',''))>4096:raise ValueError()
                values=options_for(tool,step.get('options',{}))
                if 'other' in values:values['other']=''
                steps.append(dict(tool=tool.key,options=values,pages=step.get('pages','')))
            self.steps=steps;self.refresh_steps();self.use_workflow.setChecked(True)
            self.status.setText(t('Workflow loaded. File paths and passwords must be chosen again.'))
        except (OSError,ValueError,TypeError,KeyError):self.status.setText(t('This workflow is invalid or unsupported.'))

    def start(self):
        if self.job:return
        tool=self.selected_tool();flow=self.steps if self.use_workflow.isChecked() else []
        if self.use_workflow.isChecked() and not flow:self.status.setText(t('Add at least one workflow step.'));return
        if flow and tool.key=='images_pdf':self.status.setText(t('Choose a PDF tool before running a PDF workflow.'));return
        current=self.current.isChecked() and tool.key!='images_pdf';session=self.window.session
        inputs=[str(session._working)] if current else [self.inputs.item(n).data(Qt.ItemDataRole.UserRole) for n in range(self.inputs.count())]
        if not 1<=len(inputs)<=100:self.status.setText(t('Choose between 1 and 100 input files.'));return
        if current and session.pending_redactions():self.status.setText(t('Apply or undo pending redactions before exporting tools results.'));return
        output_type='pdf' if flow else tool.output
        count=1 if tool.key=='images_pdf' else len(inputs)
        outputs=[]
        if count==1:
            base=Path(session.path if current else inputs[0]).stem
            name,_=QFileDialog.getSaveFileName(self,t('Export tool result'),base+'-'+('workflow' if flow else tool.key)+'.'+output_type,output_type.upper()+' (*.'+output_type+')')
            if not name:return
            destination=Path(name)
            if destination.suffix.lower()!='.'+output_type:destination=destination.with_suffix('.'+output_type)
            outputs=[dict(path=str(destination),expected=file_version(destination) if destination.exists() else None)]
        else:
            directory=QFileDialog.getExistingDirectory(self,t('Choose output folder'))
            if not directory:return
            used=set()
            for source in inputs:
                stem=Path(source).stem+'-'+('workflow' if flow else tool.key);n=1;destination=Path(directory)/(stem+'.'+output_type)
                while destination.exists() or str(destination).casefold() in used:
                    n+=1;destination=Path(directory)/(stem+f'-{n}.'+output_type)
                used.add(str(destination).casefold());outputs.append(dict(path=str(destination),expected=None))
        try:
            self.stage=tempfile.TemporaryDirectory(prefix='.paperlight-tool-',dir=str(Path(outputs[0]['path']).parent))
            config=dict(tool=tool.key,options=self.values(),inputs=inputs,outputs=outputs,stage=self.stage.name,pages=self.pages.text().strip(),workflow=flow,
                        password=session._working_password if current else self.password.text(),other_password=self.other_password.text(),allow_plaintext=self.plain.isChecked(),
                        current_document=current,original_encrypted=session.encrypted if current else False,original_paths=[session.path] if current else [],
                        redaction_applied=session.redaction_applied if current else False,clean_content=session.native_object_edited if current else False)
            self.planned_outputs={str(Path(output['path']).resolve()) for output in outputs}
            self.results=[];self.errors=[];self.buffer=b'';self.done_received=False;self.open_result.setEnabled(False);self.run_button.setEnabled(False);self.search.setEnabled(False);self.tools.setEnabled(False)
            self.job=QProcess(self);job=self.job;job.readyReadStandardOutput.connect(self.receive);job.readyReadStandardError.connect(lambda:job.readAllStandardError());job.finished.connect(self.job_finished)
            args=['--toolbox-worker'] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parent.parent/'main.py'),'--toolbox-worker']
            job.start(sys.executable,args)
            if not job.waitForStarted(5000):raise ValueError()
            job.write((json.dumps(config)+'\n').encode());job.closeWriteChannel();self.watchdog.start(120000);self.close_button.setText(t('Cancel job'));self.status.setText(t('Processing locally…'))
        except Exception:
            self.stop();self.status.setText(t('The toolbox job could not be started. Check the inputs and options.'))

    def receive(self):
        if not self.job:return
        self.buffer+=bytes(self.job.readAllStandardOutput())
        if len(self.buffer)>2*1024*1024:self.timed_out();return
        while b'\n' in self.buffer:
            raw,self.buffer=self.buffer.split(b'\n',1)
            try:
                if self.done_received:raise ValueError()
                row=validate_worker_message(json.loads(raw),self.planned_outputs,self.results)
            except (ValueError,TypeError,RecursionError):
                self.stop();self.status.setText(t('The toolbox worker returned invalid data.'));return
            self.watchdog.start(120000)
            if row['kind']=='progress':self.progress.setValue(round(100*row['current']/max(1,row['total'])));self.status.setText(t(row['message'])+f" {row['current']} / {row['total']}")
            elif row['kind']=='result':self.results.append(row['path'])
            elif row['kind'] in ('error','fatal'):
                self.errors.append(t(row['message']));self.status.setText(t(row['message']))
            elif row['kind']=='done':
                self.done_received=True;self.progress.setValue(100)
                summary=t('{0} files exported; {1} failed. Input files were not changed.').format(len(row['outputs']),row['failures'])
                self.status.setText(summary+ ('\n'+self.errors[0] if self.errors else ''));self.status.setToolTip('\n'.join(self.errors))

    def job_finished(self,*args):
        job=self.job
        if job:
            self.receive()
            if self.job is job:self.job=None;job.deleteLater()
        self.watchdog.stop()
        if self.stage:self.stage.cleanup();self.stage=None
        self.run_button.setEnabled(True);self.search.setEnabled(True);self.tools.setEnabled(True);self.close_button.setText(t('Close'));self.open_result.setEnabled(len(self.results)==1 and self.results[0].lower().endswith('.pdf'))
        if not self.done_received:self.status.setText(t('The job stopped. Completed exports, if any, were kept.'))

    def stop(self):
        if self.job:
            self.job.blockSignals(True);self.job.kill();self.job.waitForFinished(3000);self.job.deleteLater();self.job=None
        self.watchdog.stop()
        if self.stage:self.stage.cleanup();self.stage=None
        self.run_button.setEnabled(True);self.search.setEnabled(True);self.tools.setEnabled(True);self.close_button.setText(t('Close'))

    def timed_out(self):self.stop();self.status.setText(t('The job stopped after two minutes without progress. Completed exports were kept.'))

    def reject(self):
        if self.job:
            self.stop();self.status.setText(t('Cancelled. Completed exports were kept.'));return
        super().reject()

    def closeEvent(self,event):
        if self.job:self.stop()
        event.accept()

    def open_pdf_result(self):
        if len(self.results)==1:self.accept();self.window.open_path(self.results[0])
