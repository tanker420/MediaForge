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
WF = os.path.join(ROOT, "packaging", "ci", "build-windows.yml")


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
               "installer.iss", "dist_installer"):
        assert kw in src, f"缺少关键步骤：{kw}"


def test_workflow_is_valid_yaml():
    yaml = pytest.importorskip("yaml")
    d = yaml.safe_load(open(WF, encoding="utf-8"))
    steps = d["jobs"]["build"]["steps"]
    assert len(steps) >= 4
    assert any("build.ps1" in str(s.get("run", "")) for s in steps)


def test_workflow_references_existing_script():
    """工作流里引用的脚本必须真实存在。"""
    src = open(WF, encoding="utf-8").read()
    for m in re.finditer(r"-File\s+([\w\\/.]+)", src):
        rel = m.group(1).replace("\\", os.sep).replace("/", os.sep)
        assert os.path.isfile(os.path.join(ROOT, rel)), f"引用了不存在的脚本 {rel}"
