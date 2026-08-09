"""设置两级分层 / 滑块联动 / 防呆的回归测试。

v1.3.0 迭代引入：
- formats.Param 新增 tier（basic=一级常用 / advanced=二级高级）与 unit（固定单位后缀）；
- 桌面 ParamForm 按 tier 分两级渲染，高级区默认折叠；
- 有取值范围的数值参数用「滑块 + 数值框」联动控件，越界自动 clamp；
- 命名规则下拉 = 内置默认选项 + 自定义…，自定义为空回退 {name}。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import formats as F  # noqa: E402
from app.ui.widgets import ParamForm, SliderParam  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _all_params() -> list[F.Param]:
    pool = list(F.GENERAL_PARAMS) + list(F.VIDEO_FILTER_PARAMS) \
        + list(F.AUDIO_FILTER_PARAMS) + list(F.IMAGE_PARAMS)
    for c in list(F.VIDEO_CODECS.values()) + list(F.AUDIO_CODECS.values()):
        pool += list(c.params)
    return pool


# --------------------------------------------------------------------------
# schema 层
# --------------------------------------------------------------------------
def test_tier_values_valid() -> None:
    for p in _all_params():
        assert p.tier in (F.BASIC, F.ADVANCED), f"{p.key} tier 非法：{p.tier}"


def test_basic_keys_cover_common_settings() -> None:
    keys = {p.key for p in _all_params() if p.tier == F.BASIC}
    expected = {
        "start_time", "end_time", "duration",          # 裁剪
        "width", "height", "keep_aspect", "fps", "rotate",  # 画面
        "rate_mode", "crf", "bitrate",                 # 码率
        "audio_bitrate", "volume",                     # 音频
        "quality",                                     # 图片质量
    }
    missing = expected - keys
    assert not missing, f"一级常用设置缺少：{missing}"


def test_unit_not_embedded_in_label() -> None:
    """单位独立成 unit 字段后，标签不再内嵌单位（手动输入不改单位的前提）。"""
    for p in _all_params():
        if p.unit:
            assert p.unit not in p.label, f"{p.key} 标签仍内嵌单位：{p.label}"
    by_key = {p.key: p for p in _all_params()}
    assert by_key["volume"].unit == "dB"
    assert by_key["width"].unit == "px"


# --------------------------------------------------------------------------
# 控件层：滑块联动 + 防呆
# --------------------------------------------------------------------------
def test_slider_clamps_out_of_range(qapp) -> None:
    p = F.Param("crf", "CRF 质量", "float", 23, minimum=0, maximum=51, step=1)
    ctrl = SliderParam(p)
    ctrl.set_value(999)
    assert ctrl.value() == 51.0
    ctrl.set_value(-5)
    assert ctrl.value() == 0.0
    ctrl.set_value("abc")          # 非法输入保持原值（防呆）
    assert ctrl.value() == 0.0


def test_slider_and_spin_sync(qapp) -> None:
    p = F.Param("volume", "音量调整", "float", 0, minimum=-40, maximum=40,
                step=0.5, unit="dB")
    ctrl = SliderParam(p)
    ctrl.slider.setValue(ctrl.slider.maximum())
    assert ctrl.value() == 40.0
    assert ctrl.spin.suffix().strip() == "dB"   # 单位是固定后缀
    ctrl.spin.setValue(-16)
    assert ctrl.slider.value() == int(round((-16 - (-40)) / 0.5))


def test_int_slider_keeps_int(qapp) -> None:
    p = F.Param("quality", "质量", "int", 90, minimum=1, maximum=100)
    ctrl = SliderParam(p)
    ctrl.set_value(55.6)
    assert ctrl.value() == 56          # QSpinBox 取整
    assert isinstance(ctrl.value(), int)


# --------------------------------------------------------------------------
# 表单层：两级分层
# --------------------------------------------------------------------------
def test_form_two_tier_and_advanced_collapsed(qapp) -> None:
    params = [
        F.Param("crf", "CRF 质量", "float", 23, minimum=0, maximum=51,
                tier=F.BASIC),
        F.Param("gop", "关键帧间隔 GOP", "int", 0, minimum=0, maximum=1200),
        F.Param("x264_params", "x264 额外参数", "str", ""),
    ]
    form = ParamForm()
    form.set_params(params)
    assert not form.advanced_visible()          # 高级区默认折叠
    assert isinstance(form._controls["crf"], SliderParam)
    assert form._adv_toggle is not None
    form._adv_toggle.click()
    assert form.advanced_visible()
    form._adv_toggle.click()
    assert not form.advanced_visible()
    # 折叠状态下取值不受影响
    vals = form.values()
    assert vals["crf"] == 23.0 and vals["gop"] == 0 and vals["x264_params"] == ""


def test_form_set_values_clamps(qapp) -> None:
    form = ParamForm()
    form.set_params([F.Param("crf", "CRF", "float", 23, minimum=0,
                             maximum=51, tier=F.BASIC)])
    form.set_values({"crf": 999})
    assert form.values()["crf"] == 51.0


# --------------------------------------------------------------------------
# 主窗口：命名规则默认选项 + 自定义
# --------------------------------------------------------------------------
def test_pattern_default_options_and_custom(qapp, monkeypatch, tmp_path):
    from app.ui.main_window import MainWindow
    monkeypatch.setattr(MainWindow, "_maybe_check_update_on_startup",
                        lambda self: None)
    w = MainWindow()
    try:
        # 4 个内置默认 + 1 个自定义
        assert w.cb_pattern.count() == 5
        assert w.cb_pattern.itemText(4).startswith("自定义")
        w.cb_pattern.setCurrentIndex(0)
        assert w.ed_pattern.isHidden()
        assert w._current_pattern() == "{name}"
        w.cb_pattern.setCurrentIndex(4)
        assert not w.ed_pattern.isHidden()
        assert w._current_pattern() == "{name}"      # 空自定义防呆回退
        w.ed_pattern.setText("{name}_{date}")
        assert w._current_pattern() == "{name}_{date}"
    finally:
        w.close()


def test_workers_is_slider_with_clamp(qapp, monkeypatch) -> None:
    from app.ui.main_window import MainWindow
    monkeypatch.setattr(MainWindow, "_maybe_check_update_on_startup",
                        lambda self: None)
    w = MainWindow()
    try:
        assert isinstance(w.sp_workers, SliderParam)
        w.sp_workers.set_value(99)
        assert w.sp_workers.value() == 8
        w.sp_workers.set_value(0)
        assert w.sp_workers.value() == 1
    finally:
        w.close()
