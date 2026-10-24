# Paperlight 0.9 editing workflow

22 October 2026. This update changes the UI and OCR document workflow. It does not change the unresolved security restrictions documented in the archived 0.8 assessment and does not certify 0.9 for regulated use.

- Read selects native and recognized text automatically on hover/drag. Drag blank areas to pan. The explicit Select text tool remains available.
- Read, Select text, Draw/sign, Add text, Correct text, Undo and Redo stay on the basic toolbar. More tools expands signatures, forms, redaction and ink settings.
- Add text starts a box at the click position, including on rotated pages. Typing updates the page editor immediately. The three-dot popup changes document font, size, color, line spacing and alignment live. Done or Ctrl+Enter inserts one undoable PDF edit. Escape cancels. Save also commits the open draft. Failed overflow leaves the draft editable and the PDF unchanged.
- Correct text opens the same live editor over a dragged selection. It removes underlying text and scan pixels in that rectangle, then inserts the replacement. Surrounding paragraphs do not reflow.
- Recognize text now adds an invisible selectable text layer to the working PDF after the OCR worker finishes. Native text is preserved, repeated recognition avoids duplicate overlapping words, and Save/Ctrl+S retains the layer in the current file. The document image appearance stays unchanged. Correct text can replace the recognized scan words or short paragraphs.
- OCR cannot recover the original scan font or reconstruct a full word-processing document. Corrections without native font metadata use a readable fallback with formatting choices. Check OCR output before relying on it.
- Restricted PDFs retain read-only behavior: OCR is available for session reading/search but cannot write the layer without editing permission. OCR failures remain visible and other pages can complete. Stopping OCR retains the search results already received; it does not auto-apply a partial layer.

## Verification

69 tests passed, including real English/Chinese OCR through the separate worker, stable rendered scan pixels, duplicate avoidance, scan correction, save/reopen, undo/redo, default-cursor selection, click placement, rotated-page placement, live formatting, draft cancellation and overflow rollback. The existing security, encryption, redaction, saving and selection suite also passed.

Packaged worker/GUI checks and installed copy checks are recorded in the release verification files when built. The scanner/SBOM/hash files under security-audit-2026-10-19 apply to the archived 0.8 release, not this new binary.
