# Paperlight

An offline Windows PDF app inspired by Preview's simple toolbar and thumbnail workflow.
Approved scope: large mixed/scanned PDFs, progressive cached English and Simplified/Traditional Chinese OCR search, drawing and signatures, text and interactive forms, page operations, short text corrections, permanent redaction, edited-copy saving, and a Windows installer.

Documents remain unchanged until an explicit Save. The user requested Ctrl+S to update the current file; Save copy must preserve its source. Search and OCR must not block the UI. Redacted exports must remove underlying content and affected OCR, not merely cover it.
REA research must distinguish inspected evidence from proposed design. No Mac Preview binary or Mac runtime has been provided.

Version 0.5 adds File > Protect PDF with AES-256, optional opening password, owner password, print/copy permissions, read-only restricted inputs and owner unlock. Passwords are never persisted in preferences. Encrypted inputs use session-temporary OCR caches. See docs/protection.md.

Version 0.6 adds Microsoft YaHei UI typography for Chinese, virtualized continuous scrolling and persisted single-page mode, reusable local signature strokes, capture of current page drawing, and optional placement-day date stamps in five formats. Ink/date placement is one undo operation.

Version 0.7 adds explicit File > Save / Ctrl+S with atomic replacement, existing encryption/password preservation, external-change detection, and unchanged active-session undo. Save copy exports without clearing the source dirty state.

Version 0.8 hardens local storage (Windows DPAPI caches/signatures; private caching default), temporary working/index PDF encryption, parser dependencies and redaction checks, input/worker limits, plain-text UI/logging. Internal assessment targets highly sensitive/regulated data and explicitly does not certify or approve that use; native OS sandbox, signed distribution, legacy-data review and independent assessment remain open. See docs/security-audit-2026-10-19/assessment.md.
