"""Exercise the frozen persistent edit renderer using an encrypted working PDF."""
import json,sys,subprocess,base64,io
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from paperlight.core import PdfSession
from paperlight.objects import discover
from paperlight.edit_worker import serial
import pymupdf as f
from PIL import Image

exe=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'dist/Paperlight/Paperlight.exe'
folder=ROOT/'tmp/verification';path=folder/'packaged-edit-source.pdf'
with f.open() as doc:
    p=doc.new_page();p.draw_rect((60,100,300,220),fill=(.8,.9,1));p.insert_text((80,140),'Foreground text',fontsize=18);doc.save(path)
session=PdfSession(str(path))
try:
    obj=next(o for o in discover(session.doc[0]) if o.kind=='shape' and o.writable)
    text=next(o for o in discover(session.doc[0]) if o.kind=='text')
    common=dict(path=str(session._working),password=session._working_password,page=0,scale=1)
    requests=[dict(common,task='refresh',request=1),dict(common,task='preview',request=2,object=serial(obj)),dict(common,task='preview',request=3,object=serial(text)),dict(common,task='preview',request=4,object=serial(replace(text,kind='ocr')))]
    result=subprocess.run([str(exe),'--edit-worker'],input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,encoding='utf-8',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.stderr
    rows=[json.loads(line) for line in result.stdout.splitlines()]
    assert not any(r['kind']=='error' for r in rows)
    assert [r['request'] for r in rows if r['kind']=='done']==[1,2,3,4]
    assert any(r['kind']=='objects' and r['objects'] for r in rows)
    layers=[r for r in rows if r['kind']=='layer'];assert len(layers)==9
    for row in layers:
        image=Image.open(io.BytesIO(base64.b64decode(row['png'])));assert image.width>0 and image.height>0
    report=dict(executable=str(exe.resolve()),persistent_edit_worker=True,encrypted_input=True,preview_layers=True,native_text_preview=True,scan_pixel_preview=True,revision_ids=True)
    print(json.dumps(report,indent=2))
finally:session.close()
