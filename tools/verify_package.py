import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from paperlight.worker import search_words
from paperlight.core import PdfSession
from paperlight.security import Protection

folder=ROOT/'tmp'/'verification'
executable=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'dist'/'Paperlight'/'Paperlight.exe'
config=dict(path=str(ROOT/'assets'/'Welcome to Paperlight.pdf'),
            cache_root=str(folder/'packaged-cache'),ocr=True)
start=time.perf_counter()
worker=subprocess.run([str(executable),'--index'],input=json.dumps(config)+'\n',
                      encoding='utf-8',capture_output=True,timeout=40,
                      creationflags=subprocess.CREATE_NO_WINDOW)
if worker.returncode:
    raise RuntimeError(f'Packaged worker failed: {worker.returncode}\n{worker.stdout}\n{worker.stderr}')
rows=[json.loads(line) for line in worker.stdout.splitlines()]
assert any(row['kind']=='done' and not row['failures'] for row in rows)
records={row['page']:row for row in rows if row['kind']=='page'}
assert search_words(records[1]['words'],'OCEAN')
assert search_words(records[1]['words'],'中文文件')
report=dict(executable=str(executable),worker_seconds=round(time.perf_counter()-start,3),
            packaged_english_ocr=True,packaged_chinese_ocr=True)
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_FONTDIR='C:/Windows/Fonts')
screenshot=folder/'packaged-reader.png'
gui=subprocess.run([str(executable),str(ROOT/'assets'/'Welcome to Paperlight.pdf'),'--smoke',str(screenshot)],
                   env=env,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True)
assert gui.returncode==0,(gui.returncode,gui.stderr)
assert screenshot.stat().st_size>10000
report['gui_launch_render_exit']=True
# Exercise the bundled worker with an encrypted input and the installed reader
# with an owner-protected, publicly readable input.
sample = ROOT/'assets'/'Welcome to Paperlight.pdf'
session = PdfSession(str(sample))
try:
    for opening in ('', 'Package-reader'):
        protected = folder/('protected-open.pdf' if opening else 'protected-owner.pdf')
        session.save(protected, Protection('Package-owner', opening))
        protected_config = dict(config, path=str(protected), password=opening,
                                cache_root=str(folder/'protected-package-cache'), ocr=False)
        result = subprocess.run([str(executable), '--index'], input=json.dumps(protected_config)+'\n',
                                encoding='utf-8', capture_output=True, timeout=40,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, result.stderr
        protected_rows = [json.loads(line) for line in result.stdout.splitlines()]
        assert any(r['kind']=='done' and not r['failures'] for r in protected_rows)
        assert any(r['kind']=='page' and r['words'] for r in protected_rows)
    protected_gui = subprocess.run([str(executable), str(folder/'protected-owner.pdf'), '--smoke',
                                   str(folder/'packaged-protected-reader.png')], env=env, timeout=60,
                                  creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
    assert protected_gui.returncode == 0, protected_gui.stderr
    assert (folder/'packaged-protected-reader.png').stat().st_size > 10000
    report['protected_pdf_worker_and_readonly_gui'] = True
finally:
    session.close()
(folder/'package-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
