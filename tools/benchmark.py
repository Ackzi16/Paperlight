"""Reproducible synthetic mixed-document benchmark; no Adobe comparison implied."""
import contextlib
import io
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from paperlight.core import PdfSession
from paperlight.worker import index_document, search_words

folder=ROOT/'tmp'/'verification'
path=folder/'300-page-mixed.pdf'
results={}
start=time.perf_counter()
session=PdfSession(str(path))
results['open_working_copy_seconds']=round(time.perf_counter()-start,3)
start=time.perf_counter()
session.doc[0].get_pixmap(matrix=__import__('pymupdf').Matrix(1.2,1.2))
results['first_page_render_seconds']=round(time.perf_counter()-start,3)
session.close()
results['pages']=300
results['file_bytes']=path.stat().st_size
for name,ocr in [('native',False),('cold_ocr',True),('cached',True)]:
    start=time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()) as capture:
        index_document(str(path),str(folder/'benchmark-cache'),ocr=ocr)
    seconds=time.perf_counter()-start
    rows=[json.loads(line) for line in capture.getvalue().splitlines()]
    records={row['page']:row for row in rows if row['kind']=='page'}
    results[name+'_seconds']=round(seconds,3)
    results[name+'_completed_pages']=sum(row['complete'] for row in records.values())
    results[name+'_failures']=next(row['failures'] for row in rows if row['kind']=='done')
    print(name,results[name+'_seconds'],flush=True)
    if name=='cached':
        start=time.perf_counter()
        matches=sum(len(search_words(row['words'],'OCEAN')) for row in records.values())
        results['cached_query_seconds']=round(time.perf_counter()-start,4)
        results['cached_query_matches']=matches
    (folder/'performance.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2),flush=True)
