from __future__ import annotations

import contextlib
import os
from pathlib import Path
import shutil
import tempfile
import secrets
import math

import pymupdf as fitz
from .typography import FontCatalog, insert_styled_text
from .security import Protection, access
from dataclasses import replace as replace_style


def page_range(value: str, count: int) -> list[int]:
    """Parse human page ranges, preserving the requested order without duplicates."""
    result = []
    for part in value.split(','):
        part = part.strip()
        if not part:
            raise ValueError('Enter pages such as 1-3, 7, 10-12.')
        bits = part.split('-')
        if len(bits) == 1:
            numbers = [int(bits[0])]
        elif len(bits) == 2:
            lo, hi = map(int, bits)
            if lo > hi:
                raise ValueError('Page ranges must run forwards.')
            numbers = range(lo, hi + 1)
        else:
            raise ValueError('Invalid page range.')
        for n in numbers:
            if not 1 <= n <= count:
                raise ValueError(f'Pages must be between 1 and {count}.')
            if n - 1 not in result:
                result.append(n - 1)
    return result


def file_version(path):
    stat = Path(path).stat()
    return (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)


def check_file_version(path, expected):
    try:
        unchanged = file_version(path) == expected
    except FileNotFoundError:
        unchanged = False
    if not unchanged:
        raise ValueError('The original PDF changed outside Paperlight. Reopen it or use Save copy to keep your edits separately.')


def verify_redacted_text(page, regions):
    """Fail closed when a parser regression leaves native or hidden OCR text."""
    flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES
    for block in page.get_text('rawdict',flags=flags)['blocks']:
        for line in block.get('lines',[]):
            for span in line['spans']:
                for char in span['chars']:
                    if char.get('c','').strip() and any((fitz.Rect(char['bbox']) & r).get_area()>0.001 for r in regions):
                        raise ValueError('Redaction verification failed. The edit was cancelled because text remains in the marked area.')


