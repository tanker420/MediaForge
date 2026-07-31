# MediaForge Windows 打包脚本（供 GitHub Actions 与本地共用）
# 用法： powershell -ExecutionPolicy Bypass -File packaging\ci\build.ps1
$ErrorActionPreference = "Stop"

Write-Host "==> [1/5] 安装 Python 依赖"
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

Write-Host "==> [2/5] 下载并内置 FFmpeg"
New-Item -ItemType Directory -Force -Path bin | Out-Null
$urls = @(
  "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
  "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip",
  "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
)
$ok = $false
foreach ($url in $urls) {
  try {
    Write-Host "    尝试: $url"
    Invoke-WebRequest -Uri $url -OutFile ffmpeg.zip -TimeoutSec 300
    $ok = $true; break
  } catch { Write-Warning "    该源不可用：$($_.Exception.Message)" }
}
if (-not $ok) { throw "所有 FFmpeg 下载源均失败" }
Expand-Archive ffmpeg.zip -DestinationPath ffmpeg_tmp -Force
$ff = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffmpeg.exe  | Select-Object -First 1
$fp = Get-ChildItem ffmpeg_tmp -Recurse -Filter ffprobe.exe | Select-Object -First 1
if (-not $ff) { throw "压缩包中未找到 ffmpeg.exe" }
Copy-Item $ff.FullName bin\ -Force
if ($fp) { Copy-Item $fp.FullName bin\ -Force }
Remove-Item ffmpeg.zip, ffmpeg_tmp -Recurse -Force

Write-Host "==> [3/5] PyInstaller 打包"
pyinstaller packaging/MediaForge.spec --noconfirm --clean
$exe = "dist\MediaForge\MediaForge.exe"
if (-not (Test-Path $exe)) { throw "未生成 exe" }

Write-Host "==> [4/5] 冒烟测试"
& $exe doctor
if ($LASTEXITCODE -ne 0) { throw "doctor 命令失败（退出码 $LASTEXITCODE）" }

Write-Host "==> [5/5] 编译安装程序"
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
  Write-Host "    未检测到 Inno Setup，正在安装…"
  choco install innosetup -y --no-progress
}
if (-not (Test-Path $iscc)) {
  $found = Get-ChildItem "C:\Program Files*" -Recurse -Filter ISCC.exe -ErrorAction SilentlyContinue |
           Select-Object -First 1
  if (-not $found) { throw "找不到 ISCC.exe" }
  $iscc = $found.FullName
}
& $iscc packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败" }

Get-ChildItem dist_installer\*.exe | ForEach-Object {
  $h = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
  "$h  $($_.Name)" | Out-File -Append -Encoding utf8 dist_installer\SHA256SUMS.txt
}
Write-Host ""
Write-Host "构建完成！安装程序位于 dist_installer\ 目录"
Get-ChildItem dist_installer
