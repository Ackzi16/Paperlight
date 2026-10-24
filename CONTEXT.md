# Paperlight

An offline Windows PDF app inspired by Preview's simple toolbar and thumbnail workflow.
Approved scope: large mixed/scanned PDFs, progressive cached English and Simplified/Traditional Chinese OCR search, drawing and signatures, text and interactive forms, page operations, short text corrections, permanent redaction, edited-copy saving, and a Windows installer.

Documents remain unchanged until an explicit Save. The user requested Ctrl+S to update the current file; Save copy must preserve its source. Search and OCR must not block the UI. Redacted exports must remove underlying content and affected OCR, not merely cover it.
REA research must distinguish inspected evidence from proposed design. No Mac Preview binary or Mac runtime has been provided.

Version 0.5 adds File > Protect PDF with AES-256, optional opening password, owner password, print/copy permissions, read-only restricted inputs and owner unlock. Passwords are never persisted in preferences. Encrypted inputs use session-temporary OCR caches. See docs/protection.md.

Version 0.6 adds Microsoft YaHei UI typography for Chinese, virtualized continuous scrolling and persisted single-page mode, reusable local signature strokes, capture of current page drawing, and optional placement-day date stamps in five formats. Ink/date placement is one undo operation.

Version 0.7 adds explicit File > Save / Ctrl+S with atomic replacement, existing encryption/password preservation, external-change detection, and unchanged active-session undo. Save copy exports without clearing the source dirty state.

Version 0.8 hardens local storage (Windows DPAPI caches/signatures; private caching default), temporary working/index PDF encryption, parser dependencies and redaction checks, input/worker limits, plain-text UI/logging. Internal assessment targets highly sensitive/regulated data and explicitly does not certify or approve that use; native OS sandbox, signed distribution, legacy-data review and independent assessment remain open. See docs/security-audit-2026-10-19/assessment.md.

Version 0.9 adds OCR text-layer insertion to the working PDF, automatic read-cursor selection, always-visible basic editing tools with More tools for advanced controls, and click-to-type live on-page text boxes with three-dot formatting. Correct text uses the live editor too. Save commits a pending draft, Cancel never changes PDF bytes. OCR preserves scan appearance and native edits; it does not reconstruct source typography.

Version 0.10 adds Edit PDF current-page object discovery, native mixed-style text-box editing/reflow, instance-specific graphic/image transforms and source-scope deletion, appearance controls, overlap cycling, and current-page OCR on entering edit mode. Unknown complex graphics fail closed as read-only. Native text replacement uses text-only redaction without a fill and preserves background graphics; OCR region replacement retains its explicit scan-pixel removal behavior. No Adobe internals or binary parity claim.

Version 0.11 retains edit scene items and previews moving graphics as transformed raster layers, with separate-process revision-checked rendering/discovery. Supports arbitrary-angle rotation, oriented resize, existing path anchors/curve controls, Shift constraints, arrow nudges and one undo per completed gesture. RapidOCR CPU benchmark was slower on the synthetic mixed-language sample; Tesseract remains the bundled engine. See docs/smooth-editing-0.11.md. No certification claim or security-sandbox change.

Version 0.12 removes More tools and exposes all editing tools in one toolbar. Edit PDF single-click selects text boxes, body drag moves, corner drag resizes/reflows, double-click edits text. Native moves retain original span offsets/styles; draft previews hide the original text layer. Preview cache identities distinguish text boxes on the same page. Shape previews compose display scale and transforms together to correct zoom-dependent drift, and selection follows the real path contour. See docs/editor-controls-0.12.md.

Version 1.0.0 fixes pale/invisible editing characters using an explicit selected-text foreground and contrast-aware editor backgrounds for light and mixed-color runs. Saved PDF colors remain unchanged. The user requested this version be released publicly on GitHub. See docs/release-1.0.0.md.
