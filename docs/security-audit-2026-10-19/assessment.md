# Paperlight 0.8 internal security assessment

Assessment date: 19 October 2026, Asia/Singapore. Target: regulated or highly sensitive documents on Windows.

**Decision: NOT CERTIFIED. The assessed release is not approved by this assessment for regulated production use.** Hardening and internal checks are complete; unresolved high-risk architecture and release-trust gaps require further engineering and independent assessment. This document is not an independent penetration-test report, a compliance determination, or a certification. The same development assistant performed the review and remediation.

## Scope and evidence

Reviewed the runtime Python source, document/OCR data paths, encryption, redaction, signatures, saving, process invocation, packaging scripts and the executable distribution. Used synthetic documents only for active tests. User documents were not uploaded or used as attack samples. Online queries concerned public package names/versions, vendor documentation and public advisories. The package build and installed-executable smoke results are recorded separately in release-verification.json after packaging.

Automated evidence:

- 63 tests passed. See audit-full-tests.log and tests/test_security_audit.py in the source archive. These are functional and targeted adversarial checks, not proof against all attacks.
- pip-audit reported 0 listed vulnerabilities in the resolved Python requirements. This result does **not** establish that bundled MuPDF, Qt, Tesseract or other native components are free of vulnerabilities.
- Bandit reported 11 low-severity findings, individually reviewed in static-triage.json. Its recorded medium/high findings are zero. Bandit checks Python patterns, not native parser memory safety.
- Runtime under test: Python 3.12.14, PyMuPDF 1.28.2, MuPDF 1.28.2. The PDF engine was updated from PyMuPDF 1.26.7 / MuPDF 1.26.12.
- The limited runtime literal scan found 0 matching private-key/API-key patterns. It is not an exhaustive secret detector or a history scan.
- The CycloneDX SBOM describes resolved Python packages. It is not a complete inventory of every vendored native codec. Release SHA-256 hashes identify the exact files; hashes alone do not authenticate a publisher.

## Threat model

Assets include PDF contents, OCR text, passwords, signature strokes and original file integrity. Considered untrusted/malformed PDF input, altered local cache data, crash leftovers, accidental plaintext storage, a competing file writer and tampered application distribution. The Windows account and OS are assumed trustworthy for current-user DPAPI. Malware or an administrator acting as that user, RAM inspection, swap/hibernation, cloud synchronization, backups, disk forensics and enterprise policy compliance are outside the protection claimed by the app.

## Findings and changes

| ID | Severity before | Finding | Treatment in 0.8 |
| --- | --- | --- | --- |
| F01 | High | Working/index snapshots of unencrypted inputs could retain readable content after a crash | New working PDFs for those inputs use random per-session AES-256 passwords; index snapshots retain working-file encryption. Keys are not written to preferences or command lines. Existing encrypted inputs retain their existing security, including weak or publicly readable settings. |
| F02 | High | OCR indexes persisted as plaintext JSON | DPAPI current-Windows-user encryption with integrity checking; session-only by default. Persistent encrypted indexing requires an explicit Tools option. Password-protected inputs remain session-only. Known old search-v3 caches are removed on startup, with a warning on failure. |
| F03 | Medium | Saved signature names/strokes were plaintext | Current-user DPAPI, atomic encrypted writes, validation and automatic migration of valid existing libraries. No plaintext fallback or backup. Cross-user recovery was not tested. Windows account/key loss can prevent recovery. |
| F04 | High | Stale native parser and insufficient independent redaction verification | Updated to the latest stable PyMuPDF available during review. A post-redaction native/hidden-text check fails closed if marked text remains. Redacted output also removes outline titles. Synthetic quote-operator regression coverage is included. No claim that every upstream vulnerability is fixed. |
| F05 | Medium | Cached records, signature data and worker messages lacked strict integrity/shape bounds | Added authenticated storage, finite-coordinate/schema/size checks, page/index path validation and a 32 MiB worker-message bound. Invalid worker metadata stops the worker. |
| F06 | Medium | OCR could allocate an oversized raster or stall indefinitely | 32 million estimated OCR pixels per page, 90-second inactivity watchdog, 1 GiB file limit, 10,000 pages, 20,000-point page-edge limit and 120 million declared image pixels. These checks are not complete resource isolation and can run only after initial native parsing. |
| F07 | Low | Document-sourced text could be treated as rich text and startup diagnostics could retain document details | Runtime labels and error boxes use plain text; new startup logs record exception type/time without document names, paths or exception values. Existing older logs are not retroactively scrubbed. |

## Verified controls

Tests cover DPAPI round-trip, purpose binding and modified-ciphertext rejection; no plaintext fallback when protection fails; valid legacy signature migration; encrypted temporary PDFs; corrupted-cache rebuilding; private-cache cleanup on normal close; bounded OCR before rasterization; worker timeout; plaintext-free startup diagnostics; rejection of invalid worker cache keys; and oversized page rejection.

