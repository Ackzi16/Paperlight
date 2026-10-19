# Text selection, version 0.3

Markup now includes a dedicated Select text tool next to Read. It uses character-level native PDF geometry and word-level OCR geometry. Drag forward or backward across a line or several lines; the selection is painted blue. Double-click selects a word. Ctrl+C copies, Ctrl+A selects text on the current page, and Escape clears. Edit and right-click menus expose the same commands. Ctrl+Shift+T activates the tool.

Selection is maintained in PDF coordinates, so zoom does not lose the selection and page rotation does not offset it. Changing page or editing the document clears the selection. OCR recognition updates the current page's selectable text when results arrive. Pages with no text direct the user to Recognize text. The tool creates no annotations and does not mark the document as edited.

Four added tests cover multiline text, word boundaries, reversed selection, OCR English/Chinese spacing, blank pages, Qt mouse dragging, clipboard shortcuts, zoom persistence, rotated-page geometry and navigation clearing. The complete suite now has 20 passing tests.
