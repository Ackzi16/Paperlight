# Verification

Verified on Windows 11 x64, 2026-10-16. The source environment is Python 3.12.14, PySide6 6.12.0 and PyMuPDF 1.26.7.

## Functional checks

`python -m pytest -q` passed the original 10 tests. Version 0.2 adds six checks for typography and tool feedback, for 16 tests total. Coverage includes actual PDF save/reopen and Qt mouse interaction, not only UI construction:

- Rotation, reorder, deletion, insertion, extraction, undo and redo; source preservation.
- Mouse drawing, English/Chinese text insertion and correction, overflow rejection.
- Interactive form values in both PyMuPDF widgets and pypdf's canonical AcroForm field tree, with appearance streams.
- English and Chinese OCR on a mixed scan, cached reuse, phrase search, and searchable export.
- Search navigation and PDF/display coordinate mapping on a rotated page.
- OCR process startup, completion and cache clearing through the Qt interface.
- Redaction removes visible text, hidden OCR text, intersecting form data, whole images, and affected pixels of a partially retained image. Raw exported streams are checked for removed text. Retained image pixels are inspected separately from the black cover rectangle.
- Undo/redo of text edits, branching after saving, and temporary editing-file cleanup.
- Document font ranking by character count, selection font/size/color/baseline matching, proportional width after saving, line spacing, embedded Arial reuse and missing subset glyph recovery from an installed copy, document font choices, and explicit font overrides.
- Compact reader / optional markup mode, separate draw and redaction cursors, text insertion cursor and form-field hover cursor. Reader, markup and font-editor screenshots are visually inspected.
- Invisible OCR layers are excluded from the visual font inventory so recognition fonts do not become the default typeface for scan corrections.

The native journal conflicted with MuPDF font insertion and rotated-page extraction. The application instead stores incremental PDF revision suffixes on disk for undo. It does not keep a full in-memory copy per edit.

## Large-document measurement

Synthetic fixture: 300 pages, alternating 150 native-text pages and 150 scans with unique image content, 14,213,636 bytes. Scan contents repeat a clean English/Chinese sample with distinct sheet identifiers and paper texture. This measures this fixture on this machine; it does not represent every scan quality or document size and is not an Adobe comparison.

| Operation | Measured time |
|---|---:|
| Open and prepare isolated working copy | 0.061 s |
| Render first page at 1.2x | 0.013 s |
| Index existing text across all pages | 1.913 s |
| First OCR pass for 150 scanned pages, completing all 300 pages | 72.996 s |
| Reload the completed 300-page index | 0.321 s |
| Search cached words for OCEAN, 150 matches | 0.016 s |

OCR reported zero failed pages. The initial OCR pass is intentionally separate from cached search. Raw measurements are retained locally in `tmp/verification/performance.json`. Reproduce with `tools/make_demo.py` and `tools/benchmark.py`; a preexisting matching cache changes cold-run timings.

## Packaging checks

The Windows package bundles the Python/Qt/MuPDF runtimes and all three OCR models. `tools/verify_package.py` passed against the actual executable: worker pipes, English and Chinese recognition, GUI launch, page rendering, screenshot capture and clean exit. The windowed executable explicitly reopens inherited pipes for its OCR subprocess.

Packaging initially picked up Poppler's incompatible ICU library from the build environment. Its exports did not match the unversioned ICU API Qt uses. The build now checks and excludes that accidental dependency, allowing Qt to use Windows 10/11's ICU API. The corrected executable passed the package checks.

The Inno Setup installer completed successfully for the current Windows user, without elevation or restart, under `%LOCALAPPDATA%/Programs/Paperlight`. The Start menu application and quick-guide shortcuts and the uninstaller were present. The installed executable then passed the same English/Chinese OCR, GUI launch, rendering and exit checks. Corresponding source is included in the installation.

## Limits

No private user PDFs were supplied. The tests do not establish compatibility with every PDF producer, damaged file, signature scheme or form type. Existing certificate signatures are not preserved, and cryptographic signing and radio/button actions are not implemented. Text corrections reuse an embedded font or a matching installed face where possible; fonts or glyphs unavailable in both require a reported substitute. Scans lack original font metadata. OCR results should be reviewed on poor scans.

REA 6.5.0 diagnostics and capabilities ran successfully. Mac Preview binary/runtime inspection remains unavailable on this Windows-only setup. See `rea-findings.md` for the evidence boundary.


## Version 0.6

The full suite passes 39 tests. New coverage checks continuous scrolling on a 300-page mixed-size PDF, bounded nearby-page rasters, scrollbar/page-number/thumbnail synchronization, markup and selection on a later page, rotated coordinate mapping, single-page restoration and mode persistence. Chinese font verification loads the installed Microsoft YaHei UI TTC explicitly for the Qt offscreen test backend. Native Windows discovers this font through its normal font database.

Signature tests draw multiple strokes with QtTest, save/reload/delete a local library entry, persist date preferences, check all five date formats, capture page ink into a reusable signature, and place a signature with a simulated next-day date. Ink and date undo/redo together and preserve form values. Source and UI captures were reviewed in English and Chinese, including a signature placed on a PDF. Password protection and earlier PDF functions remain covered.


## Version 0.7

The full suite passes 50 tests. New checks cover direct save to the current filename, Ctrl+S without a file picker, close-prompt saving, retained undo/redo across repeated saves, Save copy leaving the active source dirty, preservation of form values, and stopping the OCR worker before replacing a Windows file. Two sessions and a simulated mid-write external change verify that newer files are not overwritten. An injected replacement failure verifies original bytes, dirty state and temporary-file cleanup.

Encrypted tests verify both reader and owner passwords, original permission flags and AES-256 after repeated saves, with and without opening passwords, including redacted content removal. A reader explicitly permitted to edit can save while preserving an unknown owner password. Export and OCR snapshots use independent document objects; the live incremental editing history stays intact. Working documents reopen after committed edits so encrypted form revisions remain valid under undo/redo.
