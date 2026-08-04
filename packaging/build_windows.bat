@echo off
rem ============================================================
rem  MediaForge Windows 一键打包脚本
rem  前提：已安装 Python 3.10+、Inno Setup 6
rem  产物：dist\MediaForge\ 目录程序 + dist_installer\ 安装包
rem ============================================================
setlocal
cd /d "%~dp0.."

echo [1/4] 创建虚拟环境...
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [2/4] 安装依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

echo [3/4] PyInstaller 打包（无控制台窗口的 GUI 程序）...
pyinstaller --noconfirm --clean packaging\MediaForge.spec
if errorlevel 1 goto :fail

echo [4/4] Inno Setup 生成中文安装包...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo 未找到 Inno Setup 6，请先安装：https://jrsoftware.org/isinfo.php
    goto :fail
)
"%ISCC%" packaging\installer.iss
if errorlevel 1 goto :fail

echo.
echo 打包完成！安装包位于 dist_installer\ 目录。
pause
exit /b 0

:fail
echo.
echo 打包失败，请检查上方错误信息。
pause
exit /b 1
