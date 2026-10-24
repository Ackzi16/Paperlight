# Paperlight for Windows

An offline PDF reader and editor with a toolbar and thumbnail sidebar, inspired by Preview's workflow. Built for Windows x64. Version 1.0.0.

[Download the Windows installer](https://github.com/Ackzi16/Paperlight/releases/latest/download/Paperlight-Setup.exe) or see the [release downloads](https://github.com/Ackzi16/Paperlight/releases/latest) for the portable build, source and checksums.

Version 1.0.0 fixes faded editing text by giving selections a contrasting foreground and adapting the editing surface for pale or mixed-color text. PDF text colors are preserved. See [release notes](docs/release-1.0.0.md).

The reader has a compact icon toolbar and a thumbnail sidebar. All editing tools, including saved signatures, signature images, forms and redaction, are visible in the editing toolbar. Each tool has its own cursor; editable form fields show a hand when hovered.

Choose **Help > Language / 语言 > 简体中文** for the Simplified Chinese interface, or **帮助 > Language / 语言 > English** to switch back. Changes apply immediately and are remembered for the next launch. This changes the interface, not the PDF's contents or OCR languages. Menus, tooltips, editing dialogs, progress/error messages and the built-in guide are translated. Native Windows file-dialog buttons follow your Windows display language.

## Install and open

Run `dist/Paperlight-Setup.exe`. It installs for your Windows user without administrator rights and adds a Start menu shortcut. A desktop shortcut is optional. The installer and application are unsigned.

You can also run `dist/Paperlight/Paperlight.exe` directly without installing. Keep its `_internal` folder beside it. No Python installation or internet connection is required to use the packaged app.

## Use

- Open a PDF with the native file dialog or drag it into the window. Select a thumbnail to navigate. Ctrl+wheel zooms, Ctrl+0 fits, Alt+Left / Alt+Right change page.
- **Select text**, or Ctrl+Shift+T, selects text with an insertion cursor and blue feedback. The default read cursor also selects text automatically when hovering over native or recognized words; drag blank areas to pan. Drag across characters or lines, double-click a word, or Ctrl+A to select the current page. Ctrl+C copies; Escape clears. Right-click for Copy / Select all / Clear. Selection survives zoom and uses rotated page coordinates correctly. Native text supports character selection; recognized OCR supports word selection. Run Recognize text before selecting text in image-only scans. Selection does not alter the PDF.
- Ctrl+F searches existing text. Choose **Recognize text** to recognize English, Simplified Chinese and Traditional Chinese scans. Recognition runs in a separate process. Reading and editing stay available; an edit stops the active recognition job. Completed OCR is reused within the session; optional encrypted persistence is available under Tools.
- The first OCR pass takes time. OCR caches use Windows current-user encryption and are session-only by default. Tools > Remember encrypted search cache enables reuse for unencrypted inputs between sessions. Password-protected inputs stay session-only. Old plaintext search-v3 caches are removed on startup. Stop OCR preserves completed results. Tools > Clear local search cache removes cached recognition data.
- **Recognize text** runs offline OCR and adds an invisible, selectable text layer to the working PDF when recognition finishes. Use **Correct text** to replace recognized scan words or short paragraphs. The scanned image remains the visual background; OCR does not reconstruct the original layout or typeface. Save/Ctrl+S keeps the text layer in the existing file. Restricted PDFs remain read-only until owner unlock. File > Export searchable copy also exports recognized text; incomplete exports require confirmation.
- **Draw / sign** uses the mouse. **Signature image** imports PNG/JPEG/BMP/WebP and places it in a dragged rectangle. Transparent PNGs work best. These are visual signatures, not cryptographic signatures.
- **Add text** creates a box with its top-left corner at your click. Type directly on the page and see each change live. The three-dot button at the top right opens font, size, color, alignment and line-spacing controls. Done or Ctrl+Enter applies one undoable edit; Escape cancels. Save also applies the open draft. **Correct text** opens the same live editor after dragging over the existing text. **Correct text** removes the contents of the selected rectangle and inserts replacement text. Corrections detect the selected text's font, size, color, baseline and line spacing. When several fonts are selected, the most-used selected font wins. New text and areas without native text use the document's most-used font and size, weighted by character count. The font picker lists the other document fonts in frequency order, with controls for size, color, alignment and line spacing. Bold and italic faces are preserved through their font programs. Embedded fonts are reused when they contain the needed glyphs; otherwise an installed copy of the same face is preferred. The editor explicitly reports unavailable fonts and missing-glyph substitutes. Scans without native font metadata cannot reveal the original typeface. Keep correction boxes tight around the content being replaced. Overflow is rejected; surrounding paragraphs do not reflow.
- **Fill form** edits existing text, checkbox and choice fields. For paper forms, use Add text. Certificate signatures and radio/button actions are not implemented.
- Drag thumbnails to rearrange pages, or use the Pages menu to move, rotate, delete, extract/split and insert/merge. Use Ctrl/Shift to select several thumbnails. Extract accepts ranges such as `1-5, 9, 12-20`.
- Right-click an annotation to remove it. Ctrl+Z and Ctrl+Y undo and redo. Undo data uses incremental PDF revisions on disk rather than a full document copy per edit.
- **Redact** marks rectangles. **Apply redactions** removes covered text and image pixels, plus intersecting form fields and annotation payloads. Save and Save copy write a sanitized PDF without unused objects, embedded attachments, JavaScript or metadata after redaction. Pending redactions must be applied or undone before saving. Undo remains available in the current session. Save updates the input file; Save copy preserves it.
- **File > Save**, the toolbar Save button or **Ctrl+S** writes changes to the current filename without opening a file picker. The file is written and checked in a temporary file beside the original, then replaced atomically. Existing PDF encryption, both passwords and permission flags are preserved. Restricted files still require owner unlock. Applied redactions are sanitized with a full rewrite; marked but unapplied redactions block saving. Undo stays available in the current session after saving.
- **Save copy / Ctrl+Shift+S** asks for a different filename and leaves the current source unchanged. Exporting a copy does not clear unsaved changes to the active source. Closing or opening another PDF offers Save, Discard or Cancel; Save writes the current file.
- Save stops an active OCR job to release Windows file handles and retains completed search data. Restart Recognize text if needed. If the source changed in another app/window or was removed, Save refuses to overwrite it; use Save copy to rescue edits or reopen the latest version. Failed writes keep the original intact and edits unsaved.

## Reading modes and saved signatures

- **View > Continuous scroll** places pages in a vertical column with a small gap. Wheel scrolling, the scrollbar, thumbnails, page numbers and search navigate the column. Only nearby pages keep rendered images in memory. **View > Single page** restores the page-at-a-time frame. The choice is remembered. Ctrl+0 fits the width in continuous mode and fits the page in single-page mode. Selection and markup use the active page; a text selection does not span multiple pages.
- The Chinese interface uses the installed **Microsoft YaHei UI** family, with a slightly larger base size and small labels. English uses Segoe UI. PDF fonts and document contents are unaffected.
- **Tools > Create / manage signatures…** opens a mouse drawing pad. Draw one or several strokes, name the signature and choose **Save signature** to reuse it later. Select an existing signature from the list to use, update or delete it. Deleting a stored signature does not remove previously placed signatures.
- To reuse ink drawn directly on the PDF, keep the Draw / sign tool active while drawing the strokes, then choose **Tools > Save current drawing as signature…**. Review the captured strokes and save them in the dialog. A new drawing group starts when you leave and re-enter Draw / sign or move to another page.
- Choose **Saved signature** in Markup, select or draw a signature, then choose **Place signature** and drag a rectangle on the page. Check **Include today's date** to add the computer's local date each time the signature is placed. Formats are `yyyy-MM-dd`, `dd/MM/yyyy`, `MM/dd/yyyy`, `dd MMM yyyy` and `yyyy年MM月dd日`. The date choice is remembered, while the date itself is calculated at placement. Ink and date are one undo step. The placed ink is a PDF annotation and its date is page text; undo removes both together.
- Signature strokes are saved locally in `signatures.json` under Paperlight's Windows local app-data directory. They use Windows current-user DPAPI encryption and are not uploaded. Valid legacy libraries migrate atomically on startup; they are not portable to another Windows identity. These are visual signatures, not certificate-based digital signatures.

## Password protection

File > Protect PDF… offers two modes for each export. Leave the opening-password checkbox off to let anyone read the file while requiring an owner password for editing in readers that enforce permissions. Turn it on to also require a separate password to read the encrypted contents. Printing and text/image copying are optional. Editing, annotations, forms and page changes are restricted. File > Unlock editing… accepts the owner password; Save copy can then export an unprotected copy. Protection does not overwrite your original or lock the current editing session.

Permission restrictions can be bypassed by some PDF tools. Anyone able to view a PDF can capture it or run OCR. Passwords are not saved in preferences and cannot be recovered by Paperlight. Keep the owner password separately. The new controls are translated into Chinese.

## Local data and limits

Documents stay on your computer. The app has no document upload or network feature. English and Chinese OCR models ship with it. Search caches contain recognized text and word locations under your Windows local application cache directory. Search caches are encrypted and session-only by default, removed on normal close. Persistent encrypted caching is optional for unencrypted inputs. Working PDFs of unencrypted inputs use a random per-session AES-256 password. Index snapshots retain working-file encryption. Existing encrypted inputs retain their original security, including any publicly readable or weak settings. Decoded content and passwords exist in memory while processing. Temporary editing files hold undo revisions until the session closes; interrupted processes may leave temporary files. The original source can still contain material removed from an edited copy.

Password-protected PDFs can be opened with a password. Restricted PDFs open read-only until File > Unlock editing accepts the owner password. Save preserves the original encryption and passwords. Save copy creates an unencrypted copy after confirmation for encrypted inputs. Use File > Protect PDF to create an AES-256 protected copy. See docs/protection.md for the choices and limitations. Editing can invalidate existing cryptographic signatures. Complex or damaged PDFs, unusual fonts and low-quality scans may need additional handling. Test results describe synthetic fixtures; no Adobe benchmark or full compatibility guarantee is implied.

## Build from source

Use Python 3.12 x64 and PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3 pytest==9.1.1 'pypdf[crypto]==6.20.1'
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -m pytest -q
```

For the installer build, put the Inno Setup 6.7.3 compiler under `.scratch/tools/inno`, including `ISCC.exe` and its supporting files, then run `tools/build.ps1`. The build creates a portable application directory, an installer and the corresponding source archive. OCR data is included under `assets/tessdata`.

## Research and verification

The approved tickets are in `.scratch/preview/issues`. See `docs/rea-findings.md` for REA diagnostics and documented Preview workflows. No Mac Preview binary or Mac runtime was available to inspect. See `docs/verification.md` for test results and measured synthetic-document performance.

Paperlight is licensed under AGPL-3.0-or-later. See LICENSE and THIRD_PARTY_NOTICES.md. The installer includes the source archive.


## Security assessment

Version 0.8 was internally assessed for a regulated/highly sensitive document target. See docs/security-audit-2026-10-19/assessment.md, raw scanner evidence, SBOM and release hashes. This is not an independent certification and the release is not approved by that assessment for regulated production use. Important open gates include OS sandboxing for native document parsing, signed releases, legacy temporary-data review and an independent assessment. Limits are 1 GiB input, 10,000 pages, 20,000-point page edges, 120 million declared image pixels and 32 million OCR raster pixels; these are guardrails, not complete process isolation. OCR stops after 90 seconds without worker output. Native/hidden-text redaction verification fails closed on detected residual text. Some malformed or unusual documents may therefore be rejected.

Version 0.9 changes the editing workflow. The assessment dated 19 October applies to the archived 0.8 release; it is not a certification of 0.9. See docs/editing-workflow-0.9.md for the new behavior and verification.


## Edit PDF mode

Version 0.10 adds **Edit PDF** to the basic toolbar. It analyzes the current page and outlines text boxes, images, forms, annotations and vector graphics. Click a text box to select it, drag it to move, or drag a corner to resize with text reflow. Double-click to type directly. Regular/bold/font/color runs are retained in native text. Use the three-dot popup to format the box, the corner control to resize/reflow it and the move control to reposition the draft. Done/Ctrl+Enter commits; Escape cancels. An unchanged selection does not modify the PDF.

Version 0.12 places all editing tools in the visible toolbar and removes More tools. Text-box selection and drag/resize controls work directly on the page. Shape previews now use one display transform to keep the visible shape aligned with its handles at different zoom levels and page rotations; the selection outlines the actual path. See docs/editor-controls-0.12.md for behavior, limits and verification.

Select a native shape or image and drag to move it; drag a corner handle to resize it, or the round handle above it to rotate. Shift snaps rotation to 15 degrees or keeps resizing proportional. Right-click for an exact rotation angle, **Edit points** on supported shapes, stroke/fill/width or Delete. Point editing exposes existing anchors and cubic curve controls. Arrow keys nudge graphics by one PDF point, Shift+arrow by ten. Escape cancels a gesture; releasing commits one undo step. Alt+click cycles overlapping objects. Instance-specific image movement does not change other uses of a shared image. Supported native graphics are edited through verified source command scopes, preserving neighboring content and stacking order. Complex/clipped/unmapped graphics remain read-only. Rendering and analysis run in a separate process; cached layers provide live drag previews. See docs/smooth-editing-0.11.md for details and the offline OCR engine comparison.

For an image-containing page without complete OCR, entering Edit PDF recognizes only that page in the separate OCR process. Recognized text can then be clicked and corrected. This does not vectorize shapes inside scans or recover their original typefaces. Scanned text corrections replace pixels in the selected original region with white, so colored/textured backgrounds still need care. Native text edits preserve surrounding graphics/background instead. Rotated or internally rotated native text must be made upright before direct text-box editing. Text that exceeds its box is rejected; resize it rather than reflowing the whole page. See docs/edit-pdf-0.10.md for scope and verification.
