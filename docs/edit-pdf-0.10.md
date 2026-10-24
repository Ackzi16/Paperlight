# Paperlight 0.10: Edit PDF

23 October 2026, Singapore time. This implementation is based on documented Acrobat workflows and local synthetic PDF experiments. It does not contain recovered Adobe code and does not claim full Adobe compatibility.

## Use

Click **Edit PDF** in the basic toolbar. The current page gets object outlines. Click native text to edit at the cursor, retaining mixed regular/bold/fonts/colors. The three-dot popup changes font, size, color, alignment and line spacing. Resizing changes paragraph wrapping without changing font size. The diagonal control resizes the text draft; the horizontal-arrow control moves it. Done or Ctrl+Enter commits; Escape cancels. Blank text deletes the selected text box. An unchanged selection is a no-op.

Click a supported native shape or image to select it. Drag to move; drag a corner handle to resize. Right-click for stroke color, fill color, stroke width or Delete. Alt+click cycles objects that overlap. Images are edited per displayed occurrence, so other occurrences of the same image keep their position and appearance.

A form field opens its existing field editor. FreeText annotations support text editing; Ctrl+drag allows movement. Other annotation types retain their existing markup-tool workflow.

Entering Edit PDF on an image-containing page with incomplete recognition starts **current-page OCR**, through the separate OCR worker. Other pages are not automatically recognized. Recognized text boxes can then be clicked and corrected. Explicit Recognize text still processes the document. Native text editing preserves graphics and backgrounds. Scan correction removes pixels in the original text region and replaces them with white, so colored or textured scan backgrounds need care.

## Implementation and boundaries

- Native text is inferred from PDF spans and line geometry. Same-baseline distant columns are kept separate; lines group into candidate paragraphs. The PDF may have no original textbox object.
- Shape/image edits use balanced, verified source command scopes. Instance transforms are inserted at the original stacking position, with inherited transforms accounted for. Deletion removes that object's source scope, not all content in its rectangle.
- Clipped, ambiguous, recursive or unmapped graphics are inspectable but not writable. Resource/stream/operator budgets also limit complex-page discovery. Line, rectangle and ellipse candidates are recognized; general compound paths remain grouped graphics, not editable individual control points.
- Native text uses text-only removal with no white fill. Paragraph changes preserve surrounding paths/background. Repeated Form XObjects are isolated before text removal so other occurrences remain unchanged. Destination text overlap and identical overlapping text fail closed.
- Native content edits clean unused PDF content when saving while preserving bookmarks and metadata. Explicit redaction and scan pixel correction retain the existing sanitized-save behavior. Use the Redact workflow for sensitive removal rather than relying on ordinary object editing.
- Internally rotated native text, or native text on a rotated page, must be made upright before direct text-box editing. Bounded text overflow is rejected and leaves the draft available to resize or cancel. This release does not reflow surrounding boxes or repaginate the document.
- Scanned shapes remain pixels inside images; they are not automatically vectorized. OCR does not recover exact original typefaces or turn an arbitrary scan into a fully reconstructed word-processing document.
- Discovery is page-local and cached by document revision. Graphics probes have bounded stream sizes, candidate counts and operation budgets. These are guards, not an OS sandbox or an independent security certification.

## Verification

78 tests passed against the shipping dependencies. The nine object-specific tests cover source discovery without mutation, mixed-style edits, color changes retaining mixed fonts, background and border preservation, paragraph reflow and Chinese text, shared image occurrences, nested transforms, repeated shared text resources including Chinese, current-page-only OCR, click selection and mouse movement, stale-object rejection, clipped-graphic refusal, no-op selection, undo/redo, save/reopen, bookmarks and metadata. Existing encryption, redaction, atomic saving, signatures, selection and UI tests also pass.

Dependency audit initially found advisories in the older Pillow and pypdf versions. Shipping requirements were updated to Pillow 13.0.0 and pypdf 6.21.1. The subsequent pip-audit scan reports no listed vulnerabilities in the resolved Python requirements. This is not a complete native-library audit or security certification. Raw results: dependency-audit-0.10-before.json and dependency-audit-0.10.json.

Packaged and installed verification is recorded separately after building. Source extraction experiments and the documented Adobe behavior are in adobe-edit-pdf-study.md. The archived 0.8 assessment remains scoped to its original binary.
