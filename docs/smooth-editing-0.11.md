# Editing interactions in 0.11

Edit PDF now retains its Qt outlines, handles and guide lines between mouse events. Moving or rotating an object transforms a cached raster layer instead of rendering or parsing the PDF on every mouse movement. Page rendering and object analysis run in a separate persistent process. Only a completed gesture writes the PDF and creates an undo entry. Escape cancels the active gesture.

Select a supported shape or image, then drag to move it, drag a corner to resize it, or drag the round handle above it to rotate. Shift snaps rotation to 15 degrees and keeps corner scaling proportional. Right-click > Rotate object accepts an exact angle. Arrow keys move the selected graphic by one PDF point; Shift+arrow moves it by ten.

Right-click a supported native shape > Edit points to expose its anchors and cubic curve controls. Drag an anchor to reshape the path; neighboring curve controls follow its anchor. Drag a control independently to change the curve. Shift constrains point motion horizontally or vertically. Point mode remains active after the edit commits. This edits existing points; inserting/deleting nodes, converting scans to vectors and general CAD constraints are outside this release.

The preview divides source commands into background, selected object and foreground layers. Foreground content continues to cover the selected object during dragging. The writer preserves the original source scope and paint/style commands, changing its geometry. Complex, clipped or unverified source graphics remain read-only. A scan contains pixels, so shapes inside it cannot acquire vector handles through OCR.

The renderer receives the encrypted working-file password through stdin, closes its document after each request, and writes only bounded PNG/JSON output through pipes. It creates no plaintext preview files. Results carry revision checks. The GUI stops the worker before a conflicting mutation or session close. Separate processes improve responsiveness; they are not an OS security sandbox or certification.

## OCR decision

The current Tesseract engine remains bundled. A separate benchmark environment tested RapidOCR 3.10.0 with ONNX Runtime 1.31.0, CPU models PP-OCRv6_det_small, ch_ppocr_mobile_v2.0_cls_mobile and PP-OCRv6_rec_small. Public models were downloaded for local testing; document images were not uploaded. RapidOCR and its models are not added to the application runtime.

On one synthetic scanned page containing English, Simplified Chinese and Traditional Chinese at 160 dpi, three Tesseract runs took 0.346, 0.341 and 0.334 seconds including rasterization. RapidOCR consumed the pre-rendered image and took 1.936, 0.818 and 0.819 seconds. Rendering the image separately took 0.039 seconds. RapidOCR initialization was lazy, so the first inference includes model startup. Both recognized the expected strings after whitespace normalization. RapidOCR grouped the Chinese lines better, but did not justify replacing the faster current engine on this sample.

This is a narrow CPU comparison, not evidence about hundreds of pages, skewed/noisy scans, GPU acceleration or every document. A future engine change needs a representative corpus, accuracy scoring, explicit offline model packaging, model license review and packaged-device verification. The 0.11 work makes rendering and discovery asynchronous and keeps the existing separate OCR process. It does not claim a faster OCR model.

## Implementation references

- [Qt graphics items](https://doc.qt.io/qt-6/qgraphicsitem.html) for retained transforms and scene interactions.
- [Qt painter paths](https://doc.qt.io/qt-6/qpainterpath.html) for cubic curve previews.
- [Qt Elastic Nodes example](https://doc.qt.io/qt-6/qtwidgets-graphicsview-elasticnodes-example.html) for movable controls.
- [RapidOCR source](https://github.com/RapidAI/RapidOCR) for the evaluated alternative engine.

No Adobe binary was inspected and no Adobe source was copied. This release uses the existing native Qt interface and verified PDF content writer.

## Verification

The final source suite passed 83 tests. Focused cases cover arbitrary-angle image transforms, path-coordinate persistence, invalid-path rollback, saved-file reopening, neighboring content, shared image instances, preview layer composition at page rotations 0 and 90, canceled rotation, one undo per drag, retained scene-item identity, point-mode persistence and keyboard nudges. A final focused run passed all five interaction/geometry cases.

A synthetic offscreen rotation test processed 120 mouse events at a median 0.95 ms and p95 1.27 ms per event. This measures event processing on the test machine, excluding display presentation and the final commit. It does not guarantee 60 fps on large or complex PDFs. The page preview and point controls were also rendered and visually checked.

See `tests-0.11.log`, `editor-tests-0.11.log` and `ocr-comparison-0.11.json` for evidence. Packaged/installed verification is recorded separately. The earlier security assessment is not a certification of this version.
