param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = "Stop"
$File = Get-Item -LiteralPath $Path
if ($File.PSIsContainer) {
    throw "Expected a file: $Path"
}
$Hash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
# Standard sha256sum format, UTF-8 without a BOM, using a relative filename.
$ChecksumPath = Join-Path $File.DirectoryName "sha256.txt"
$Utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($ChecksumPath, "$Hash  $($File.Name)`n", $Utf8)
Write-Host "Checksum created at $ChecksumPath"
