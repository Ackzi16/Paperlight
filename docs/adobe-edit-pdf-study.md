# Acrobat-style Edit PDF investigation

23 October 2026, Singapore time.

## Evidence boundary

This is a behavior/specification reconstruction and a Paperlight architecture review. Adobe's proprietary implementation was not recovered, executed or decompiled. Acrobat was not found in the three common installation paths checked; this is not an exhaustive installed-application inventory. Adobe behavior below is supported by its public documentation. The local experiment uses a PDF created by us and PyMuPDF 1.28.2, not an Acrobat-generated or Acrobat-edited file. No user documents were inspected or uploaded. No application changes or new installed release are part of this investigation.

## Documented target behavior

Adobe documents selecting existing text in Edit mode, paragraph-local reflow and font controls. Text-box resize reflows text without changing font size. It documents image/object selection, movement, resize, crop and rotation. For scanned pages Edit invokes OCR before editing. These facts do not establish the grouping, segmentation, font synthesis or object-rewrite algorithms Adobe uses. The documentation does not establish universal conversion of arbitrary scanned diagrams into editable vector shapes.

References:
- https://helpx.adobe.com/acrobat/using/edit-text-pdfs1.html
- https://helpx.adobe.com/acrobat/desktop/edit-documents/edit-text-in-pdfs/adjust-text-boxes.html
- https://helpx.adobe.com/acrobat/desktop/create-documents/scan-documents-to-pdfs/edit-scans.html
- https://www.adobe.com/learn/acrobat/web/edit-text-graphic-multimedia-elements-pdf
- https://pymupdf.readthedocs.io/en/latest/recipes-drawing-and-graphics.html

## Local experiment

Fixture and raw observations are in tmp/verification/adobe-edit-study/object-probe.pdf and results.json.

Page 1 contains native mixed-font text, a rectangle, a line, a circle, a FreeText annotation and a form field. Its mixed-font sentence is extracted as a single text block containing separate Helvetica and Helvetica-Bold spans. The rectangle has an `re` path primitive, the line `l`, and the circle four cubic `c` segments. The annotation and widget have explicit object types and identities. Their appearance text can also appear in general text extraction; object discovery must avoid exposing duplicate editable text over an annotation or field.

Page 2 embeds a raster rendering of that page. Extraction finds one image and no native text blocks or vector paths. OCR is needed for its text; recovering independently editable shapes requires additional image segmentation and vector reconstruction. A visually identical document can therefore require a fundamentally different edit route.

## Proposed reconstruction for Paperlight

This section is our design, not a statement about Adobe internals.

1. Add an explicit Edit PDF mode. Discover objects lazily on the current/visible page rather than OCRing an entire document before the user can interact. Cache object analysis by document revision, page and engine/model version.
2. Build a page object model with type, bounds, transforms, source references, stacking order, style runs and confidence. Distinguish native text groups, vector paths, images, annotations, widgets and OCR regions. Do not use a bounding rectangle as object identity.
3. Group native glyphs/spans into lines and paragraphs using baseline direction, spacing, alignment, font/style boundaries and column/table separators. Preserve mixed style runs and CJK shaping. Allow ambiguous regions to be split or selected individually. Extracted block boundaries are candidates, not guaranteed original textbox boundaries.
4. Classify simple native vector paths: lines and rectangles first; ellipse candidates from compatible curve groups. Preserve stroke, fill, dash, opacity, transform, clipping and stacking order. Arbitrary logos/compound paths remain grouped graphics initially. Paths may also be text converted to outlines; they are not recoverable text without recognition.
5. Hit-test using geometry and stacking order, with a way to cycle overlapping objects. Hover outlines an object. Click selects it and shows handles; text click opens the existing live editor. Provide move/resize/delete and a contextual formatting panel. Read-mode text selection remains separate.
6. Make native text editing run-aware and reflow within the selected box. Resizing a text box changes line layout, not font size. Reuse embedded/installed fonts where they can encode the new text, otherwise disclose substitution. Do not claim that OCR can recover an exact original typeface from pixels.
7. Add an object-aware write backend. Removing or moving a path/text object must target its original content operators or an isolated resource, with correct graphics-state and clipping dependencies. Moving one use of a shared image/Form XObject must not alter its other uses. PyMuPDF extraction is useful but does not itself provide a general object-edit transaction.
8. For scans, OCR into word/line/paragraph candidates with confidence, then offer text correction through the live editor. Preserve the background carefully; white rectangle replacement is unsuitable on textured or colored backgrounds. Detection of scan lines/rectangles/ellipses and background reconstruction is a separate optional feature requiring validation. Keep uncertain scan graphics as image regions rather than falsely labeling them native vector objects.
9. Commit through the existing encryption, owner-permission, undo/redo and atomic Save machinery. Discovery and hover must not modify bytes or mark the document dirty. Keep detection, OCR and bulk document work isolated from the UI. Invalidate only affected object/cache entries after an edit.

## Gaps in Paperlight 0.9

Available foundations: PDF rendering; native/OCR selection; font catalog; on-page text draft and formatting popup; native widgets; signatures; encrypted working files and caches; permission enforcement; undo/redo and atomic Save.

Missing: unified object discovery/identity and hit-testing; style-run-preserving paragraph layout; selectable vector/image objects and handles; source-object-aware mutation; scan paragraph/shape segmentation and background preservation.

The current Correct text route redacts a rectangle and inserts replacement text. It can remove overlapping vector content and scan pixels. It must not be used as the generic implementation of native shape movement or arbitrary textbox editing. Merely drawing selection borders around extracted blocks would not complete this feature.

## Suggested delivery stages

A. Detection preview: Edit PDF mode, current-page text/image/vector/annotation/form outlines, overlap selection and type labels. No mutation until the object classification is reliable.
B. Native text editing: click-to-edit, mixed-font runs, bounded paragraph reflow and robust undo/save. Retain explicit scan correction for OCR regions.
C. Simple native objects: move/resize/delete images, lines and rectangles with verified object-specific removal and no collateral changes. Extend to ellipses and compound paths after coverage exists.
D. Scanned regions: faster OCR integration, paragraph grouping, confidence review and optional simple-shape reconstruction. This is a separate image-analysis problem from native PDF extraction.

## Acceptance criteria

Use fixtures for mixed English/Chinese fonts, subset fonts, rotated/skewed text, columns, tables, overlapping shapes/text, transparent and clipped paths, repeated/shared XObjects, annotations and forms. Include raster-only pages and outlined text.

Check object count/type and selection geometry across zoom/rotation/continuous scrolling; typing and resize reflow; unchanged rendering outside the edited object; no accidental loss of neighboring content; correct extraction after save/reopen; encrypted permissions; save failures; undo/redo; cancellation and stale-revision detection. Use a licensed Acrobat installation and identical fixtures for any future black-box parity comparison. Do not claim Adobe parity from synthetic extraction results alone.
