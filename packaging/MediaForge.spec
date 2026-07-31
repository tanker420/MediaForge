# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

用法（在 Windows 上）：
    pyinstaller packaging/MediaForge.spec --noconfirm
"""
import os
from pathlib import Path

ROOT = Path(os.getcwd())
RES = ROOT / "app" / "resources"
ICON = RES / "icon.ico"
VERSION_FILE = ROOT / "packaging" / "version_info.txt"

datas = [(str(RES), "app/resources")]

# 若存在 bin 目录（内含 ffmpeg.exe / ffprobe.exe），一并打包进去
binaries = []
bin_dir = ROOT / "bin"
if bin_dir.is_dir():
    for f in bin_dir.iterdir():
        if f.is_file():
            binaries.append((str(f), "bin"))

hiddenimports = [
    "PIL._tkinter_finder",
    "pillow_heif",
]

excludes = [
    "tkinter", "matplotlib", "numpy", "scipy", "pandas", "pytest",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts", "PySide6.QtMultimedia",
    "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtOpenGL", "PySide6.QtPositioning", "PySide6.QtBluetooth",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MediaForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI 程序，不弹黑框
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.exists() else None,
    # 必须用绝对路径：PyInstaller 解析此项时以 spec 所在目录为基准，
    # 写相对路径会被拼成 packaging/packaging/version_info.txt
    version=str(VERSION_FILE) if (os.name == "nt" and VERSION_FILE.exists()) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MediaForge",
)
