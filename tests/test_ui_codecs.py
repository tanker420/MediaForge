"""界面编码器可用性测试。

回归背景：打包的 FFmpeg 精简版不含 libsvtav1，但界面仍把它列为可选
且默认选中，用户点转换后只得到一句英文 "Unknown encoder"。
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.core import formats as F  # noqa: E402

LIMITED = frozenset({"libx264", "libx265", "libvpx-vp9", "mpeg4",
                     "aac", "libmp3lame", "libopus", "flac", "copy", "gif"})


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def win(qapp, monkeypatch):
    import app.core.ffprobe as fp
    import app.ui.main_window as mw
    monkeypatch.setattr(fp, "available_encoders", lambda: LIMITED)
    monkeypatch.setattr(mw, "available_encoders", lambda: LIMITED)
    monkeypatch.setattr(mw, "ffmpeg_path", lambda: "/fake/ffmpeg")
    try:
        return mw.MainWindow()
    except Exception as exc:  # 缺少图形依赖时跳过
        pytest.skip(f"无法创建窗口：{exc}")


def _codec_items(cb):
    return [(cb.itemData(i), cb.model().item(i).isEnabled())
            for i in range(cb.count())]


def test_unavailable_encoder_is_disabled(win):
    win.cb_kind.setCurrentIndex(win.cb_kind.findData(F.VIDEO))
    win.cb_format.setCurrentIndex(win.cb_format.findData("mkv"))
    for enc, enabled in _codec_items(win.cb_vcodec):
        if enc in ("copy", "none"):
            continue
        assert enabled == (enc in LIMITED), f"{enc} 的可用状态不正确"


def test_default_selection_is_usable(win):
    """默认选中的编码器必须是当前 FFmpeg 真正支持的。"""
    win.cb_kind.setCurrentIndex(win.cb_kind.findData(F.VIDEO))
    for ext in ("mkv", "mp4", "webm", "mov"):
        idx = win.cb_format.findData(ext)
        if idx < 0:
            continue
        win.cb_format.setCurrentIndex(idx)
        sel = win.cb_vcodec.currentData()
        assert sel in LIMITED or sel in ("copy", "none"), \
            f".{ext} 默认选中了不可用的编码器 {sel}"


def test_start_blocks_unavailable_encoder(win, monkeypatch, tmp_path):
    """强行选中不可用编码器时，应弹出提示且不启动转换。"""
    import app.ui.main_window as mw

    shown = {}

    class FakeMB:
        @staticmethod
        def critical(parent, title, text):
            shown["title"] = title

        @staticmethod
        def warning(*a, **k):
            pass

        @staticmethod
        def information(*a, **k):
            pass

    monkeypatch.setattr(mw, "QMessageBox", FakeMB)

    src = tmp_path / "a.mp4"
    src.write_bytes(b"\0" * 10)
    win._add_paths([str(src)])
    win.cb_kind.setCurrentIndex(win.cb_kind.findData(F.VIDEO))
    win.cb_format.setCurrentIndex(win.cb_format.findData("mkv"))
    i = win.cb_vcodec.findData("libsvtav1")
    if i < 0:
        pytest.skip("该格式无 libsvtav1 选项")
    win.cb_vcodec.setCurrentIndex(i)

    win.start()
    assert shown.get("title") == "编码器不可用"
    assert not win.queue.running


def test_no_crash_when_encoder_list_unknown(qapp, monkeypatch):
    """探测不到编码器列表时（返回空集），不应禁用任何项。"""
    import app.core.ffprobe as fp
    import app.ui.main_window as mw
    monkeypatch.setattr(fp, "available_encoders", frozenset)
    monkeypatch.setattr(mw, "available_encoders", frozenset)
    try:
        w = mw.MainWindow()
    except Exception as exc:
        pytest.skip(f"无法创建窗口：{exc}")
    w.cb_format.setCurrentIndex(w.cb_format.findData("mkv"))
    assert all(en for _, en in _codec_items(w.cb_vcodec)), \
        "编码器列表未知时不应禁用任何选项"


def test_preset_falls_back_to_available_encoder(win):
    """预设指定的编码器不可用时，应自动替换为可用项。

    回归：选择《AV1 高压缩》预设后，界面照单全收设成 libsvtav1，
    而精简版 FFmpeg 并无该编码器，转换时才抛出 Unknown encoder。
    """
    i = win.cb_preset.findData("AV1 高压缩")
    if i < 0:
        pytest.skip("未找到 AV1 预设")
    win.cb_preset.setCurrentIndex(i)

    sel = win.cb_vcodec.currentData()
    assert sel != "libsvtav1"
    assert sel in LIMITED, f"回退后仍不可用：{sel}"
    assert win.collect_params()["video_codec"] in LIMITED


def test_preset_notifies_user_about_substitution(win):
    i = win.cb_preset.findData("AV1 高压缩")
    if i < 0:
        pytest.skip("未找到 AV1 预设")
    win.cb_preset.setCurrentIndex(i)
    assert "自动替换" in win.status.currentMessage()


def test_all_builtin_presets_yield_usable_encoder(win):
    """任何内置预设应用后，都不该留下不可用的编码器。"""
    from app.core import presets as P

    for p in P.BUILTIN:
        if p.kind == F.IMAGE:
            continue
        idx = win.cb_kind.findData(p.kind)
        if idx >= 0:
            win.cb_kind.setCurrentIndex(idx)
        j = win.cb_preset.findData(p.name)
        if j < 0:
            continue
        win.cb_preset.setCurrentIndex(j)
        params = win.collect_params()
        for key in ("video_codec", "audio_codec"):
            enc = params.get(key) or ""
            if not enc or enc in ("copy", "none"):
                continue
            assert enc in LIMITED, f"预设《{p.name}》产生了不可用的 {key}={enc}"
