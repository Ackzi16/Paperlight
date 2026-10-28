param(
    [Parameter(Mandatory=$true)][string[]]$Path,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9A-Fa-f]{40}$')][string]$CertificateThumbprint
)
$ErrorActionPreference = 'Stop'
foreach ($releasePath in $Path) {
    $resolved = (Resolve-Path -LiteralPath $releasePath).Path
    $signature = Get-AuthenticodeSignature -LiteralPath $resolved
    if ($signature.Status -ne 'Valid') { throw "Public release blocked: $resolved has no valid trusted Authenticode signature." }
    if ($signature.SignerCertificate.Thumbprint -ne $CertificateThumbprint) { throw "Public release blocked: unexpected publisher for $resolved." }
    if (-not $signature.TimeStamperCertificate) { throw "Public release blocked: $resolved has no verified timestamp." }
    if ($signature.SignerCertificate.Subject -eq $signature.SignerCertificate.Issuer) { throw 'Self-signed publisher certificates are not accepted.' }
    Write-Output "Verified trusted publisher signature and timestamp: $resolved"
}
