param(
    [switch]$SkipInstaller,
    [switch]$Release,
    [string]$CertificateThumbprint,
    [string]$SignToolPath,
    [uri]$TimestampServer = 'https://timestamp.digicert.com'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($Release) {
    if ($CertificateThumbprint -notmatch '^[0-9A-Fa-f]{40}$') { throw 'A verified publisher code-signing certificate thumbprint is required for a public release.' }
    if (-not $SignToolPath -or -not (Test-Path -LiteralPath $SignToolPath -PathType Leaf)) { throw 'Provide the Windows SDK signtool.exe path.' }
    $SignToolPath = (Resolve-Path -LiteralPath $SignToolPath).Path
    if ($TimestampServer.AbsoluteUri -notmatch '^https://[A-Za-z0-9.-]+(/[A-Za-z0-9._~/-]*)?$') { throw 'Use an HTTPS RFC 3161 timestamp endpoint without credentials, query parameters or shell characters.' }
    $certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint"
    if (-not $certificate.HasPrivateKey -or $certificate.Subject -eq $certificate.Issuer -or $certificate.NotAfter -le (Get-Date)) { throw 'A current CA-issued certificate with an accessible private key is required.' }
    if ('1.3.6.1.5.5.7.3.3' -notin $certificate.EnhancedKeyUsageList.ObjectId) { throw 'The certificate must allow code signing.' }
    $chain = [System.Security.Cryptography.X509Certificates.X509Chain]::new()
    try { if (-not $chain.Build($certificate)) { throw 'Publisher certificate trust or revocation validation failed.' } } finally { $chain.Dispose() }
}
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $pythonExe -m PyInstaller --noconfirm --noupx --windowed --onedir --name Paperlight --icon assets\paperlight.ico --add-data 'assets;assets' --add-data 'LICENSE;.' --add-data 'THIRD_PARTY_NOTICES.md;.' --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick main.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
& $pythonExe tools\fix_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime dependency validation failed.' }
if ($Release) {
    & $SignToolPath sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampServer.AbsoluteUri /td SHA256 'dist\Paperlight\Paperlight.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Application signing failed.' }
    & "$PSScriptRoot\verify-release.ps1" -Path 'dist\Paperlight\Paperlight.exe' -CertificateThumbprint $CertificateThumbprint
} else { Write-Warning 'Development build is unsigned. Do not publish it as a trusted signed release.' }
& $pythonExe tools\package_source.py
if ($LASTEXITCODE -ne 0) { throw 'Source packaging failed.' }
if ($SkipInstaller) { return }
$compiler = Join-Path $projectRoot '.scratch\tools\inno\ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Inno Setup compiler is missing. See README.md.' }
if ($Release) {
    # Inno substitutes $f with the quoted setup/uninstaller filename.
    $signCommand = '"' + $SignToolPath + '" sign /sha1 ' + $CertificateThumbprint + ' /fd SHA256 /tr "' + $TimestampServer.AbsoluteUri + '" /td SHA256 $f'
    & $compiler '/DReleaseSigning' "/Spaperlight=$signCommand" packaging\paperlight.iss
} else { & $compiler packaging\paperlight.iss }
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
if ($Release) {
    & "$PSScriptRoot\verify-release.ps1" -Path 'dist\Paperlight-Setup.exe' -CertificateThumbprint $CertificateThumbprint
}
