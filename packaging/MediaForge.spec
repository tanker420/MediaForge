# -*- mode: python ; coding: utf-8 -*-
"""MediaForge PyInstaller 打包配置。

生成「单目录」GUI 程序（无控制台窗口），随后由 Inno Setup 打成安装包。
用法： pyinstaller --noconfirm --clean packaging\\MediaForge.spec
"""
import os

# PyInstaller 在 exec 执行 .spec 时，命名空间里没有 __file__（6.x 的限制），
# 但会注入 SPEC 变量（spec 文件路径）。按优先级取项目根目录：
#   PyInstaller 运行（SPEC 注入） -> 直接运行 spec（__file__ 存在） -> 当前目录
if "SPEC" in globals():
    ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), ".."))
elif "__file__" in globals():
    ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
else:
    ROOT = os.getcwd()


a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # 图标资源随程序一起分发（运行期 QIcon 会从相对路径读取）
        (os.path.join(ROOT, "app", "resources"), os.path.join("app", "resources")),
    ],
    hiddenimports=[
        "pillow_heif",          # AVIF / HEIC 图片支持（可选依赖，缺失时自动降级）
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx=True,
    console=False,              # 关键：无命令行窗口，纯 GUI 程序
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "app", "resources", "icon.ico"),
    version=os.path.join(ROOT, "packaging", "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MediaForge",
)
