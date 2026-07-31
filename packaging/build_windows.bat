@echo off
REM 在本地 Windows 上一键构建安装程序
REM 需要：Python 3.10+、Inno Setup 6（iscc 在 PATH 中或默认安装路径）
setlocal
cd /d "%~dp0\.."

echo [1/4] 安装依赖...
python -m pip install --upgrade pip || goto :err
python -m pip install -r requirements.txt pyinstaller || goto :err

echo [2/4] 运行测试...
python -m pytest tests -q || echo 警告：部分测试未通过，继续构建

echo [3/4] PyInstaller 打包...
python -m PyInstaller packaging\MediaForge.spec --noconfirm --clean || goto :err

echo [4/4] 编译安装程序...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=iscc"
"%ISCC%" packaging\installer.iss || goto :err

echo.
echo 构建完成！安装程序位于 dist_installer\ 目录。
exit /b 0

:err
echo.
echo 构建失败，请查看上方错误信息。
exit /b 1
