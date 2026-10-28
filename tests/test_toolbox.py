import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import io,json,zipfile
from pathlib import Path
import pymupdf as f
import pytest
from PIL import Image
from paperlight.tool_catalog import TOOLS,BY_KEY,options_for
from paperlight.tool_engine import execute,transform,extract,csv_cell
from paperlight.core import PdfSession
from paperlight.security import Protection,access
from paperlight.app import Window
from paperlight.toolbox import ToolboxDialog,validate_worker_message
from .test_ui import app,wait_for

@pytest.fixture
def utility_pdf(tmp_path):
    path=tmp_path/'utilities.pdf'
    with f.open() as doc:
        p=doc.new_page(width=420,height=600);p.insert_text((50,65),'First page ALPHA',fontsize=16);p.insert_text((50,95),'中文测试',fontname='china-s')
        image=Image.new('RGB',(200,100),(50,100,180));stream=io.BytesIO();image.save(stream,format='PNG');p.insert_image((50,140,250,240),stream=stream.getvalue())
        field=f.Widget();field.field_name='customer';field.field_value='Retained value';field.field_type=f.PDF_WIDGET_TYPE_TEXT;field.rect=f.Rect(50,270,280,300);field.field_flags=f.PDF_FIELD_IS_READ_ONLY;p.add_widget(field)
        p.add_text_annot((300,80),'Synthetic comment')
        p.insert_link({'kind':f.LINK_URI,'from':f.Rect(50,310,150,330),'uri':'https://example.com'})
        p=doc.new_page(width=420,height=600);p.insert_text((50,65),'Second page BETA',fontsize=16)
        for x in (50,150,250):p.draw_line((x,130),(x,210))
        for y in (130,170,210):p.draw_line((50,y),(250,y))
        for point,text in (((60,155),'Name'),((160,155),'Value'),((60,195),'Item'),((160,195),'42')):p.insert_text(point,text)
        doc.new_page(width=420,height=600)
        p=doc.new_page(width=420,height=600);p.insert_text((50,65),'Rotated GAMMA',fontsize=16);p.set_rotation(90)
        doc.set_toc([[1,'First section',1],[1,'Second section',2]]);doc.set_metadata(dict(title='Synthetic utilities',author='Paperlight tests'))
        doc.embfile_add('fixture.txt',b'Harmless synthetic attachment')
        action=doc.get_new_xref();doc.update_object(action,r'<< /S /JavaScript /JS (app.alert\(1\)) >>');doc.xref_set_key(doc.pdf_catalog(),'OpenAction',f'{action} 0 R')
        doc.save(path)
    return path

def job(tmp_path,source,key,options=None,**extras):
    output=tmp_path/(key+'-result.'+BY_KEY[key].output);stage=tmp_path/('stage-'+key);stage.mkdir(exist_ok=True)
    config=dict(tool=key,inputs=[str(source)],outputs=[dict(path=str(output))],options=options or {},stage=str(stage),**extras)
    rows=[];execute(config,rows.append);return output,rows

def success(rows):
    assert rows[-1]['kind']=='done' and rows[-1]['failures']==0,rows


@pytest.mark.parametrize('fail',[False,True])
def test_staging_never_modifies_existing_files(tmp_path,utility_pdf,fail):
    source=tmp_path/'result-0000.pdf';source.write_bytes(utility_pdf.read_bytes())
    original=source.read_bytes();output=tmp_path/'export.pdf';rows=[]
    if fail:output.write_bytes(b'Existing output')
    execute(dict(tool='compress',inputs=[str(source)],outputs=[dict(path=str(output))],stage=str(tmp_path)),rows.append)
    assert source.read_bytes()==original
    assert rows[-1]['failures']==int(fail) and not list(tmp_path.glob('.job-*'))
    if fail:assert output.read_bytes()==b'Existing output'
    else:
        with f.open(output) as doc:assert doc[0].search_for('ALPHA')


