# MediaForge Windows build script (ASCII only, safe for Windows PowerShell 5.1)
# Usage: powershell -ExecutionPolicy Bypass -File packaging\ci\build.ps1
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# UTF-8 helpers.
# CRITICAL: the Python sources and version_info.txt contain Chinese text and are
# saved as UTF-8.  In Windows PowerShell 5.1, Get-Content / Set-Content default
# to the system ANSI code page (GBK / cp1252), NOT UTF-8.  If we read those files
# without an explicit encoding, every Chinese character is silently mangled into
# mojibake, which then gets baked into the built exe -> the installed app's UI
# shows garbled text. So always read/write these files with explicit UTF-8.
function Read-TextUtf8([string]$Path) {
    return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}
# Write UTF-8 WITHOUT a BOM so we don't modify the repo's source files any more
# than necessary (the version-stamping edits are the only intended change).
function Write-TextUtf8NoBom([string]$Path, [string]$Content) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

Write-Host "==> [1/6] Installing Python dependencies"
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

Write-Host "==> [2/6] Downloading and bundling FFmpeg"
New-Item -ItemType Directory -Force -Path bin | Out-Null
# Use FULL builds: the "essentials" variant lacks libsvtav1 / libaom-av1 / libvpx etc.
$urls = @(
  "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z",
  "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-full_build.7z",
  "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
  "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)
$archive = $null
foreach ($url in $urls) {
  $ext = if ($url -match '\.7z$') { "7z" } else { "zip" }
  $dest = "ffmpeg_dl.$ext"
  try {
    Write-Host "    trying: $url"
    Invoke-WebRequest -Uri $url -OutFile $dest -TimeoutSec 600
    $archive = $dest
    break
  } catch {
    Write-Warning "    source failed: $($_.Exception.Message)"
    if (Test-Path $dest) { Remove-Item $dest -Force }
  }
}
if (-not $archive) { throw "All FFmpeg download sources failed" }

Write-Host "    extracting $archive"
if ($archive -match '\.7z$') {
  # 7-Zip is preinstalled on GitHub windows runners; fall back to choco if missing.
  $sevenzip = "$env:ProgramFiles\7-Zip\7z.exe"
  if (-not (Test-Path $sevenzip)) { $sevenzip = (Get-Command 7z -ErrorAction SilentlyContinue).Source }
  if (-not $sevenzip) {
    choco install 7zip -y --no-progress
    $sevenzip = "$env:ProgramFiles\7-Zip\7z.exe"
  }
  if (-not (Test-Path $sevenzip)) { throw "7z.exe not found, cannot extract .7z archive" }
  & $sevenzip x $archive "-offmpeg_tmp" -y | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "7z extraction failed" }
} else {
  Expand-Archive $archive -DestinationPath ffmpeg_tmp -Force
}
$ff = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffmpeg.exe  | Select-Object -First 1
$fp = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffprobe.exe | Select-Object -First 1
if (-not $ff) { throw "ffmpeg.exe not found in archive" }
Copy-Item $ff.FullName bin\ -Force
if ($fp) { Copy-Item $fp.FullName bin\ -Force }
Remove-Item $archive, ffmpeg_tmp -Recurse -Force
Get-ChildItem bin

# Verify the encoders the UI offers are actually present in this FFmpeg build.
Write-Host "    verifying bundled encoders"
$encoders = & bin\ffmpeg.exe -hide_banner -encoders 2>&1 | Out-String
$want = @("libx264","libx265","libsvtav1","libvpx-vp9","libmp3lame","libopus","libvorbis","aac","flac")
$missing = @()
foreach ($e in $want) {
  if ($encoders -notmatch [regex]::Escape($e)) { $missing += $e }
}
if ($missing.Count -gt 0) {
  Write-Warning "    bundled FFmpeg is missing: $($missing -join ', ')"
} else {
  Write-Host "    all key encoders present"
}

# Version comes from APP_VERSION (set by CI from git tag); local builds fall back.
$version = if ($env:APP_VERSION) { $env:APP_VERSION } else { "0.0.0-dev" }
Write-Host "==> [3/6] Stamping version: $version"

# Keep in-app VERSION strings in sync with the installer (best-effort).
foreach ($py in @("app\cli.py", "app\ui\main_window.py")) {
  if (Test-Path $py) {
    $fullPath = (Resolve-Path $py).Path
    $txt = Read-TextUtf8 $fullPath
    $txt = $txt -replace 'VERSION\s*=\s*"[^"]*"', "VERSION = `"$version`""
    Write-TextUtf8NoBom $fullPath $txt
  }
}

# Update Windows PE version resource (numeric tuple + display strings).
$viPath = "packaging\version_info.txt"
if (Test-Path $viPath) {
  $nums = @()
  foreach ($p in (($version -split '[-+]')[0] -split '\.')) {
    $n = 0
    if ($p -match '^\d+$') { $n = [int]$p }
    $nums += $n
  }
  while ($nums.Count -lt 4) { $nums += 0 }
  $tuple = ($nums[0..3] -join ", ")
  $disp = "$($nums[0]).$($nums[1]).$($nums[2]).$($nums[3])"
  $viFull = (Resolve-Path $viPath).Path
  $vi = Read-TextUtf8 $viFull
  $vi = $vi -replace 'filevers=\([^)]+\)', "filevers=($tuple)"
  $vi = $vi -replace 'prodvers=\([^)]+\)', "prodvers=($tuple)"
  $vi = $vi -replace "StringStruct\('FileVersion', '[^']*'\)", "StringStruct('FileVersion', '$disp')"
  $vi = $vi -replace "StringStruct\('ProductVersion', '[^']*'\)", "StringStruct('ProductVersion', '$disp')"
  Write-TextUtf8NoBom $viFull $vi
}

Write-Host "==> [4/6] Running PyInstaller"
# Sanity check: make sure we are building the fixed spec, not a stale checkout.
$specText = Get-Content packaging\MediaForge.spec -Raw
if ($specText -match 'version\s*=\s*"packaging/version_info.txt"') {
  throw "Stale spec detected (relative version path). The checkout is not up to date - start a NEW workflow run instead of re-running the old one."
}
Write-Host "    spec check passed"

pyinstaller packaging/MediaForge.spec --noconfirm --clean
$exe = "dist\MediaForge\MediaForge.exe"
if (-not (Test-Path $exe)) { throw "exe was not produced" }

Write-Host "==> [5/6] Smoke test"
& $exe doctor
if ($LASTEXITCODE -ne 0) { throw "doctor command failed with exit code $LASTEXITCODE" }

Write-Host "==> [6/6] Building installer with Inno Setup"
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
Write-Host "    installer version: $version"
& $iscc "/DMyAppVersion=$version" packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }

Get-ChildItem dist_installer\*.exe | ForEach-Object {
  $h = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
  "$h  $($_.Name)" | Out-File -Append -Encoding utf8 dist_installer\SHA256SUMS.txt
}

Write-Host ""
Write-Host "Build finished. Installer is in dist_installer\"
Get-ChildItem dist_installer
