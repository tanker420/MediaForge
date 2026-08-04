# ============================================================
#  MediaForge Windows 构建脚本（PyInstaller + Inno Setup）
#  供 GitHub Actions 调用，也可在本地 PowerShell 手动执行：
#     powershell -ExecutionPolicy Bypass -File packaging\ci\build.ps1
# ============================================================
param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # 仓库根目录
Set-Location $root

$Version = $Version.TrimStart('v')

Write-Host "==> MediaForge 构建开始，版本：$Version"

# ---------- 1. FFmpeg（BtbN 静态构建，无需安装） ----------
if (-not (Test-Path "bin\ffmpeg.exe")) {
    Write-Host "==> 下载 FFmpeg（BtbN 最新静态构建）..."
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
    Write-Host "==> FFmpeg 就绪：bin\ffmpeg.exe"
} else {
    Write-Host "==> 使用已有 FFmpeg：bin\ffmpeg.exe"
}

# ---------- 2. Python 依赖 ----------
Write-Host "==> 安装 Python 依赖..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

# ---------- 3. PyInstaller 打包（无控制台窗口） ----------
Write-Host "==> PyInstaller 打包..."
pyinstaller --noconfirm --clean "packaging\MediaForge.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }

# ---------- 4. Inno Setup 生成中文安装包 ----------
Write-Host "==> Inno Setup 生成安装包..."
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "$env:ProgramFiles\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { throw "未找到 Inno Setup 6，请先安装：https://jrsoftware.org/isinfo.php" }
& $iscc "/DMyAppVersion=$Version" "packaging\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 打包失败" }

Write-Host ""
Write-Host "==> 构建完成！安装包位于 dist_installer\ 目录"
Get-ChildItem "dist_installer\*.exe" | ForEach-Object { Write-Host "    $($_.FullName)" }
