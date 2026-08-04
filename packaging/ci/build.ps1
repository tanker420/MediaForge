# ============================================================
#  MediaForge Windows build script (PyInstaller + Inno Setup)
#  Used by GitHub Actions and local PowerShell:
#    powershell -ExecutionPolicy Bypass -File packaging\ci\build.ps1
#  NOTE: This file is intentionally ASCII-only (no Chinese chars)
#  so it parses correctly under Windows PowerShell 5.1 regardless
#  of file encoding (no BOM required).
# ============================================================
param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # repo root
Set-Location $root

$Version = $Version.TrimStart('v')

Write-Host "==> MediaForge build started, version: $Version"

# ---------- 1. FFmpeg (BtbN static build, no install needed) ----------
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

# ---------- 2. Python dependencies ----------
Write-Host "==> Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

# ---------- 3. PyInstaller (windowed, no console) ----------
Write-Host "==> Running PyInstaller..."
pyinstaller --noconfirm --clean "packaging\MediaForge.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

# ---------- 4. Inno Setup (Chinese installer) ----------
Write-Host "==> Running Inno Setup..."
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "$env:ProgramFiles\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 not found. Install from: https://jrsoftware.org/isinfo.php" }
& $iscc "/DMyAppVersion=$Version" "packaging\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }

Write-Host ""
Write-Host "==> Build complete! Installer is in dist_installer\"
Get-ChildItem "dist_installer\*.exe" | ForEach-Object { Write-Host "    $($_.FullName)" }
