"""Prepare a local internal assessment and release inventory, not a certificate."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'docs'/'security-audit-2026-10-19'
RAW=ROOT/'tmp'/'verification'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    # Release-specific hashes are created after the build and shipped in the
    # evidence bundle, not recursively embedded in their own source archive.
    for name in ('release-sha256.json','release-verification.json','authenticode-after.json'):
        (OUT/name).unlink(missing_ok=True)
    for name in ('dependency-audit-before.json','dependency-audit-after.json','bandit-before.json',
                 'bandit-after.json','sbom.cdx.json','runtime-audit.json','authenticode-before.json','audit-full-tests.log'):
        shutil.copyfile(RAW/name,OUT/name)
    static=json.loads((OUT/'bandit-after.json').read_text())
    dependencies=json.loads((OUT/'dependency-audit-after.json').read_text())
    testlog=(OUT/'audit-full-tests.log').read_text()
    passed=int(re.search(r'(\d+) passed',testlog).group(1))
    vulns=sum(len(d.get('vulns',[])) for d in dependencies['dependencies'])
    runtime=json.loads((OUT/'runtime-audit.json').read_text())
    triage=[]
    for result in static['results']:
        reason=('Empty-password defaults support intentionally unprotected/publicly readable PDFs, or this is a translated UI label. No hardcoded secret.'
                if result['test_id'] in ('B105','B107') else
                'Destructor cleanup is best effort; normal close performs cleanup. Crash remnants remain a documented limitation.'
                if result['test_id']=='B110' else
                'A font candidate that cannot be parsed is skipped in favor of the next candidate. Missing-font fallback is disclosed in the editor.')
        triage.append(dict(file=result['filename'],line=result['line_number'],test=result['test_id'],
                           severity=result['issue_severity'],disposition='reviewed',reason=reason))
    (OUT/'static-triage.json').write_text(json.dumps(triage,indent=2),encoding='utf-8')
    files=[ROOT/'main.py',ROOT/'requirements.txt',ROOT/'packaging'/'paperlight.iss']
    files+=list((ROOT/'paperlight').glob('*.py'))+list((ROOT/'tools').glob('*.py'))+list((ROOT/'tools').glob('*.ps1'))
    source=[dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p)) for p in sorted(files)]
    (OUT/'source-inventory.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
    patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'\bAKIA[A-Z0-9]{16}\b',r'\bsk-[A-Za-z0-9]{30,}\b']
    matches=[]
    for path in [ROOT/'main.py',*(ROOT/'paperlight').glob('*.py')]:
        for number,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
            if any(re.search(pattern,line) for pattern in patterns):
                matches.append(dict(path=path.relative_to(ROOT).as_posix(),line=number))
    (OUT/'limited-secret-scan.json').write_text(json.dumps(dict(scope='Runtime Python source; limited literal key patterns only',matches=matches),indent=2),encoding='utf-8')
    report=f'''# Paperlight 0.8 internal security assessment

Assessment date: 19 October 2026, Asia/Singapore. Target: regulated or highly sensitive documents on Windows.

**Decision: NOT CERTIFIED. The assessed release is not approved by this assessment for regulated production use.** Hardening and internal checks are complete; unresolved high-risk architecture and release-trust gaps require further engineering and independent assessment. This document is not an independent penetration-test report, a compliance determination, or a certification. The same development assistant performed the review and remediation.

## Scope and evidence

Reviewed the runtime Python source, document/OCR data paths, encryption, redaction, signatures, saving, process invocation, packaging scripts and the executable distribution. Used synthetic documents only for active tests. User documents were not uploaded or used as attack samples. Online queries concerned public package names/versions, vendor documentation and public advisories. The package build and installed-executable smoke results are recorded separately in release-verification.json after packaging.

Automated evidence:

- {passed} tests passed. See audit-full-tests.log and tests/test_security_audit.py in the source archive. These are functional and targeted adversarial checks, not proof against all attacks.
- pip-audit reported {vulns} listed vulnerabilities in the resolved Python requirements. This result does **not** establish that bundled MuPDF, Qt, Tesseract or other native components are free of vulnerabilities.
- Bandit reported {len(triage)} low-severity findings, individually reviewed in static-triage.json. Its recorded medium/high findings are zero. Bandit checks Python patterns, not native parser memory safety.
- Runtime under test: Python {runtime['python']}, PyMuPDF {runtime['pymupdf']}, MuPDF {runtime['mupdf']}. The PDF engine was updated from PyMuPDF 1.26.7 / MuPDF 1.26.12.
- The limited runtime literal scan found {len(matches)} matching private-key/API-key patterns. It is not an exhaustive secret detector or a history scan.
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
| R03 | High until reviewed | {runtime['legacy_temp_folder_count']} historical paperlight-edit-* temporary folders were observed. Their contents were neither inspected nor deleted; they may contain synthetic test files or unsaved user work from earlier versions. Review/recover needed work and remove obsolete data under an approved retention process. Old crash logs/backups/cloud versions may also retain information. No secure-deletion or retroactive cleanup guarantee. |
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
'''
    (OUT/'assessment.md').write_text(report,encoding='utf-8')


def release():
    files=[ROOT/'dist'/'Paperlight-Setup.exe',ROOT/'dist'/'paperlight-source.zip']
    files+=list((ROOT/'dist'/'Paperlight').rglob('*'))
    rows=[dict(path=p.relative_to(ROOT/'dist').as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(files) if p.is_file()]
    manifest=dict(product='Paperlight',version='0.8.0',assessment='Internal only; not certified',files=rows)
    (OUT/'release-sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    shutil.copyfile(RAW/'package-verification.json',OUT/'release-verification.json')
    print(json.dumps(dict(files=len(rows),installer_sha256=next(r['sha256'] for r in rows if r['path']=='Paperlight-Setup.exe'))))


if __name__=='__main__':
    release() if '--release' in sys.argv else prepare()
