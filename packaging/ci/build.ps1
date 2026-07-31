# MediaForge Windows build script (ASCII only, safe for Windows PowerShell 5.1)
# Usage: powershell -ExecutionPolicy Bypass -File packaging\ci\build.ps1
$ErrorActionPreference = "Stop"

Write-Host "==> [1/5] Installing Python dependencies"
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

Write-Host "==> [2/5] Downloading and bundling FFmpeg"
New-Item -ItemType Directory -Force -Path bin | Out-Null
$urls = @(
  "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
  "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip",
  "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
)
$ok = $false
foreach ($url in $urls) {
  try {
    Write-Host "    trying: $url"
    Invoke-WebRequest -Uri $url -OutFile ffmpeg.zip -TimeoutSec 300
    $ok = $true
    break
  } catch {
    Write-Warning "    source failed: $($_.Exception.Message)"
  }
}
if (-not $ok) { throw "All FFmpeg download sources failed" }

Expand-Archive ffmpeg.zip -DestinationPath ffmpeg_tmp -Force
$ff = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffmpeg.exe  | Select-Object -First 1
$fp = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffprobe.exe | Select-Object -First 1
if (-not $ff) { throw "ffmpeg.exe not found in archive" }
Copy-Item $ff.FullName bin\ -Force
if ($fp) { Copy-Item $fp.FullName bin\ -Force }
Remove-Item ffmpeg.zip, ffmpeg_tmp -Recurse -Force
Get-ChildItem bin

Write-Host "==> [3/5] Running PyInstaller"
# Sanity check: make sure we are building the fixed spec, not a stale checkout.
$specText = Get-Content packaging\MediaForge.spec -Raw
if ($specText -match 'version\s*=\s*"packaging/version_info.txt"') {
  throw "Stale spec detected (relative version path). The checkout is not up to date - start a NEW workflow run instead of re-running the old one."
}
Write-Host "    spec check passed"

pyinstaller packaging/MediaForge.spec --noconfirm --clean
$exe = "dist\MediaForge\MediaForge.exe"
if (-not (Test-Path $exe)) { throw "exe was not produced" }

Write-Host "==> [4/5] Smoke test"
& $exe doctor
if ($LASTEXITCODE -ne 0) { throw "doctor command failed with exit code $LASTEXITCODE" }

Write-Host "==> [5/5] Building installer with Inno Setup"
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
  Write-Host "    Inno Setup not found, installing..."
  choco install innosetup -y --no-progress
}
if (-not (Test-Path $iscc)) {
  $found = Get-ChildItem "C:\Program Files*" -Recurse -Filter ISCC.exe -ErrorAction SilentlyContinue |
           Select-Object -First 1
  if (-not $found) { throw "ISCC.exe (Inno Setup compiler) not found" }
  $iscc = $found.FullName
}
& $iscc packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }

Get-ChildItem dist_installer\*.exe | ForEach-Object {
  $h = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
  "$h  $($_.Name)" | Out-File -Append -Encoding utf8 dist_installer\SHA256SUMS.txt
}

Write-Host ""
Write-Host "Build finished. Installer is in dist_installer\"
Get-ChildItem dist_installer
