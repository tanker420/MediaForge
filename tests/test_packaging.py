"""打包相关文件的完整性测试。

覆盖 C9 修复（icon.ico 用于 Windows 打包 / icon.png 用于 GUI 窗口图标），
以及安装脚本、构建脚本、CI 工作流之间的路径一致性。
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    p = ROOT / rel
    assert p.is_file(), f"缺少文件：{rel}"
    return p.read_text("utf-8", errors="replace")


# ---------------- 资源 ----------------
def test_icon_files_exist():
    assert (ROOT / "app" / "resources" / "icon.ico").is_file()
    assert (ROOT / "app" / "resources" / "icon.png").is_file()


def test_icon_usage_no_confusion():
    """C9 修复：GUI 窗口用 PNG，Windows 打包/安装程序用 ICO，各司其职。"""
    ui_src = _read("app/ui/main_window.py")
    assert "icon.png" in ui_src
    assert "icon.ico" not in ui_src
    spec = _read("packaging/MediaForge.spec")
    assert "icon.ico" in spec
    iss = _read("packaging/installer.iss")
    assert "icon.ico" in iss


# ---------------- PyInstaller ----------------
def test_spec_basic():
    spec = _read("packaging/MediaForge.spec")
    assert 'name="MediaForge"' in spec
    assert "console=False" in spec          # 无命令行窗口
    assert "main.py" in spec
    assert "version_info.txt" in spec
    assert "resources" in spec


def test_version_info_chinese():
    vi = _read("packaging/version_info.txt")
    assert "080404B0" in vi                # zh-CN / UTF-16
    assert "2052" in vi
    assert "全能媒体格式转换器" in vi


# ---------------- Inno Setup ----------------
def test_installer_chinese_localization():
    iss = _read("packaging/installer.iss")
    assert "ChineseSimplified.isl" in iss
    # 简体中文必须是第一个语言（默认语言）
    lang_block = iss.split("[Languages]")[1].split("[")[0]
    assert lang_block.strip().splitlines()[0].startswith("Name: \"chinesesimplified\"")
    assert "全能格式转换器" in iss
    assert "dist\\MediaForge" in iss       # 引用 PyInstaller 输出
    assert "dist_installer" in iss         # 安装包输出目录


def test_installer_app_mutex():
    """更新器依赖 Inno Setup 的 /CLOSEAPPLICATIONS 关闭正在运行的 MediaForge，
    需要 [Setup] 段声明 AppMutex。"""
    iss = _read("packaging/installer.iss")
    assert "AppMutex=" in iss, "[Setup] 缺少 AppMutex，自更新无法静默关闭运行中的 MediaForge"


def test_installer_license_and_icon_paths():
    iss = _read("packaging/installer.iss")
    assert "..\\LICENSE.zh-CN.txt" in iss, "安装程序许可页应展示中文许可文件"
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "LICENSE.zh-CN.txt").is_file()


# ---------------- 构建脚本 ----------------
def test_bat_references_spec_and_iss():
    bat = _read("packaging/build_windows.bat")
    assert "MediaForge.spec" in bat
    assert "installer.iss" in bat


def test_ps1_references_spec_and_iss():
    ps1 = _read("packaging/ci/build.ps1")
    assert "MediaForge.spec" in ps1
    assert "installer.iss" in ps1
    assert "ffmpeg" in ps1.lower()


def test_ps1_ascii_only():
    """build.ps1 必须在 PowerShell 5.1 下无 BOM 也能正确解析，
    中文字符会破坏编码（PowerShell 5.1 把无 BOM UTF-8 当 GBK 解码）。"""
    raw = (ROOT / "packaging" / "ci" / "build.ps1").read_bytes()
    raw.decode("ascii", errors="strict")  # 任何非 ASCII 都抛错


def test_ps1_supports_code_signing():
    """代码签名是可选的（无证书时跳过），但 build.ps1 必须支持。"""
    text = _read("packaging/ci/build.ps1")
    assert "PfxPath" in text and "signtool" in text.lower()
    # 还需在工作流里把证书 secret 传进来
    wf = _read(".github/workflows/build-windows.yml")
    assert "CODE_SIGNING_PFX_BASE64" in wf, "CI 没把签名证书传进 build.ps1"


def test_workflow_references_build_script():
    wf = _read(".github/workflows/build-windows.yml")
    assert "build.ps1" in wf
    assert "windows-latest" in wf


def test_gui_has_no_command_preview():
    """A2/B6 修复：GUI 不再展示命令行，也不再暴露专家参数。"""
    ui_src = _read("app/ui/main_window.py")
    assert "preview_command" not in ui_src
    assert "extra_args" not in ui_src


def test_build_doc_exists():
    assert (ROOT / "如何生成安装程序.md").is_file()
