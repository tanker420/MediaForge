"""打包脚本的健全性测试。

回归背景：build.ps1 曾包含 UTF-8 中文注释，Windows PowerShell 5.1
按 ANSI 读取导致乱码与语法错误，CI 直接失败。
"""
from __future__ import annotations

import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PS1 = os.path.join(ROOT, "packaging", "ci", "build.ps1")
# Real workflow used by GitHub Actions (not the packaging/ci reference template).
WF = os.path.join(ROOT, ".github", "workflows", "build-windows.yml")
ISS = os.path.join(ROOT, "packaging", "installer.iss")


def test_build_script_exists():
    assert os.path.isfile(PS1)


def test_build_script_is_pure_ascii():
    """PowerShell 5.1 对无 BOM 的 UTF-8 中文会解析失败，故限定纯 ASCII。"""
    raw = open(PS1, "rb").read()
    bad = [(i, b) for i, b in enumerate(raw) if b > 127]
    assert not bad, f"build.ps1 含非 ASCII 字节，位置 {bad[:5]}"


def test_build_script_brackets_balanced():
    src = open(PS1, encoding="utf-8").read()
    depth = {"{": 0, "(": 0, "[": 0}
    pairs = {"}": "{", ")": "(", "]": "["}
    i, n, quote = 0, len(src), None
    while i < n:
        c = src[i]
        if quote:
            if c == quote:
                quote = None
            elif c == "`":
                i += 1
        elif c in "\"'":
            quote = c
        elif c == "#":
            while i < n and src[i] != "\n":
                i += 1
        elif c in depth:
            depth[c] += 1
        elif c in pairs:
            depth[pairs[c]] -= 1
            assert depth[pairs[c]] >= 0, f"多余的 {c}"
        i += 1
    assert quote is None, "存在未闭合的引号"
    for k, v in depth.items():
        assert v == 0, f"{k} 未闭合"


def test_build_script_has_required_steps():
    src = open(PS1, encoding="utf-8").read()
    for kw in ("requirements.txt", "MediaForge.spec",
               "installer.iss", "dist_installer",
               "APP_VERSION", "/DMyAppVersion="):
        assert kw in src, f"缺少关键步骤：{kw}"


def test_installer_iss_version_is_overridable():
    """Inno Setup version must be overridable via /DMyAppVersion=..."""
    src = open(ISS, encoding="utf-8").read()
    assert "#ifndef MyAppVersion" in src
    assert '#define MyAppVersion "0.0.0-dev"' in src


def test_workflow_is_valid_yaml():
    yaml = pytest.importorskip("yaml")
    d = yaml.safe_load(open(WF, encoding="utf-8"))
    steps = d["jobs"]["build"]["steps"]
    assert len(steps) >= 4
    assert any("build.ps1" in str(s.get("run", "")) for s in steps)


def test_workflow_tag_driven_release():
    """Tag push builds + releases; manual dispatch only builds."""
    yaml = pytest.importorskip("yaml")
    d = yaml.safe_load(open(WF, encoding="utf-8"))
    on = d["on"] if "on" in d else d[True]  # PyYAML may parse 'on' as True
    assert "workflow_dispatch" in on
    assert "push" in on
    assert "v*" in on["push"].get("tags", [])
    assert d.get("permissions", {}).get("contents") == "write"
    src = open(WF, encoding="utf-8").read()
    assert "APP_VERSION" in src
    assert "softprops/action-gh-release" in src
    assert "github.ref_type == 'tag'" in src or 'github.ref_type == "tag"' in src


def test_workflow_references_existing_script():
    """工作流里引用的脚本必须真实存在。"""
    src = open(WF, encoding="utf-8").read()
    for m in re.finditer(r"-File\s+([\w\\/.]+)", src):
        rel = m.group(1).replace("\\", os.sep).replace("/", os.sep)
        assert os.path.isfile(os.path.join(ROOT, rel)), f"引用了不存在的脚本 {rel}"


# ---------------------------------------------------------------------------
# PyInstaller spec 路径测试
#
# 回归背景：spec 中 version="packaging/version_info.txt" 用了相对路径，
# PyInstaller 以 spec 所在目录为基准解析，拼成 packaging/packaging/...
# 导致 FileNotFoundError，构建在最后一步失败。
# ---------------------------------------------------------------------------
SPEC = os.path.join(ROOT, "packaging", "MediaForge.spec")


def _eval_spec(simulate_windows: bool = False) -> dict:
    """执行 spec 并捕获传给各构建器的参数。"""
    src = open(SPEC, encoding="utf-8").read()
    if simulate_windows:
        src = src.replace('os.name == "nt"', "True")

    captured: dict = {}

    class Rec:
        def __init__(self, name):
            self.n = name
            self.pure = []
            self.scripts = []
            self.binaries = []
            self.datas = []

        def __call__(self, *a, **k):
            captured[self.n] = (a, k)
            return self

    ns = {n: Rec(n) for n in ("Analysis", "PYZ", "EXE", "COLLECT")}
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        exec(compile(src, SPEC, "exec"), ns)
    finally:
        os.chdir(cwd)
    return captured


def test_spec_is_executable():
    assert _eval_spec(), "spec 未能正常执行"


def test_spec_entry_script_is_absolute_and_exists():
    script = _eval_spec()["Analysis"][0][0][0]
    assert os.path.isabs(script), "入口脚本应使用绝对路径"
    assert os.path.isfile(script)


def test_spec_icon_path_resolves():
    icon = _eval_spec()["EXE"][1]["icon"]
    if icon:
        assert os.path.isabs(icon)
        assert os.path.isfile(icon)


def test_spec_version_file_absolute_on_windows():
    """version 必须是绝对路径，否则会被拼成 packaging/packaging/..."""
    version = _eval_spec(simulate_windows=True)["EXE"][1]["version"]
    assert version, "Windows 下应设置版本信息文件"
    assert os.path.isabs(version), (
        "version 必须用绝对路径：PyInstaller 以 spec 所在目录为基准解析相对路径"
    )
    assert os.path.isfile(version), f"版本文件不存在：{version}"


def test_spec_paths_resolve_relative_to_specdir():
    """模拟 PyInstaller 的解析规则，确保没有路径会被重复拼接。"""
    cap = _eval_spec(simulate_windows=True)
    specdir = os.path.dirname(SPEC)
    values = [
        cap["Analysis"][0][0][0],
        cap["EXE"][1].get("icon"),
        cap["EXE"][1].get("version"),
    ]
    for val in values:
        if not val:
            continue
        resolved = val if os.path.isabs(val) else os.path.join(specdir, val)
        assert os.path.isfile(resolved), f"路径解析后不存在：{resolved}"
