# Stirling PDF comparison and Paperlight offline toolbox

Reviewed on 28 October 2026. Sources were Stirling's official tool and desktop-processing documentation, README and license at repository commit `5bd8181777c08bff5544abcc4c8b57172f28cc7f`. No Stirling binary was installed or runtime benchmarked. No Stirling code, engine, assets or branding are included in Paperlight.

Sources: [tool catalog](https://docs.stirlingpdf.com/Tools/), [where tools run](https://docs.stirlingpdf.com/Desktop/Where-Tools-Run/), [reference README](https://github.com/Stirling-Tools/Stirling-PDF/blob/5bd8181777c08bff5544abcc4c8b57172f28cc7f/README.md), [reference license](https://github.com/Stirling-Tools/Stirling-PDF/blob/5bd8181777c08bff5544abcc4c8b57172f28cc7f/LICENSE).

Stirling distinguishes desktop-local processing from server/cloud processing. Its documentation says OCR and several conversions commonly require a backend. Its license has directory-specific exceptions. Paperlight therefore implements the agreed native-toolbox scope with its existing local libraries and bundled OCR, rather than embedding Stirling components. This is a functional comparison, not a full compatibility or parity claim.

| Tool family | Paperlight 1.1.0 coverage |
| --- | --- |
| Reader, editing, OCR, signing, protection | Existing native reader, object/text editing, English/Chinese OCR, visual signatures, forms, redaction, password controls |
| Compression | Lossless stream/object optimization; optional image recompression |
| Conversion/extraction | Image/PDF conversion, text export, embedded-image export, table CSV export |
| Review | Text comparison, document information, metadata and bookmark editing |
| Stamping | Searchable watermarks and formatted page numbers |
| Page operations | Insert, copy, rotate, reverse, retain/remove selected pages; existing split/merge/reorder |
| Layout | Crop, resize, multi-up, booklet, tiles, overlays, long-page join |
| Cleanup | Flatten, remove comments/images/blank pages/metadata, sanitize actions/attachments, unlock form flags, limited repair |
| Scan appearance | Grayscale, inversion and contrast exports with existing searchable text retained |
| Batch workflows | Up to 100 local inputs, up to 30 native transformation steps, reorder/update steps, save/load recipes |

## Using the toolbox

Choose **PDF tools** on the document toolbar or **Tools > PDF tools**, shortcut Ctrl+Shift+P. Search the tool list, choose options and export. The current-document option includes unsaved edits. Uncheck it to add local files. Multiple inputs use an output folder and distinct result names. Existing batch results are never silently overwritten.

Choose **Add tool to workflow** to build a chain of PDF transformations. Select a step to review it, change its options and use **Update selected step**. Save/load JSON recipes to reuse a chain. Recipes exclude file-specific PDF paths and passwords; an overlay file must be selected again after loading. Watermark text, bookmark text and metadata entered as options are included in an explicitly saved recipe.

All processing stays local and uses a separate worker. The toolbox adds no runtime dependency or document-upload feature. Results are exported atomically; source files are not changed and the current session's undo state is retained. Opening the toolbox stops active OCR, retaining completed recognition; restart Recognize text if needed. The edit preview resumes on returning to Edit PDF. Closing or cancelling a job stops the worker and cleans its staging folder during normal operation. Already-completed batch outputs remain available.

## Security and practical limits

PDF transformations retain the source encryption and both original passwords. A normally unencrypted source stays unencrypted even though Paperlight's internal working file has a random session password. Owner restrictions and copying permissions are enforced. Plain images, text, CSV, JSON and comparison reports cannot retain PDF encryption, so protected inputs require an explicit unencrypted-export choice. Pending redactions block tool exports.

Cropping only hides content. Watermarks and flattening do not prevent editing. Image removal is not a redaction tool. Sanitization removes active actions, links, attachments and metadata but is not an independent security certification or complete malicious-document disarm guarantee. The previous parser-sandboxing and release-signing limitations remain. Interruptions or application crashes may leave temporary output files; no secure-erasure guarantee is made.

Layout operations flatten fields and annotations into visible native page content. Scan color adjustments rasterize pages and recreate existing text as an invisible search layer; they cannot discover text without OCR. Comparison reports compare searchable text, not visual layout. Tables are detected from native text geometry; complex/scanned tables may require manual cleanup. Formula-leading CSV cells receive an apostrophe to prevent spreadsheet formula execution. Repair can only rebuild documents the local parser can open.

Limits include 1 GiB/PDF, 10,000 pages, 20,000-point page edges, bounded raster previews, 100 inputs and 30 workflow steps. Text exports are bounded to two million characters. Joining hundreds of pages into a single sheet can exceed the long-page limit. Compression does not promise a smaller file when the source is already optimized. Certificate signatures may be invalidated by exports that rewrite content.

Office/eBook/web conversion, certificate signing/trust validation, network timestamps, AI models, automatic form detection, portfolios/attachment management and server integrations are outside the scope selected for this release. No cloud badge or inactive placeholder claims those capabilities. Existing drawn/image signatures remain visual signatures.
