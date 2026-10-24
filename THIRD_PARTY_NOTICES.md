# Third-party notices

Paperlight is distributed under AGPL-3.0-or-later. Corresponding application source, build scripts and bundled OCR data are supplied in `source/paperlight-source.zip` in the installed application. You can also run the source with an ordinary Python installation.

- PyMuPDF / MuPDF 1.28.2: Artifex Software, AGPL-3.0-or-later. Source: https://github.com/pymupdf/PyMuPDF/tree/1.28.2 and https://mupdf.com/releases/ . Its binaries include Tesseract OCR support and bundled font resources; upstream notices are included in the Python distribution's licensing files.
- PySide6 / Qt for Python 6.12.0: The Qt Company and contributors, LGPL-3.0 / GPL-3.0 / commercial licensing. This application uses the LGPL option for the Qt Core, GUI and Widgets modules. Qt remains in replaceable shared DLLs in `_internal/PySide6`. Source and license materials: https://code.qt.io/pyside/pyside-setup.git and https://download.qt.io/official_releases/QtForPython/ . See `assets/licenses` for the bundled license texts.
- Tesseract OCR and tessdata_fast language models: Apache-2.0. English, Simplified Chinese, Traditional Chinese. https://github.com/tesseract-ocr/tesseract and https://github.com/tesseract-ocr/tessdata_fast . Model files are unchanged from upstream. License text is in `assets/licenses/Tesseract-LICENSE`.
- Python 3.12: Python Software Foundation license. https://www.python.org/psf/license/ . The Python runtime is bundled by PyInstaller.
- PyInstaller 6.22.3 bootloader: GPL-2.0-or-later with its distribution exception. https://pyinstaller.org/en/stable/license.html . This exception permits distribution of the generated application under the application's own license.
- Pillow 13.0.0, used by the build/test tools: MIT-CMU. https://github.com/python-pillow/Pillow .
- Inno Setup compiler: Jordan Russell and Martijn Laan. https://jrsoftware.org/isinfo.php . The compiler itself is not bundled with the app.

No Apple program files, icons, code or other proprietary assets are included. Workflow references and the REA evidence boundary are documented in `docs/rea-findings.md` in the source archive.

- pypdf 6.21.1: BSD-3-Clause, used to parse and serialize bounded PDF content streams for object editing. https://github.com/py-pdf/pypdf . License text: assets/licenses/pypdf-LICENSE.
