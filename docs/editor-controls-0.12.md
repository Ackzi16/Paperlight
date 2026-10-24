# Toolbar and selection changes in 0.12

All editing tools now share the visible editing toolbar. Saved signatures, signature images, forms, redaction, ink color, stroke width and Apply redactions no longer require More tools. The More tools button and shortcut are removed.

In Edit PDF, click a text box to select it. Drag its body to move it or a corner to resize its layout without scaling the font. Double-click to place the text cursor and type. The three-dot formatting button remains in the text editor. Moving unchanged native text keeps the original span positions relative to the box, fonts, sizes and colors. Resizing reflows text within the new bounds. A completed drag creates one undo entry; Escape cancels an active drag. Text selections do not modify the PDF.

The preview renderer removes native text from a scratch page and reconstructs a separate selected-text layer. A live text draft hides that layer while the editor displays its contents. Cancel restores the selected layer. Preview identities include object kind, bounds and annotation/source identifiers, so different text boxes on one page cannot reuse each other's results.

Native text with internal rotation or a rotated page still needs to be made upright before direct editing. Existing safety checks reject overlapping target text and overflowing content. OCR corrections retain the existing white-pixel replacement behavior for the original scan region; they do not recover the scan's typeface or background. Native text is reinserted above existing page content when committed, as in the previous text editor. A PDF does not retain an ordinary paragraph's empty editing frame; subsequent selection bounds follow its resulting text.

Selecting recognized scan text uses a crop of the original full-page raster, so selection itself preserves the scan's typography and pixels. The live editor appears only when dragging, resizing or entering text editing. A scan-selection composition test compares the unchanged preview against the original raster.

## Shape-preview correction

Version 0.11 used both a QGraphicsItem scale property and a separate base transform. Qt applies the scale before the base transform, which left translations scaled incorrectly when display zoom differed from preview raster scale. Version 0.12 composes raster-to-page conversion, page rotation, object transformation and display scale into one transform. The page origin remains the item's position. Selected shapes now also show their actual path contour, including curves, rather than only a rectangular outline.

Regression tests verify preview coordinates at zoom factors 0.65, 1.8, 2.2 and 2.7, page rotations 0, 90 and 270, and a nonzero page origin. Other cases exercise toolbar visibility, text selection, live dragging, resize/reflow, mixed-font retention, background graphics, double-click editing, cancellation, undo and same-page text-preview identity. Source and packaged verification results are recorded separately. This release makes no new security certification claim.

The full source suite passed 90 tests. The final scan-preview refinement is covered by the subsequent focused editor suite. See `tests-0.12.log` and `editor-tests-0.12.log` for exact results.
