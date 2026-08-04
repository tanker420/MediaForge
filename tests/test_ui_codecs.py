"""UI 与格式目录的一致性测试（无需 Qt 实例）。

保证 formats.py 作为单一事实来源的完整性：每个容器引用的编码器
都必须已注册，且 GUI 参数表单暴露的参数集合与目录一致。
"""
from __future__ import annotations

from app.core import formats as F

# GUI 表单中不暴露、由专属控件处理的参数
_GUI_EXCLUDED = {"extra_args", "overwrite"}


def test_video_formats_codecs_registered():
    for fmt in F.VIDEO_FORMATS:
        for enc in fmt.video_codecs:
            assert enc in F.VIDEO_CODECS, f"{fmt.ext} 引用了未注册视频编码器 {enc}"
        for enc in fmt.audio_codecs:
            assert enc in F.AUDIO_CODECS, f"{fmt.ext} 引用了未注册音频编码器 {enc}"


def test_audio_formats_codecs_registered():
    for fmt in F.AUDIO_FORMATS:
        for enc in fmt.audio_codecs:
            assert enc in F.AUDIO_CODECS, f"{fmt.ext} 引用了未注册音频编码器 {enc}"


def test_all_encoders_have_labels():
    for name, codec in {**F.VIDEO_CODECS, **F.AUDIO_CODECS}.items():
        assert codec.label, name
        assert codec.encoder == name


def test_gui_video_param_pool_complete():
    """GUI 视频表单 = 通用参数 + 视频滤镜 + 音频滤镜 + 当前编码器参数。
    这里验证基础池与目录一致，且不含专家字段。"""
    pool = list(F.GENERAL_PARAMS) + list(F.VIDEO_FILTER_PARAMS) + list(F.AUDIO_FILTER_PARAMS)
    keys = {p.key for p in pool}
    assert "width" in keys and "crf" not in keys          # crf 来自编码器
    assert "extra_args" in keys                            # 目录里有（CLI 用）
    gui_keys = keys - _GUI_EXCLUDED
    assert "extra_args" not in gui_keys and "overwrite" not in gui_keys


def test_gui_image_param_pool():
    keys = {p.key for p in F.IMAGE_PARAMS}
    assert "quality" in keys and "ico_sizes" in keys
    # overwrite 属于图片参数（引擎需要），GUI 由专属复选框提供；extra_args 不出现
    assert "extra_args" not in keys
    assert "overwrite" in keys


def test_video_codec_params_do_not_collide_after_dedup():
    """多段参数合并后按键去重不应丢参数（main_window 中按 key 去重）。"""
    pool = list(F.GENERAL_PARAMS) + list(F.VIDEO_FILTER_PARAMS) + list(F.AUDIO_FILTER_PARAMS)
    seen = {}
    for p in pool:
        seen[p.key] = p
    merged = list(seen.values())
    assert len(merged) == len({p.key for p in merged})


def test_choices_contain_default():
    for codec in {**F.VIDEO_CODECS, **F.AUDIO_CODECS}.values():
        for p in codec.params:
            if p.type == "choice" and p.default is not None:
                assert p.default in p.choices, f"{codec.encoder}.{p.key} 默认值不在选项中"
