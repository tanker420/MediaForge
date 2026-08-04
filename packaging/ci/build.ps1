# ============================================================
#  MediaForge Windows build script (PyInstaller + Inno Setup)
#  Used by GitHub Actions and local PowerShell:
#    powershell -ExecutionPolicy Bypass -File packaging\ci\build.ps1
#  NOTE: This file is intentionally ASCII-only (no Chinese chars)
#  so it parses correctly under Windows PowerShell 5.1 regardless
#  of file encoding (no BOM required).
# ============================================================
param(
    [string]$Version = "1.0.0",
    [string]$PfxPath = "",
    [string]$PfxPassword = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # repo root
Set-Location $root

$Version = $Version.TrimStart('v')

Write-Host "==> MediaForge build started, version: $Version"

# ---------- 1. Sync version into packaging/version_info.txt ----------
# Single source of truth for runtime version is app\__init__.py.
# PyInstaller reads version_info.txt at build time, so we rewrite
# the file_version / product_version / version strings in place.
#
# CRITICAL (encoding): version_info.txt is UTF-8 WITHOUT BOM.
# Never use Get-Content/Set-Content here - Windows PowerShell 5.1
# decodes BOM-less UTF-8 as GBK/ANSI and corrupts the Chinese text.
# Use .NET APIs with an explicit UTF-8 encoding (identical on PS5.1 and PS7).
$versionInfoPath = "packaging\version_info.txt"
if (Test-Path $versionInfoPath) {
    $parts = $Version.Split('.')
    if ($parts.Count -lt 3) { $parts = @($parts[0], "0", "0") }
    $tuple = "($($parts[0]), $($parts[1]), $($parts[2]), 0)"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $vi = [System.IO.File]::ReadAllText((Resolve-Path $versionInfoPath), $utf8NoBom)
    $vi = $vi -replace 'filevers=\([^)]*\)', "filevers=$tuple"
    $vi = $vi -replace 'prodvers=\([^)]*\)', "prodvers=$tuple"
    $vi = $vi -replace "u'FileVersion', u'[^']*'", "u'FileVersion', u'$Version'"
    $vi = $vi -replace "u'ProductVersion', u'[^']*'", "u'ProductVersion', u'$Version'"
    [System.IO.File]::WriteAllText((Resolve-Path $versionInfoPath), $vi, $utf8NoBom)
    Write-Host "==> Synced version $Version into $versionInfoPath (UTF-8, no BOM)"
} else {
    Write-Host "==> WARNING: $versionInfoPath not found, version sync skipped"
}

# ---------- 2. FFmpeg (BtbN static build, no install needed) ----------
if (-not (Test-Path "bin\ffmpeg.exe")) {
    Write-Host "==> Downloading FFmpeg (BtbN latest static build)..."
    $ffmpegZip = "ffmpeg-master-latest-win64-gpl.zip"
    Invoke-WebRequest -Uri "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/$ffmpegZip" `
                      -OutFile $ffmpegZip -UseBasicParsing
    Expand-Archive -Path $ffmpegZip -DestinationPath "ffmpeg-tmp" -Force
    New-Item -ItemType Directory -Force -Path "bin" | Out-Null
    Get-ChildItem "ffmpeg-tmp" -Directory | ForEach-Object {
        Copy-Item "$($_.FullName)\bin\ffmpeg.exe"  "bin\" -Force
        Copy-Item "$($_.FullName)\bin\ffprobe.exe" "bin\" -Force
    }
    Remove-Item "ffmpeg-tmp" -Recurse -Force
    Remove-Item $ffmpegZip -Force
    Write-Host "==> FFmpeg ready: bin\ffmpeg.exe"
} else {
    Write-Host "==> Using existing FFmpeg: bin\ffmpeg.exe"
}

# ---------- 3. Python dependencies ----------
Write-Host "==> Installing Python dependencies..."
python -m pip install --upgrade pip | Out-Null
# Pin PyInstaller to 6.x: 7.x changed SPEC injection semantics.
python -m pip install --upgrade -r requirements.txt "pyinstaller>=6.3,<7" | Out-Null

# ---------- 4. PyInstaller (windowed, no console) ----------
Write-Host "==> Running PyInstaller..."
pyinstaller --noconfirm --clean "packaging\MediaForge.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

# ---------- 5. Optional code signing ----------
$signtool = Get-ChildItem -Path "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" `
                         -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $signtool) {
    $signtool = Get-ChildItem -Path "${env:ProgramFiles}\Windows Kits\10\bin\*\x64\signtool.exe" `
                              -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Sign-IfPossible($file) {
    if (-not $script:signtool) { return $false }
    if (-not (Test-Path $file)) { return $false }
    if (-not $PfxPath -or -not (Test-Path $PfxPath)) {
        Write-Host "==> Skipping sign (no cert): $file"
        return $false
    }
    Write-Host "==> Signing: $file"
    & $script:signtool sign /f "$PfxPath" /p "$PfxPassword" `
        /fd SHA256 /tr "$TimestampUrl" /td SHA256 "$file"
    if ($LASTEXITCODE -ne 0) { throw "signtool failed for $file" }
    return $true
}

if ($signtool) {
    Sign-IfPossible "dist\MediaForge\MediaForge.exe"
} else {
    Write-Host "==> WARNING: signtool.exe not found (Windows SDK not installed?) - skipping signing"
}

# ---------- 6. Inno Setup (Chinese installer) ----------
Write-Host "==> Running Inno Setup..."
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "$env:ProgramFiles\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 not found. Install from: https://jrsoftware.org/isinfo.php" }
& $iscc "/DMyAppVersion=$Version" "packaging\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }

# Sign installer too (dual-sign main exe + installer)
if ($signtool) {
    Get-ChildItem "dist_installer\*.exe" | ForEach-Object {
        Sign-IfPossible $_.FullName
    }
}

Write-Host ""
Write-Host "==> Build complete! Installer is in dist_installer\"
Get-ChildItem "dist_installer\*.exe" | ForEach-Object { Write-Host "    $($_.FullName)" }