@pytest.mark.parametrize('row',[
    [],{},dict(kind='progress',current=1,total=0,message='x'),
    dict(kind='progress',current=True,total=1,message='x'),
    dict(kind='progress',current=1,total=1,message='x'*2049),
    dict(kind='result',path='unrequested.pdf',bytes=10),
    dict(kind='result',path='allowed.pdf',bytes=-1),
    dict(kind='done',outputs=['unrequested.pdf'],failures=0),
    dict(kind='done',outputs=[],failures=0),dict(kind='fatal',message=[]),
])
def test_worker_protocol_rejects_malformed_or_unrequested_output(row):
    with pytest.raises(ValueError):validate_worker_message(row,{'allowed.pdf'},[])


def test_worker_protocol_accepts_expected_results_and_rejects_duplicates():
    result=dict(kind='result',path='allowed.pdf',bytes=42)
    assert validate_worker_message(result,{'allowed.pdf'},[])==result
    with pytest.raises(ValueError):validate_worker_message(result,{'allowed.pdf'},['allowed.pdf'])
    validate_worker_message(dict(kind='done',outputs=['allowed.pdf'],failures=0),{'allowed.pdf'},['allowed.pdf'])

@pytest.mark.parametrize('key',[t.key for t in TOOLS if t.workflow])
def test_pdf_transformations_export_and_preserve_input(tmp_path,utility_pdf,key):
    original=utility_pdf.read_bytes();options={}
    if key=='metadata':options={'title':'Updated title'}
    elif key=='bookmarks':options={'bookmarks':'1 | 1 | Chapter one\n2 | 2 | Details'}
    elif key=='overlay':options={'other':str(utility_pdf)}
    elif key in ('grayscale','invert','contrast'):options={'dpi':72}
    extras={'pages':'1-2'} if key=='keep_pages' else {'pages':'3'} if key=='remove_pages' else {}
    output,rows=job(tmp_path,utility_pdf,key,options,**extras);success(rows)
    assert utility_pdf.read_bytes()==original
    with f.open(output) as doc:
        expected={'blank':5,'duplicate':8,'blank_pages':3,'resize':4,'nup':1,'booklet':2,'tiles':8,'long_page':1,'keep_pages':2,'remove_pages':3}
        assert len(doc)==expected.get(key,4)
        text=''.join(p.get_text() for p in doc)
        if key not in ('images','crop','tiles'):assert 'ALPHA' in text
        if key=='metadata':assert doc.metadata['title']=='Updated title' and doc.metadata['author']=='Paperlight tests'
        if key=='bookmarks':assert doc.get_toc()==[[1,'Chapter one',1],[2,'Details',2]]
        if key=='reverse':assert 'GAMMA' in doc[0].get_text()
        if key=='duplicate':assert next(doc[4].widgets()).field_value=='Retained value'
        if key=='numbers':assert '1 / 4' in doc[0].get_text()
        if key=='watermark':assert 'DRAFT' in doc[0].get_text()
        if key=='flatten':assert not list(doc[0].widgets() or []) and not list(doc[0].annots() or []) and 'Retained value' in text
        if key=='annotations':assert not list(doc[0].annots() or []) and list(doc[0].widgets())
        if key=='unlock_forms':assert not next(doc[0].widgets()).field_flags & f.PDF_FIELD_IS_READ_ONLY
        if key=='clear_metadata':assert not doc.metadata['title'] and doc.get_toc()
        if key=='sanitize':
            assert doc.embfile_count()==0 and not doc.metadata['title'] and not doc[0].get_links()
            assert doc.xref_get_key(doc.pdf_catalog(),'OpenAction')[0]=='null'
            assert next(doc[0].widgets()).field_value=='Retained value'
        if key in ('grayscale','invert','contrast'):assert '中文' in text and doc.get_toc()

