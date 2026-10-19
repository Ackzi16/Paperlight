# UI and typography update, 0.2

The reader now uses a restrained gray toolbar, original monochrome vector buttons, centered thumbnails with a blue selection outline, page shadows and an optional Markup bar. The document title and page position occupy the main toolbar instead of a second heading. It uses Windows system UI typography rather than bundling Apple's system fonts or assets.

This follows Preview's documented separation of reading from the optional Markup toolbar and its thumbnail navigation. References: [Apple's Preview overview](https://support.apple.com/guide/preview/prvw846b61d3/mac) and [Markup guide](https://support.apple.com/guide/preview/prvw11580/mac). No new Mac runtime inspection is claimed.

Drawing, text correction, signature placement and redaction have distinct cursor graphics. Text uses an insertion cursor; existing form fields show a hand on hover. Outside the page, the cursor returns to an arrow. Hiding Markup selects Read to avoid leaving a hidden editing mode active.

Text replacement previously used one CJK font for all text, fixed baseline offsets and fixed 1.4x line spacing. The new editor inventories fonts using actual span character counts across the document. A correction matches the dominant selected font, size and color, and preserves the first selected character's baseline and original line spacing when measurable. New text defaults to the document's dominant face and most-used size. Users can select other fonts found in the document and change size, color, alignment and baseline spacing.

Original embedded font programs are preferred if writable and they contain the requested glyphs. A matching installed face can supply letters absent from an embedded subset. Standard PDF faces remain standard PDF fonts; they are not silently renamed to a metrically equivalent embedded font. Where the original program is unavailable, the editor reports the substitute or missing-glyph fallback. Bitmap scans cannot identify a font from PDF metadata, so use the document default or a reported standard fallback. Arbitrary rich-text run formatting and word-processor reflow remain outside this editor's scope.

Invisible OCR text is excluded from the visible font inventory. It is recognition data, not evidence of a scan's original font.

The implementation uses PyMuPDF's [span metadata](https://pymupdf.readthedocs.io/en/latest/textpage.html), [font extraction](https://pymupdf.readthedocs.io/en/latest/document.html#Document.extract_font), and [font metrics](https://pymupdf.readthedocs.io/en/latest/font.html). Six added tests verify actual saved typography and cursor/tool behavior, alongside the existing functional tests.
