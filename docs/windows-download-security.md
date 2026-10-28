# Windows download warning and security changes

Assessment date: 28 October 2026. Local candidate: Paperlight 1.1.1.

The user reported Edge calling the download unsafe or uncommon. No exact threat
name or Microsoft verdict was supplied. The 1.1.0 executable and installer are
unsigned. Unknown file or publisher reputation is a plausible explanation, not a
confirmed Microsoft diagnosis. A SHA-256 checksum verifies file identity; it is
neither a publisher signature nor a malware certificate.

## Changes

- Update pypdf from 6.21.1 to 6.21.2. The upstream release fixes three malformed
  PDF denial-of-service advisories: GHSA-6c7f-9265-g8fw, GHSA-jr96-gvgh-j3r4 and
  GHSA-gmh7-3g9r-mjh5. Also remove an older dependency pin from the build guide.
- Give each toolbox export a newly created private staging subdirectory. An
  existing `result-0000.pdf` in a caller-selected staging folder is never used
  or deleted as a temporary output.
- Validate toolbox child-process message types, numeric bounds, result paths,
  duplicates and completion accounting before displaying or opening results.
  This validation does not confine a compromised native parser.
- Disable installer automatic closing of running applications.
- Explicitly disable UPX compression in development and release builds. This
  is a packaging choice, not evidence that UPX caused the warning.
- Add a separate signed release mode. It requires a CA-issued code-signing
  certificate, private-key access, Windows trust validation and RFC 3161
  timestamps. Sign the application, installer and uninstaller. Block unsigned
  or unexpected publisher output at the release verification step.

## Verification and remaining limits

All 155 automated tests pass. The packaged application passes English/Chinese
OCR, protected-document reading, persistent edit rendering and all 36 toolbox
checks. The patched local installer was installed as 1.1.1 without closing a
running user session. The installed executable's SHA-256 matches the tested
package. Installed OCR/reader and toolbox checks are recorded alongside the
dependency and static-analysis evidence in `security-audit-2026-10-28/`.

The dependency audit after the update reports no known advisories for the nine
resolved Python distributions. This does not cover every bundled native library
or prove that the application is malware-free. Bandit reports 14 low-severity
findings and no medium/high findings. The low findings concern empty password
defaults, a translated password label and best-effort font/destructor cleanup;
they are not embedded credentials. These findings were reviewed without adding
scanner suppression rules.

Windows Defender reports its antivirus service and real-time protection inactive
on this computer. Empty local threat records therefore do not establish a clean
Defender scan. No Defender settings, exclusions, trust roots, SmartScreen settings
or browser safety settings were changed.

Native PDF parsing is still not contained by an OS sandbox. The app is offline
by implementation, not by an OS-enforced network prohibition. The earlier
[regulated-document assessment](security-audit-2026-10-19/assessment.md) remains
unresolved and this update is not independent security certification.

## Publishing a trusted release

There is no usable code-signing identity in the current user's certificate store.
The local development candidate remains unsigned and must not be described as
Microsoft-approved or guaranteed warning-free.

For GitHub distribution, obtain a verified publisher identity and a publicly
trusted code-signing certificate with protected private-key access. This build
mode supports a certificate exposed in the current user's Personal certificate
store, including compatible hardware-backed providers. Cloud signing needs its
provider integration instead of passing private keys or passwords on a command
line. Do not commit signing credentials or create a locally trusted self-signed
publisher certificate as a workaround.

With a real certificate and Windows SDK SignTool installed:

```powershell
.\tools\build.ps1 -Release -CertificateThumbprint '<40-hex publisher thumbprint>' -SignToolPath 'C:\path\to\signtool.exe'
```

The SHA-1 thumbprint selects the certificate; file signatures and timestamps use
SHA-256. Verify signatures again after copying final assets, run packaged
functional checks, scan those exact final files with an active maintained malware
scanner, then compute public SHA-256 checksums. The successful signing path has
not been exercised because no signing identity is available. The unsigned
release rejection path has been checked.

Microsoft Store distribution is the recommended route for avoiding SmartScreen
download warnings. It requires a verified publisher account, appropriate Store
packaging and Microsoft's submission review. Direct signed downloads can still
warn while reputation develops. No source change can guarantee Microsoft's
future classification.

Sources:

- [Microsoft SmartScreen reputation guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
- [Microsoft SignTool reference](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
- [Inno Setup signing](https://jrsoftware.org/ishelp/topic_setup_signtool.htm)
- [pypdf repeated missing-object advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-6c7f-9265-g8fw)
- [pypdf malformed cross-reference advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-jr96-gvgh-j3r4)
- [pypdf cross-reference header advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-gmh7-3g9r-mjh5)