@pytest.mark.parametrize('key',['text','compare','info','pdf_images','extract_images','tables'])
def test_extractions(tmp_path,utility_pdf,key):
    options={'other':str(utility_pdf)} if key=='compare' else {'dpi':72} if key=='pdf_images' else {}
    output,rows=job(tmp_path,utility_pdf,key,options);success(rows)
    if key=='text':assert '中文' in output.read_text(encoding='utf-8') and 'BETA' in output.read_text(encoding='utf-8')
    elif key=='compare':assert 'No text differences' in output.read_text()
    elif key=='info':assert json.loads(output.read_text(encoding='utf-8'))['pages']==4
    else:
        with zipfile.ZipFile(output) as archive:
            assert archive.namelist()
            assert all('..' not in name and not name.startswith('/') for name in archive.namelist())
            if key=='tables':assert any(name.endswith('.csv') for name in archive.namelist())

def test_images_pdf_tiff_frames_and_workflow(tmp_path,utility_pdf):
    image=tmp_path/'frames.tiff';Image.new('RGB',(80,60),'red').save(image,save_all=True,append_images=[Image.new('RGB',(80,60),'blue')])
    output,rows=job(tmp_path,image,'images_pdf');success(rows)
    with f.open(output) as doc:assert len(doc)==2
    workflow=[dict(tool='metadata',options={'title':'Workflow output'}),dict(tool='reverse'),dict(tool='numbers',options={'text':'P{number}'})]
    output,rows=job(tmp_path,utility_pdf,'compress',workflow=workflow);success(rows)
    with f.open(output) as doc:assert doc.metadata['title']=='Workflow output' and 'GAMMA' in doc[0].get_text() and 'P1' in doc[0].get_text()

def test_protection_preserved_and_restrictions_enforced(tmp_path,utility_pdf):
    protected=tmp_path/'protected.pdf';session=PdfSession(str(utility_pdf));session.save(protected,Protection('Owner pass','Reader pass'));session.close()
    output,rows=job(tmp_path,protected,'resize',password='Reader pass');assert rows[-1]['failures']==1 and not output.exists()
    output,rows=job(tmp_path,protected,'resize',password='Owner pass');success(rows)
    with f.open(output) as doc:
        assert doc.needs_pass and doc.authenticate('Reader pass')
        assert access(doc,'Owner pass')[1] is False and 'ALPHA' in doc[0].get_text()
    output,rows=job(tmp_path,protected,'text',password='Reader pass');assert rows[-1]['failures']==1 and not output.exists()
    output,rows=job(tmp_path,protected,'text',password='Reader pass',allow_plaintext=True);success(rows)
    assert 'ALPHA' in output.read_text(encoding='utf-8')

def test_current_unsaved_export_and_no_input_overwrite(tmp_path,utility_pdf):
    session=PdfSession(str(utility_pdf))
    try:
        with session.operation('Unsaved fixture'):session.doc[0].insert_text((50,400),'UNSAVED CONTENT')
        output,rows=job(tmp_path,session._working,'compress',password=session._working_password,current_document=True,original_encrypted=False,original_paths=[str(utility_pdf)])
        success(rows)
        with f.open(output) as doc:assert not doc.needs_pass and not doc.metadata.get('encryption') and 'UNSAVED' in doc[0].get_text()
        report,rows=job(tmp_path,session._working,'info',password=session._working_password,current_document=True,original_encrypted=False,original_paths=[str(utility_pdf)])
        success(rows);data=json.loads(report.read_text(encoding='utf-8'));assert data['encrypted'] is False and data['metadata']['encryption'] is None
        original=utility_pdf.read_bytes();stage=tmp_path/'same-stage';stage.mkdir()
        rows=[];execute(dict(tool='compress',inputs=[str(utility_pdf)],outputs=[dict(path=str(utility_pdf))],stage=str(stage)),rows.append)
        assert rows[-1]['failures']==1 and utility_pdf.read_bytes()==original
    finally:session.close()

