"""Separate-process PDF indexing. No MuPDF document crosses a thread boundary."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time
import math
import tempfile

import pymupdf as fitz
from .local_protection import protect,unprotect,MAX_BLOB


INDEX_VERSION = 'v4-protected-160-eng-chi_sim-chi_tra'
MAX_OCR_PIXELS = 32_000_000


def emit(data):
    print(json.dumps(data, ensure_ascii=True), flush=True)


def resource_path():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets' / 'tessdata'


def cache_key(path, language):
    digest = hashlib.sha256((INDEX_VERSION + language).encode())
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def word_rows(page, textpage=None, source='native'):
    words = page.get_text('words', textpage=textpage, sort=True)
    if len(words)>50000 or sum(len(w[4]) for w in words)>250000:
        raise ValueError('This page exceeds the supported text size.')
    return [dict(rect=list(w[:4]), text=w[4], block=w[5], line=w[6], source=source) for w in words]


def valid_record(row, page):
    if not isinstance(row,dict) or row.get('page')!=page or not isinstance(row.get('complete'),bool) or not isinstance(row.get('ocr'),bool) or not isinstance(row.get('words'),list) or len(row['words'])>50000:
        return False
    total = 0
    for word in row['words']:
        if not isinstance(word,dict) or not isinstance(word.get('text'),str) or word.get('source') not in ('native','ocr'):
            return False
        rect = word.get('rect')
        if not isinstance(rect,list) or len(rect)!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e7 for v in rect):
            return False
        total += len(word['text'])
    return total<=250000


def cache_purpose(path):
    return 'cache/'+path.parent.name+'/'+path.stem


def needs_ocr(page):
    words = page.get_text('words')
    if not words:
        return True
    area = max(1, page.rect.get_area())
    return any(fitz.Rect(image['bbox']).get_area() / area > .18 for image in page.get_image_info())


def index_document(path, cache_root, language='eng+chi_sim+chi_tra', password='', ocr=True, seed=None):
    started = time.perf_counter()
    key = cache_key(path, language)
    folder = Path(cache_root) / key
    folder.mkdir(parents=True, exist_ok=True)
    emit(dict(kind='meta', key=key))
    with fitz.open(path) as doc:
        if doc.needs_pass and not doc.authenticate(password):
            raise ValueError('Incorrect PDF password.')
        # Publish native text for ALL pages before doing any expensive OCR.
        pending = []
        records = {}
        for n, page in enumerate(doc):
            cached = folder / f'{n}.bin'
            if seed and str(n) in seed and not cached.exists():
                if valid_record(seed[str(n)],n):
                    store(cached, seed[str(n)])
            if cached.exists():
                try:
                    if cached.stat().st_size>MAX_BLOB:
                        raise ValueError('Cache record too large.')
                    row = json.loads(unprotect(cached.read_bytes(),cache_purpose(cached)).decode('utf-8'))
                    if not valid_record(row,n):
                        raise ValueError('Cache record invalid.')
                    records[n] = row
                    emit(dict(kind='page', **row, cached=True))
                    if ocr and not row.get('complete', False):
                        pending.append(n)
                    continue
                except (ValueError, OSError):
                    pass
            row = dict(page=n, words=word_rows(page), complete=not needs_ocr(page), ocr=False)
            records[n] = row
            emit(dict(kind='page', **row, cached=False))
            store(cached, row)
            if not row['complete']:
                pending.append(n)
        emit(dict(kind='native_done', pages=len(doc), pending=len(pending)))
        failures = []
        if ocr:
            for position, n in enumerate(pending):
                emit(dict(kind='progress', page=n, current=position + 1, total=len(pending)))
                page = doc[n]
                try:
                    pixels = page.rect.width*page.rect.height*(160/72)**2
                    if not math.isfinite(pixels) or pixels>MAX_OCR_PIXELS:
                        raise ValueError('This page exceeds the supported OCR image size.')
                    tp = page.get_textpage_ocr(language=language, dpi=160, full=True,
                                               tessdata=str(resource_path()))
                    native = records[n]['words']
                    native_rects = [fitz.Rect(w['rect']) for w in native]
                    recognized = []
                    for w in word_rows(page, tp, source='ocr'):
                        rect = fitz.Rect(w['rect'])
                        if not any((rect & r).get_area() > rect.get_area() * .45 for r in native_rects):
                            recognized.append(w)
                    row = dict(page=n, words=native + recognized, complete=True, ocr=True)
                    store(folder / f'{n}.bin', row)
                    emit(dict(kind='page', **row, cached=False))
                except Exception as exc:
                    failures.append(n)
                    emit(dict(kind='warning', page=n, message=str(exc)))
        emit(dict(kind='done', seconds=round(time.perf_counter()-started, 3),
                  pages=len(doc), failures=failures, pending=0 if ocr else len(pending)))


def store(path, row):
    payload = protect(json.dumps(row,ensure_ascii=False).encode('utf-8'),cache_purpose(path))
    fd,temporary = tempfile.mkstemp(prefix='.index-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(payload)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def search_words(words, query):
    """Match phrases and CJK across OCR word boundaries, retaining geometry."""
    if not query.strip():
        return []
    chars, owners = [], []
    for i, word in enumerate(words):
        for char in word['text'].casefold():
            if not char.isspace():
                chars.append(char)
                owners.append(i)
    needle = ''.join(query.casefold().split())
    haystack = ''.join(chars)
    if not needle:
        return []
    hits, offset = [], 0
    while len(hits) < 500:
        pos = haystack.find(needle, offset)
        if pos < 0:
            break
        indexes = list(dict.fromkeys(owners[pos:pos+len(needle)]))
        hits.append(dict(rects=[words[i]['rect'] for i in indexes],
                         text=' '.join(w['text'] for w in words[max(0,indexes[0]-4):indexes[-1]+5])))
        offset = pos + max(1, len(needle))
    return hits


def main():
    # Password travels over stdin, never process arguments or persisted cache metadata.
    config = json.loads(sys.stdin.readline())
    try:
        index_document(**config)
    except Exception as exc:
        emit(dict(kind='error', message=str(exc)))
        return 1
    return 0
