param(
    [string]$FFmpegBin = "",
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ($PythonPath) {
    $PythonExecutable = (Resolve-Path -LiteralPath $PythonPath).Path
} else {
    $PythonCandidates = @()
    if ($env:VIRTUAL_ENV) {
        $PythonCandidates += Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
    }
    $PythonCandidates += Join-Path $ProjectRoot "venv\Scripts\python.exe"
    $PythonCandidates += Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $PathPython = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($PathPython) {
        $PythonCandidates += $PathPython.Source
    }
    $PythonExecutable = $PythonCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
    if (-not $PythonExecutable) {
        throw "Python was not found. Activate the development environment or pass -PythonPath."
    }
}

if ($FFmpegBin) {
    $ResolvedBin = (Resolve-Path -LiteralPath $FFmpegBin).Path
} else {
    $FFmpegCommand = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    $FFprobeCommand = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
    if (-not $FFmpegCommand -or -not $FFprobeCommand) {
        throw "FFmpeg and FFprobe were not found. Pass -FFmpegBin C:\path\to\ffmpeg\bin."
    }
    $FFmpegDirectory = Split-Path -Parent $FFmpegCommand.Source
    $FFprobeDirectory = Split-Path -Parent $FFprobeCommand.Source
    if ($FFmpegDirectory -ne $FFprobeDirectory) {
        throw "FFmpeg and FFprobe must come from the same bin directory. Pass -FFmpegBin explicitly."
    }
    $ResolvedBin = $FFmpegDirectory
}

foreach ($Tool in @("ffmpeg.exe", "ffprobe.exe")) {
    $ToolPath = Join-Path $ResolvedBin $Tool
    if (-not (Test-Path -LiteralPath $ToolPath -PathType Leaf)) {
        throw "Required binary not found: $ToolPath"
    }
}

$env:KYYKKA_FFMPEG_BIN = $ResolvedBin
try {
    & $PythonExecutable -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath (Join-Path $ProjectRoot "dist") `
        --workpath (Join-Path $ProjectRoot "build") `
        (Join-Path $ProjectRoot "packaging\kyykka_editor.spec")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
} finally {
    Remove-Item Env:KYYKKA_FFMPEG_BIN -ErrorAction SilentlyContinue
}

$OutputDirectory = Join-Path $ProjectRoot "dist\KyykkaEditor"
Copy-Item `
    -LiteralPath (Join-Path $ProjectRoot "LICENSE") `
    -Destination (Join-Path $OutputDirectory "LICENSE") `
    -Force
Copy-Item `
    -LiteralPath (Join-Path $ProjectRoot "THIRD_PARTY_NOTICES.md") `
    -Destination (Join-Path $OutputDirectory "THIRD_PARTY_NOTICES.md") `
    -Force
$RequiredOutput = @(
    (Join-Path $OutputDirectory "KyykkaEditor.exe"),
    (Join-Path $OutputDirectory "_internal\kyykka_editor\bin\ffmpeg.exe"),
    (Join-Path $OutputDirectory "_internal\kyykka_editor\bin\ffprobe.exe"),
    (Join-Path $OutputDirectory "LICENSE"),
    (Join-Path $OutputDirectory "THIRD_PARTY_NOTICES.md")
)
foreach ($OutputPath in $RequiredOutput) {
    if (-not (Test-Path -LiteralPath $OutputPath -PathType Leaf)) {
        throw "Package is incomplete; expected file not found: $OutputPath"
    }
}

Write-Host "Package created at $OutputDirectory"