def atomic_pdf_write(doc: fitz.Document, destination: str, *, sanitize=False, protection: Protection | None = None,
                     keep_encryption=False, password='', expected_version=None, snapshot_path=None):
    """Write beside destination, then replace atomically; never leave a partial PDF."""
    if keep_encryption and protection:
        raise ValueError('Choose either existing protection or new protection.')
    options = protection.save_options() if protection else {'encryption':fitz.PDF_ENCRYPT_KEEP} if keep_encryption else {}
    target = Path(destination)
    if expected_version is not None:
        check_file_version(target,expected_version)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.paperlight-', suffix='.pdf', dir=target.parent)
    os.close(fd)
    try:
        # Full compression/garbage collection can change MuPDF's live xref state.
        # Export from an independent snapshot so later incremental edits and undo
        # keep using the unchanged working file. Sessions supply their disk file
        # to avoid copying large documents into memory.
        clean = fitz.open(snapshot_path) if snapshot_path else fitz.open(
            stream=doc.tobytes(encryption=fitz.PDF_ENCRYPT_KEEP if keep_encryption else fitz.PDF_ENCRYPT_NONE),filetype='pdf')
        with clean:
            if not clean.authenticate(password):
                raise ValueError('Protected PDF verification failed.')
            if sanitize:
                # Remove hidden history, unused objects and sensitive payloads.
                clean.scrub(attached_files=True, embedded_files=True, hidden_text=False,
                            javascript=True, metadata=True, redactions=True,
                            remove_links=False, reset_fields=False, reset_responses=True,
                            thumbnails=True, xml_metadata=True)
                clean.set_toc([])
            clean.save(temporary, garbage=4, deflate=True, clean=sanitize, **options)
        with fitz.open(temporary) as check:
            if protection and not check.authenticate(protection.owner_password) & 4:
                raise ValueError('Protected PDF verification failed.')
            if keep_encryption and not check.authenticate(password):
                raise ValueError('Protected PDF verification failed.')
            if check.page_count != doc.page_count:
                raise ValueError('Saved page count does not match the document.')
        if expected_version is not None:
            check_file_version(target,expected_version)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PdfSession:
    def __init__(self, path: str, password: str = ''):
        self.path = str(Path(path).resolve())
        self._source_version = file_version(self.path)
        if self._source_version[2]>1024**3:
            raise ValueError('This document exceeds the supported file size.')
        self._password = password
        self._working_password = password
        self.doc = fitz.open(self.path)
        try:
            self.encrypted, self.readonly, self.copy_allowed = access(self.doc, password)
        except Exception:
            self.doc.close()
            raise
        if not self.doc.is_pdf or self.doc.page_count == 0:
            self.doc.close()
            raise ValueError('Open a PDF containing at least one page.')
        try:
            if self.doc.page_count>10000:
                raise ValueError('This document exceeds the supported page count.')
            for page in self.doc:
                if any(not math.isfinite(v) or not 0<v<=20000 for v in (page.rect.width,page.rect.height)):
                    raise ValueError('This document contains unsupported page dimensions.')
                if any(image[2]*image[3]>120_000_000 for image in page.get_images(full=True)):
                    raise ValueError('This document contains an image exceeding the supported size.')
        except Exception:
            self.doc.close()
            raise
        # Keep an isolated, normalized working file. Undo stores only incremental
        # suffixes on disk, rather than copying every page for every mouse stroke.
        # MuPDF's in-memory journal currently conflicts with font insertion and
        # rotated-page text extraction, so edits use PDF incremental revisions.
        self._temporary = tempfile.TemporaryDirectory(prefix='paperlight-edit-')
        self._working = Path(self._temporary.name) / 'working.pdf'
        if self.encrypted:
            # Keep the original security dictionary and both passwords, including
            # passwords unknown to this session. Native encrypted incremental
            # revisions allow Save to preserve that protection exactly.
            self.doc.save(self._working,encryption=fitz.PDF_ENCRYPT_KEEP)
        else:
            self._working_password = secrets.token_urlsafe(30)
            self.doc.save(self._working,encryption=fitz.PDF_ENCRYPT_AES_256,
                          owner_pw=self._working_password,user_pw=self._working_password)
        self.doc.close()
        self._open_working()
        self._history = []
        self._position = 0
        self._revision = 0
        self.saved_position = 0
        self.redaction_applied = False
        self._pending_count = None

    @property
    def dirty(self):
        return self._position != self.saved_position

    @property
    def position(self):
        return self._position

    def can_do(self):
        return {'undo': self._position > 0, 'redo': self._position < len(self._history)}

    def close(self):
        if not self.doc.is_closed:
            self.doc.close()
        self._temporary.cleanup()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _reopen_at(self, length):
        self.doc.close()
        with open(self._working, 'r+b') as stream:
            stream.truncate(length)
        self._open_working()

    def _open_working(self):
        self.doc = fitz.open(self._working)
        if not self.doc.authenticate(self._working_password):
            self.doc.close()
            raise ValueError('This PDF needs the correct password.')

    @contextlib.contextmanager
    def operation(self, title):
        self.require_edit()
        before = self._working.stat().st_size
        try:
            yield
            if not self.doc.is_dirty:
                return
            self.doc.saveIncr()
            after = self._working.stat().st_size
            self._revision += 1
            delta = Path(self._temporary.name) / f'{self._revision}.delta'
            with open(self._working, 'rb') as source, open(delta, 'wb') as target:
                source.seek(before)
                shutil.copyfileobj(source, target)
            # Start the next edit from the committed revision. MuPDF can otherwise
            # coalesce later form updates into a prior incremental suffix, which
            # makes truncation-based undo invalid for encrypted forms.
            self.doc.close()
            self._open_working()
        except Exception:
            self._reopen_at(before)
            raise
        else:
            if self.saved_position > self._position:
                self.saved_position = -1
            for row in self._history[self._position:]:
                row['delta'].unlink(missing_ok=True)
            self._history[self._position:] = [dict(before=before,after=after,delta=delta,title=title)]
            self._position += 1
        finally:
            self._pending_count = None

    def pending_redactions(self):
        if self._pending_count is None:
            self._pending_count = sum(1 for page in self.doc for a in (page.annots() or [])
                                      if a.type[0] == fitz.PDF_ANNOT_REDACT)
        return self._pending_count

    def rotate(self, index, degrees=90):
        with self.operation('Rotate page'):
            page = self.doc[index]
            page.set_rotation((page.rotation + degrees) % 360)

    def reorder(self, order):
        if sorted(order) != list(range(len(self.doc))):
            raise ValueError('A page order must contain each page exactly once.')
        with self.operation('Rearrange pages'):
            self.doc.select(order)

    def delete(self, pages):
        if len(set(pages)) >= len(self.doc):
            raise ValueError('Keep at least one page in the document.')
        with self.operation('Delete pages'):
            self.doc.delete_pages(pages)

    def merge(self, path, after, password=''):
        with fitz.open(path) as source:
            if access(source, password)[1]:
                raise ValueError('Unlock editing with the owner password first.')
            with self.operation('Insert PDF'):
                self.doc.insert_pdf(source, start_at=after + 1, widgets=True, join_duplicates=False)

    def split(self, pages, destination):
        self.require_edit()
        with fitz.open() as output:
            for p in pages:
                output.insert_pdf(self.doc, from_page=p, to_page=p, widgets=True)
            atomic_pdf_write(output, destination, sanitize=self.redaction_applied)

    def ink(self, index, points, color=(0.12, .32, .8), width=2):
        if len(points) < 2:
            return
        with self.operation('Draw'):
            annot = self.doc[index].add_ink_annot([[(float(p[0]), float(p[1])) for p in points]])
            annot.set_colors(stroke=color)
            annot.set_border(width=width)
            annot.update()

    def image(self, index, rect, path):
        with self.operation('Place signature image'):
            self.doc[index].insert_image(rect, filename=path, keep_proportion=True)

    def signature(self, index, rect, signature, date_text=''):
        rect = fitz.Rect(rect)
        if rect.width <= 3 or rect.height <= 3:
            raise ValueError('Draw a larger box for the signature.')
        # Keep Latin date digits proportionally spaced; a CJK font's fixed-width
        # Latin glyphs otherwise spread dates out unnaturally.
        latin, cjk = fitz.Font('helv'), fitz.Font('china-s')
        runs = []
        for char in date_text:
            name = 'helv' if ord(char)<128 else 'china-s'
            if runs and runs[-1][0]==name:
                runs[-1][1] += char
            else:
                runs.append([name,char])
        unit_width = sum((latin if name=='helv' else cjk).text_length(text,fontsize=1) for name,text in runs)
        size = min(11,rect.height*.19,rect.width/max(1,unit_width)) if date_text else 0
        available_height = max(1,rect.height-size*1.9)
        width = min(rect.width-2,available_height*signature['aspect'])
        height = width/max(.01,signature['aspect'])
        x = rect.x0+(rect.width-width)/2
        y = rect.y0+(available_height-height)/2
        paths = [[(x+a*width,y+b*height) for a,b in stroke] for stroke in signature['strokes'] if len(stroke)>1]
        if not paths:
            raise ValueError('Draw a signature before saving or placing it.')
        with self.operation('Place saved signature'):
            page = self.doc[index]
            annot = page.add_ink_annot(paths)
            annot.set_colors(stroke=(.12,.16,.23))
            annot.set_border(width=max(.5,min(3,height*.018)))
            annot.update()
            if date_text:
                x = rect.x0+(rect.width-unit_width*size)/2
                for name,text in runs:
                    page.insert_font(fontname=name)
                    page.insert_text((x,rect.y1-size*.3),text,fontsize=size,fontname=name,color=(.12,.16,.23))
                    x += (latin if name=='helv' else cjk).text_length(text,fontsize=size)

    def font_catalog(self):
        key=(id(self.doc),self._position,self._revision)
        if getattr(self,'_font_catalog_key',None)!=key:
            self._font_catalog=FontCatalog(self.doc)
            self._font_catalog_key=key
        return self._font_catalog

    def text(self, index, rect, text, size=None, replace=False, style=None):
        if not text:
            return
        rect = fitz.Rect(rect)
        if replace and self.pending_redactions():
            raise ValueError('Apply or undo pending redactions before correcting text.')
        if style is None:
            style=self.font_catalog().style(index,rect if replace else None)
        if size is not None:
            style=replace_style(style,size=float(size),line_height=style.line_height*float(size)/style.size)
        with self.operation('Replace text' if replace else 'Add text'):
            page = self.doc[index]
            if replace:
                # Existing content is actually removed, including scan pixels.
                page.add_redact_annot(rect, fill=(1, 1, 1), cross_out=False)
                page.apply_redactions(images=2, graphics=2, text=0)
                verify_redacted_text(page,[rect])
            insert_styled_text(page,rect,text,style)
        if replace:
            self.redaction_applied = True

    def mark_redaction(self, index, rect):
        with self.operation('Mark redaction'):
            self.doc[index].add_redact_annot(rect, fill=(0, 0, 0), cross_out=True)

    def apply_redactions(self):
        with self.operation('Apply redactions'):
            for page in self.doc:
                regions = [fitz.Rect(a.rect) for a in (page.annots() or [])
                           if a.type[0] == fitz.PDF_ANNOT_REDACT]
                if not regions:
                    continue
                # Remove annotation payloads and form values that intersect a mark.
                for widget in list(page.widgets() or []):
                    if any(widget.rect.intersects(r) for r in regions):
                        page.delete_widget(widget)
                for annot in list(page.annots() or []):
                    if annot.type[0] != fitz.PDF_ANNOT_REDACT and any(annot.rect.intersects(r) for r in regions):
                        page.delete_annot(annot)
                for link in page.get_links():
                    if any(fitz.Rect(link['from']).intersects(r) for r in regions):
                        page.delete_link(link)
                page.apply_redactions(images=2, graphics=2, text=0)
                verify_redacted_text(page,regions)
        self.redaction_applied = True

    def fill(self, index, xref, value):
        with self.operation('Fill form field'):
            widget = self.doc[index].load_widget(xref)
            if widget.field_flags & fitz.PDF_FIELD_IS_READ_ONLY:
                raise ValueError('This form field is read-only.')
            widget.field_value = value
            widget.update()

    def undo(self):
        if self.can_do()['undo']:
            row = self._history[self._position-1]
            self._reopen_at(row['before'])
            self._position -= 1
            self._pending_count = None

    def redo(self):
        if self.can_do()['redo']:
            row = self._history[self._position]
            self.doc.close()
            with open(self._working,'ab') as target, open(row['delta'],'rb') as source:
                shutil.copyfileobj(source,target)
            self._open_working()
            self._position += 1
            self._pending_count = None

    def require_edit(self):
        if self.readonly:
            raise ValueError('Unlock editing with the owner password first.')

    def unlock(self, password):
        with fitz.open(self.path) as original:
            if not original.authenticate(password) & 4:
                raise ValueError('Incorrect owner password.')
        self._password = password
        self._working_password = password
        self.doc.authenticate(password)
        self.readonly = False
        self.copy_allowed = True

    def save(self, destination, protection=None):
        self.require_edit()
        if Path(destination).resolve() == Path(self.path):
            raise ValueError('Choose a different filename to preserve the original PDF.')
        if self.pending_redactions():
            raise ValueError('Apply or undo the pending redactions before saving.')
        atomic_pdf_write(self.doc, destination, sanitize=self.redaction_applied, protection=protection,
                         snapshot_path=self._working,password=self._working_password)
        # Exporting a copy does not save the active source document.

    def save_in_place(self):
        self.require_edit()
        if self.pending_redactions():
            raise ValueError('Apply or undo the pending redactions before saving.')
        atomic_pdf_write(self.doc,self.path,sanitize=self.redaction_applied,
                         keep_encryption=self.encrypted,password=self._working_password,
                         expected_version=self._source_version,snapshot_path=self._working)
        self._source_version = file_version(self.path)
        self.saved_position = self._position

    def write_index_snapshot(self, destination):
        atomic_pdf_write(self.doc,destination,snapshot_path=self._working,
                         password=self._working_password,keep_encryption=True)


def insert_ocr_words(page, words):
    """Add an invisible search layer without replacing page content or forms."""
    page.insert_font(fontname='china-s')
    for word in words:
        if word.get('source') != 'ocr' or not word['text'].strip():
            continue
        rect = fitz.Rect(word['rect'])
        size = max(3, min(50, rect.height * .78))
        text = word['text']
        # Match word width as closely as possible; embedded CJK font handles Chinese.
        font = fitz.Font('china-s')
        width = font.text_length(text, fontsize=size)
        if width > rect.width and width > 0:
            size *= rect.width / width
        page.insert_text((rect.x0, rect.y1 - rect.height * .15), text,
                         fontsize=size, fontname='china-s', render_mode=3,
                         overlay=True)
