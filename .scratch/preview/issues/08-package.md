# 08: Package and verify the Windows app

**What to build:** Deliver an offline Windows executable and installer, documentation, and verification evidence.

**Blocked by:** 03: Search text and scanned pages; 04: Draw, sign, and fill forms; 05: Organize and combine pages; 06: Correct existing text; 07: Permanently redact content.

**Status:** complete

- [x] Package OCR models and runtime dependencies.
- [x] Test mixed documents, reopen saved edits, and measure search timing.
- [x] Smoke-test the packaged executable and document limitations.

The per-user installer and installed executable were verified, including bundled English/Chinese OCR, rendering, Start menu shortcuts and uninstaller presence. Ten functional tests passed. The 300-page mixed fixture's completed index loaded in 0.321 seconds and a cached query took 0.016 seconds; the first OCR pass took 72.996 seconds.