Existing tests cover both PDF passwords and permission flags, read-only handling until owner unlock, redacted text/image/form removal, native/OCR text search, atomic file saving, external-change detection, failed writes, and undo/redo. A synthetic PDF Launch action was not dispatched through the application launch APIs instrumented by the test. A Python socket guard detected no network attempt during the tested extraction/save path. Neither test proves the absence of native-code network activity or execution under all malicious inputs.

Application code has no document-upload feature, browser engine, automatic PDF link launcher, PDF JavaScript dispatcher, or shell-command construction from document contents in the reviewed paths. Offline architecture is not an OS-enforced network deny rule.

## Unresolved release gates

| ID | Severity | Gap and required work |
| --- | --- | --- |
| R01 | High | Native PDF/font/image parsing still occurs in the GUI and ordinary user-level worker processes. A separate process is not a Windows sandbox. Move all untrusted parsing/rendering/editing behind a restricted AppContainer or equivalent broker design, enforce memory/CPU/file/network limits, and test escapes in an isolated VM. |
| R02 | High | Application and installer are unsigned. Establish trusted Authenticode or signed MSIX distribution, protected signing keys, dependency/build provenance and update verification. SHA-256 manifests do not replace publisher authentication. |
| R03 | High until reviewed | 48 historical paperlight-edit-* temporary folders were observed. Their contents were neither inspected nor deleted; they may contain synthetic test files or unsaved user work from earlier versions. Review/recover needed work and remove obsolete data under an approved retention process. Old crash logs/backups/cloud versions may also retain information. No secure-deletion or retroactive cleanup guarantee. |
| R04 | Medium/High by policy | DPAPI protects at rest for the Windows identity, not against code running as that identity. Use managed device encryption, separate accounts, endpoint protection, controlled backups and appropriate crash-dump/clipboard policies. AES-256 PDF permissions do not prevent an authorized reader from taking screenshots or using a reader that ignores editing restrictions. |
| R05 | Open | No independent binary penetration test, native fuzz campaign, complete native-library CVE inventory, organization-specific classification/retention/access controls, or tamper-evident enterprise activity logging has been completed. Scope these with the assessor and the data owner. |

Saving or exporting an intentionally unencrypted PDF still writes plaintext to the selected destination and its atomic staging file. Original input PDFs may already be plaintext. PDF working copies of documents with an empty opening password inherit that publicly readable security. Use an opening password and managed disk protection where the approved policy requires confidentiality. Python memory cannot be guaranteed erased, and a crash can leave encrypted temporary data. No sensitive-data readiness claim is based solely on the passing test count.

## Certification and independent-assessment handoff

1. Choose the applicable organizational/customer/regulatory profile and agree on a data-flow/threat-model scope. “SHA-256 security” is not a certification.
2. Resolve R01/R02 and review legacy storage under R03. Adopt a maintained dependency/native-advisory inventory, release approval and patch-response process.
3. Give an independent qualified assessor the exact release hashes, source inventory, SBOM, this report and raw results. Request Windows binary/installer testing, malicious-document tests in an isolated VM, crypto/key/storage review, sandbox/egress escape tests and a remediation retest.
4. If a specific certification is required, engage its recognized assessment route. ISO/IEC 27001 concerns an organization's ISMS; this app has no such certificate. FIPS 140 validation concerns an evaluated cryptographic module/configuration; using AES-256 or Windows DPAPI does not certify Paperlight. No FIPS, Common Criteria, ISO, HIPAA, PDPA or GDPR compliance claim is made here.

No certification was issued, no external assessor was contacted, and no continuous monitoring was configured by this task.

## References

- [NIST SSDF SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final), used as a review framework, not a certification checklist.
- [Microsoft CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata), current-user scope and integrity protection.
- [PyMuPDF vendor change log](https://raw.githubusercontent.com/pymupdf/PyMuPDF/main/changes.txt), version history and upstream regressions. Regression verification here is scoped to the tests, not all PDF constructs.
- [CERT VU#951662](https://kb.cert.org/vuls/id/951662), native MuPDF advisory and isolation guidance. Python package scanner results do not resolve native advisory applicability by themselves.
- [NIST CMVP](https://csrc.nist.gov/Projects/cryptographic-module-validation-program/faqs), module validation scope.
- [ISO/IEC 27001](https://www.iso.org/standard/27001), organizational ISMS scope.

## Reproduction

Run `.venv/Scripts/python.exe -m pytest -q`. Install pip-audit/Bandit in a separate audit environment, then run `python -m pip_audit -r requirements.txt -f json` and `python -m bandit -r paperlight main.py -f json`. Source/artifact hashes and tool outputs apply to this assessed snapshot and date only. Do not run real exploit samples against an everyday workstation.