def test_pending_redactions_fail_closed_and_batch_keeps_success(tmp_path,utility_pdf):
    pending=tmp_path/'pending.pdf'
    with f.open(utility_pdf) as doc:doc[0].add_redact_annot((40,40,200,90));doc.save(pending)
    output,rows=job(tmp_path,pending,'flatten');assert rows[-1]['failures']==1 and not output.exists()
    stage=tmp_path/'batch-stage';stage.mkdir();outputs=[tmp_path/'batch-good.pdf',tmp_path/'batch-bad.pdf'];rows=[]
    execute(dict(tool='compress',inputs=[str(utility_pdf),str(pending)],outputs=[dict(path=str(p)) for p in outputs],stage=str(stage)),rows.append)
    assert rows[-1]['failures']==1 and outputs[0].exists() and not outputs[1].exists()

def test_csv_cells_do_not_become_formulas():
    assert csv_cell('=HYPERLINK("file")').startswith("'") and csv_cell('@SUM(A1)')[0]=="'" and csv_cell('42')=='42'

def test_crop_is_not_redaction_and_repair_rebuilds_xref(tmp_path,utility_pdf):
    output,rows=job(tmp_path,utility_pdf,'crop',{'left':200});success(rows)
    with f.open(output) as doc:
        doc[0].set_cropbox(doc[0].mediabox)
        assert doc[0].search_for('ALPHA')
    import re
    damaged=tmp_path/'damaged.pdf';damaged.write_bytes(re.sub(rb'startxref\s+\d+',b'startxref\n0',utility_pdf.read_bytes()))
    with f.open(damaged) as doc:assert doc.is_repaired
    output,rows=job(tmp_path,damaged,'repair');success(rows)
    with f.open(output) as doc:assert not doc.is_repaired and doc[0].search_for('ALPHA')

def test_workflow_failure_and_output_collision_are_atomic(tmp_path,utility_pdf):
    output=tmp_path/'compress-result.pdf';output.write_bytes(b'Existing file')
    _,rows=job(tmp_path,utility_pdf,'compress');assert rows[-1]['failures']==1 and output.read_bytes()==b'Existing file'
    output.unlink()
    workflow=[dict(tool='metadata',options={'title':'Not committed'}),dict(tool='crop',options={'left':2000})]
    _,rows=job(tmp_path,utility_pdf,'compress',workflow=workflow);assert rows[-1]['failures']==1 and not output.exists()

def test_recipe_privacy_editing_and_cancel_cleanup(app,tmp_path,utility_pdf,monkeypatch):
    window=Window();window.show();window.open_path(str(utility_pdf));wait_for(lambda:window.job is None)
    try:
        dialog=ToolboxDialog(window);dialog.show()
        dialog.tools.setCurrentRow(next(n for n,t in enumerate(TOOLS) if t.key=='overlay'));dialog.fields['other'].setText(str(utility_pdf));dialog.append_step()
        recipe=tmp_path/'recipe.json';monkeypatch.setattr('paperlight.toolbox.QFileDialog.getSaveFileName',lambda *a,**k:(str(recipe),'JSON'));dialog.save_recipe()
        data=json.loads(recipe.read_text(encoding='utf-8'));assert 'other' not in data['steps'][0]['options'] and str(utility_pdf) not in recipe.read_text(encoding='utf-8')
        dialog.workflow.setCurrentRow(0);dialog.select_step(dialog.workflow.item(0));dialog.fields['other'].setText('');dialog.replace_step();assert dialog.steps[0]['options']['other']==''
        monkeypatch.setattr('paperlight.toolbox.QFileDialog.getOpenFileName',lambda *a,**k:(str(recipe),'JSON'));dialog.load_recipe();assert dialog.steps[0]['options']['other']==''
        dialog.use_workflow.setChecked(False);dialog.tools.setCurrentRow(0)
        output=tmp_path/'cancelled.pdf';monkeypatch.setattr('paperlight.toolbox.QFileDialog.getSaveFileName',lambda *a,**k:(str(output),'PDF'))
        original=utility_pdf.read_bytes();dialog.start();assert dialog.job is not None;dialog.stop()
        assert dialog.job is None and dialog.stage is None and not list(tmp_path.glob('.paperlight-tool-*')) and utility_pdf.read_bytes()==original
        dialog.close()
    finally:window.close()

