# PDF password protection

Paperlight 0.5 adds File > Protect PDF… / 文件 > 保护 PDF… . Each export offers:

| Choice | Benefit | Limitation |
| --- | --- | --- |
| Owner password, no opening password | Everyone can read; supporting readers require the owner password for editing | Some tools bypass permission flags |
| Opening password plus a different owner password | AES-256 encrypts contents until either password is provided; supporting readers distinguish readers from editors | Password sharing and screenshots remain possible; editing restrictions are viewer-enforced |

Printing and text/image copying are independently optional. Editing content, annotations, form filling and page assembly are disabled in the protected output. Accessibility access remains enabled. Both modes use AES-256; with no opening password the empty reader password lets anyone decrypt the file for viewing. This is not confidentiality protection.

Use long, unique passwords and keep the owner password separately. Passwords are limited to 40 UTF-8 bytes for compatibility with the bundled PDF library; Chinese characters usually use three bytes each. Passwords are case-sensitive and spaces are preserved. Opening and owner passwords must differ. Paperlight does not store them in preferences or provide password recovery.

Protection saves a new file and preserves the original. The current editing session stays unlocked, including undo. Pending redactions must be applied or undone before export. Applied redactions are sanitized before encryption. Ordinary Save copy does not add cached OCR; first export a searchable copy and open that copy if you want the OCR layer included in a protected PDF.

Protected PDFs with editing restrictions open read-only in Paperlight unless authenticated as owner. Navigation, search and OCR remain available. Copy follows the file's copy permission. Paperlight conservatively disables all editing and exports when a document restricts any editing permission. File > Unlock editing… checks the owner password. After unlocking, Save preserves the current file's encryption, both passwords and permissions. Ordinary Save copy creates an unencrypted copy and asks for confirmation; Protect PDF applies new protection. A restricted PDF also needs its owner password before insertion into another PDF.

Encrypted inputs use a temporary OCR cache in their session folder, removed on normal close. Encrypted inputs retain encryption in their editing working file. OCR data and temporary index snapshots can contain decrypted content while the file is open; crashes can leave temporary files. This feature protects exported PDFs, not an unlocked Windows session or local disk. Windows disk encryption is a separate control.

For detecting later tampering, a certificate-based digital signature is another option. It lets a validating reader report changes after signing, rather than preventing them. Paperlight's drawn and imported signatures are visual marks, not digital signatures. Certificate signing, recipient-certificate encryption, online revocation and rights-management services are not included in this release.

References: [Adobe permissions and security methods](https://www.adobe.com/devnet-docs/acrobatetk/tools/DigSig/Acrobat_Reader_SecurityMethods.pdf), [PyMuPDF encryption and permissions](https://pymupdf.readthedocs.io/en/latest/the-basics.html).
