# Paperlight 1.0.0

Windows x64 release with the current editing workflow, English and Chinese OCR, signatures, forms, page operations, redaction and password protection.

## Text readability fix

The inline editor now specifies dark selected text on its pale-blue highlight, rather than inheriting a system highlight foreground that can be white. This also applies to the other pale-highlight input controls.

The editing surface adapts to the actual text colors. Ordinary dark text uses white; pale text uses a dark surface; mixed pale and dark runs use a neutral gray surface. These are editor backgrounds only. Existing and newly typed text keep their document colors when saved. A white heading on a dark PDF panel remains white on that panel.

Regression tests cover selection against a light system highlight foreground, white text, mixed white/black runs, insertion, saving and reopening. They verify that document colors and background graphics remain intact.

## Included since the previous GitHub release

- Current-page Edit PDF discovery for supported text, images and native shapes.
- Text-box selection, dragging, corner resizing/reflow and double-click editing, retaining mixed font/color runs.
- Shape movement, resizing, arbitrary-angle rotation and existing path-anchor/curve controls, with corrected live previews.
- All editing tools visible in the toolbar.
- Click-to-type new text with live formatting, OCR text-layer insertion, progressive search and continuous scrolling.

Read `editor-controls-0.12.md` and `smooth-editing-0.11.md` for editing limits. Scans do not contain editable vector shapes or recoverable original fonts. Complex unsupported graphics remain read-only. Rotated native text must be made upright before editing.

The installer and executable are unsigned. This is not a security certification or approval for regulated production use. The earlier internal assessment's unresolved gates remain documented in `security-audit-2026-10-19/assessment.md`.

## Validation

94 source tests passed. Packaged English/Chinese OCR, encrypted input, read-only protected files, GUI launch/render/exit and persistent edit previews passed. Installed-app verification is recorded in the corresponding JSON reports.