def test_tool_catalog_has_chinese_interface():
    from paperlight.i18n import t
    for tool in TOOLS:
        assert t(tool.title,'zh_CN')!=tool.title and t(tool.description,'zh_CN')!=tool.description
        for option in tool.options:assert t(option.label,'zh_CN')!=option.label

def test_sanitize_preserves_font_resource_names_and_removes_external_actions(tmp_path,utility_pdf):
    source=tmp_path/'named-font.pdf'
    with f.open(utility_pdf) as doc:
        page=doc[0];font=next(row[0] for row in page.get_fonts() if row[4]=='helv')
        resources=int(doc.xref_get_key(page.xref,'Resources')[1].split()[0])
        doc.xref_set_key(resources,'Font/AA',f'{font} 0 R')
        for xref in page.get_contents():doc.update_stream(xref,doc.xref_stream(xref).replace(b'/helv',b'/AA'))
        action=doc.get_new_xref();doc.update_object(action,'<< /S /URI /URI (https://example.com) >>')
        annot=next(page.annots());doc.xref_set_key(annot.xref,'A',f'{action} 0 R');doc.save(source)
    output,rows=job(tmp_path,source,'sanitize');success(rows)
    with f.open(output) as doc:
        assert any(row[4]=='AA' for row in doc[0].get_fonts()) and doc[0].search_for('ALPHA')
        assert not any(doc.xref_get_key(xref,'S')==('name','/URI') for xref in range(1,doc.xref_length()))

def test_worker_protocol_excludes_library_advisories(tmp_path,utility_pdf):
    import subprocess,sys
    output=tmp_path/'table-protocol.zip'
    config=dict(tool='tables',inputs=[str(utility_pdf)],outputs=[dict(path=str(output))],stage=str(tmp_path),options={})
    process=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'main.py'),'--toolbox-worker'],input=json.dumps(config)+'\n',text=True,capture_output=True,timeout=30)
    assert process.returncode==0 and not process.stderr
    rows=[json.loads(line) for line in process.stdout.splitlines()]
    success(rows)
    with zipfile.ZipFile(output) as archive:assert any(n.endswith('.csv') for n in archive.namelist())

def test_image_recompression_accepts_ui_numbers_and_retains_text(tmp_path):
    source=tmp_path/'high-dpi.pdf';image=Image.new('RGB',(1600,800),(30,90,170));stream=io.BytesIO();image.save(stream,format='PNG')
    with f.open() as doc:
        page=doc.new_page();page.insert_text((50,80),'Native text stays searchable');page.insert_image((50,120,250,220),stream=stream.getvalue());doc.save(source)
    original=source.read_bytes();output,rows=job(tmp_path,source,'compress',dict(images=True,dpi=72.0,quality=65.0));success(rows)
    assert source.read_bytes()==original
    with f.open(output) as doc:
        assert doc[0].search_for('searchable')
        assert max(row[2] for row in doc[0].get_images())<1600

def test_toolbox_search_and_separate_worker(app,tmp_path,utility_pdf,monkeypatch):
    window=Window();window.show();window.open_path(str(utility_pdf));wait_for(lambda:window.job is None)
    try:
        window.stop_index();dialog=ToolboxDialog(window);dialog.show()
        dialog.search.setText('watermark');assert sum(not dialog.tools.item(n).isHidden() for n in range(dialog.tools.count()))==1
        dialog.search.clear();dialog.tools.setCurrentRow(next(n for n,t in enumerate(TOOLS) if t.key=='text'))
        output=tmp_path/'ui-text.txt';monkeypatch.setattr('paperlight.toolbox.QFileDialog.getSaveFileName',lambda *a,**k:(str(output),'TXT'))
        dialog.start();wait_for(lambda:dialog.job is None,20000)
        assert output.exists() and 'ALPHA' in output.read_text(encoding='utf-8') and not window.session.dirty
        assert dialog.stage is None and not list(tmp_path.glob('.paperlight-tool-*'))
        dialog.close()
    finally:window.close()
