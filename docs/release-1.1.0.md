# Paperlight 1.1.0

Adds a searchable native offline PDF toolbox, based on the user-selected Stirling comparison scope. Open **PDF tools** on the document toolbar, **Tools > PDF tools**, or Ctrl+Shift+P.

The 36 tools cover compression, image/PDF conversion, text/table/image extraction, text comparison, document information, metadata/bookmarks, watermarks/page numbers, page operations, layouts, cleanup, repair and scan color adjustments. Workflows chain up to 30 transformations across up to 100 input PDFs, with save/load, reorder and step editing. English and Simplified Chinese interfaces are included.

All processing runs locally in a separate process. No new runtime dependency, server, account or network service is required. Tools export copies, use current unsaved edits when requested, preserve source PDF encryption and enforce owner/copy restrictions. Protected inputs require explicit consent before producing unencrypted image, text or report exports. Pending redactions block exports. Batch files get distinct names, and input files are never overwritten by these tools.

Read the [comparison and toolbox guide](stirling-offline-study-1.1.0.md) for the detailed feature mapping, usage, security behavior and limits. Layout operations flatten forms and annotations. Cropping is not redaction; watermarks/flattening are not edit protection. Scan color tools rasterize appearance and retain existing text as an invisible layer. Text comparison is not visual comparison; table extraction depends on native/OCR geometry. Office/web conversion, local AI, certificate signing/trust validation and server features were outside the selected scope.

The installer and executable remain unsigned. This release is not independently security-certified or approved for regulated production use. The earlier internal assessment's parser-isolation, signing and independent-review gates remain open.

Downloads include the Windows installer, portable application, corresponding source archive and SHA-256 checksums. Source, packaged-tool, OCR, encrypted-file and installed-application checks are recorded in the versioned verification reports.

## Verification

142 source tests passed, including 48 toolbox checks. The frozen worker passed all 36 tool paths, image recompression, JPEG export, encrypted layout export and multi-file workflows. The packaged reader, English/Chinese OCR, protected-file handling and edit previews also passed. Installed checks are recorded separately.
