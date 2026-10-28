"""Exercise all native tools through the frozen worker, using synthetic files."""
import json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from paperlight.tool_catalog import TOOLS
from paperlight.core import PdfSession
from paperlight.security import Protection
from tests.test_toolbox import utility_pdf
from PIL import Image
import pymupdf as f

exe=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'dist/Paperlight/Paperlight.exe'
report=dict(executable=str(exe),tools=[],encrypted_layout_export=False)
with tempfile.TemporaryDirectory(prefix='toolbox-verify-',dir=ROOT/'tmp/verification') as temporary:
    folder=Path(temporary);source=utility_pdf.__wrapped__(folder);original=source.read_bytes()
    image=folder/'frames.tiff';Image.new('RGB',(80,60),'red').save(image,save_all=True,append_images=[Image.new('RGB',(80,60),'blue')])
    def run(config):
        process=subprocess.run([str(exe),'--toolbox-worker'],input=json.dumps(config)+'\n',capture_output=True,encoding='utf-8',timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
        assert process.returncode==0,process.stderr
        rows=[json.loads(line) for line in process.stdout.splitlines()]
        assert rows and rows[-1]['kind']=='done' and rows[-1]['failures']==0,rows
    for tool in TOOLS:
        options={};pages=''
        if tool.key in ('compare','overlay'):options={'other':str(source)}
        elif tool.key=='metadata':options={'title':'Packaged toolbox'}
        elif tool.key=='bookmarks':options={'bookmarks':'1 | 1 | First chapter'}
        elif tool.key in ('pdf_images','grayscale','invert','contrast'):options={'dpi':72}
        if tool.key=='keep_pages':pages='1-2'
        elif tool.key=='remove_pages':pages='3'
        output=folder/(tool.key+'.'+tool.output)
        config=dict(tool=tool.key,options=options,inputs=[str(image if tool.key=='images_pdf' else source)],outputs=[dict(path=str(output))],stage=str(folder),pages=pages)
        run(config);assert output.stat().st_size>0 and source.read_bytes()==original
        if tool.output=='pdf':
            with f.open(output) as doc:assert len(doc)>0
        elif tool.output=='zip':
            with zipfile.ZipFile(output) as archive:
                assert archive.testzip() is None
                if tool.key=='tables':assert any(n.endswith('.csv') for n in archive.namelist())
        report['tools'].append(tool.key)
    protected=folder/'protected.pdf';session=PdfSession(str(source));session.save(protected,Protection('Tool-owner','Tool-reader'));session.close()
    output=folder/'protected-layout.pdf'
    run(dict(tool='nup',options={},inputs=[str(protected)],outputs=[dict(path=str(output))],stage=str(folder),password='Tool-owner'))
    with f.open(output) as doc:assert doc.needs_pass and doc.authenticate('Tool-reader') and doc[0].search_for('ALPHA')
    report['encrypted_layout_export']=True
    output=folder/'workflow.pdf';second=folder/'workflow-2.pdf'
    run(dict(tool='compress',options={},inputs=[str(source),str(source)],outputs=[dict(path=str(output)),dict(path=str(second))],stage=str(folder),workflow=[dict(tool='rotate',options={'degrees':90}),dict(tool='numbers',options={}),dict(tool='compress',options={})]))
    with f.open(output) as doc:assert doc[0].rotation==90
    report['batch_workflow']=True
    output=folder/'compressed-images.pdf'
    run(dict(tool='compress',options=dict(images=True,dpi=72,quality=65),inputs=[str(source)],outputs=[dict(path=str(output))],stage=str(folder)))
    with f.open(output) as doc:assert doc[0].search_for('ALPHA')
    report['image_recompression']=True
    output=folder/'jpeg-pages.zip'
    run(dict(tool='pdf_images',options=dict(format='JPEG',dpi=72),inputs=[str(source)],outputs=[dict(path=str(output))],stage=str(folder)))
    with zipfile.ZipFile(output) as archive:assert any(n.endswith('.jpg') for n in archive.namelist())
    report['jpeg_export']=True
report['tool_count']=len(report['tools'])
print(json.dumps(report,indent=2))
