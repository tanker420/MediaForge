"""updater 模块的单元测试。

不联网：只测纯函数（版本解析、Markdown 剥离）。
联网检查在 test_updater_integration.py 里通过环境变量可选触发。
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import updater  # noqa: E402


def test_parse_version_basic():
    assert updater.parse_version("v1.2.3") == (1, 2, 3)
    assert updater.parse_version("1.0.0") == (1, 0, 0)
    assert updater.parse_version("v10.20.30") == (10, 20, 30)


def test_parse_version_prerelease():
    # 预发布标签只取主版本号段
    assert updater.parse_version("v1.2.3-rc1") == (1, 2, 3)
    assert updater.parse_version("1.2.3-beta2") == (1, 2, 3)


def test_parse_version_invalid():
    # 解析失败返回 (-1,)，这样任意新版本都不会被误判为「比当前旧」
    assert updater.parse_version("") == (-1,)
    assert updater.parse_version("abc") == (-1,)
    assert updater.parse_version("v1.x") == (-1,)


def test_strip_markdown():
    text = "# Title\n\n**bold** and *italic*\n- item 1\n- item 2\n\n`code`"
    out = updater._strip_markdown(text)
    assert "**" not in out
    assert "*" not in out
    assert "Title" in out and "bold" in out and "italic" in out
    assert "• item 1" in out
    assert "code" in out


def test_install_asset_pattern():
    """文件名匹配规则覆盖空格、大小写。"""
    asset = updater._INSTALLER_RE
    assert asset.search("MediaForge-1.0.1-Setup.exe")
    assert asset.search("mediaforge-1.0.1-setup.EXE")
    assert asset.search("MediaForge-1.0.1-rc1-Setup.exe")
    assert not asset.search("MediaForge-1.0.1.zip")
    assert not asset.search("Source code (zip)")