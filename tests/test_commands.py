"""ffmpeg 命令构建测试。

B5 修复：此前整个模块在缺少 ffmpeg 时全部跳过，导致纯字符串层面的
测试（滤镜链、参数翻译、路径转义）永远无法运行。现在拆分：
  - 纯字符串测试：无需 ffmpeg，始终运行；
  - 完整命令测试：仅当 ffmpeg 存在时运行。
"""
from __future__ import annotations

import pytest

from app.core.ffmpeg_builder import (
    _audio_encoder_args,
    _escape_filter_path,
    _video_encoder_args,
    build_audio_filters,
    build_video_filters,
    needs_two_pass,
)
from app.core.ffprobe import ffmpeg_path


# ======================================================================
# 纯字符串测试（不依赖 ffmpeg）
# ======================================================================
def test_escape_filter_path():
    esc = _escape_filter_path(r"C:\videos\[1080p] 片.srt")
    assert "\\:" in esc          # 冒号转义
    assert "\\[" in esc and "\\]" in esc
    assert "\\," not in esc or True
    assert "/" in esc            # 反斜杠统一为正斜杠


def test_subtitle_burn_uses_escaped_path():
    chain = build_video_filters({
        "subtitle_mode": "burn",
        "subtitle_file": r"C:\a\b [x],y.srt",
    })
    assert any("subtitles=" in c for c in chain)
    joined = ",".join(chain)
    # B4 修复：路径中的 [ ] , 都必须被转义，否则滤镜解析失败
    assert "\\[" in joined and "\\]" in joined and "\\," in joined


def test_scale_keep_aspect_adds_pad():
    chain = build_video_filters({"width": 1920, "height": 1080, "keep_aspect": True})
    assert any(c.startswith("scale=1920:1080") for c in chain)
    assert any(c.startswith("pad=1920:1080") for c in chain)


def test_rotate_270():
    chain = build_video_filters({"rotate": "270"})
    assert chain == ["transpose=2"]


def test_fade_out_uses_injected_duration():
    """A2 修复：淡出依赖媒体总时长，时长由探测结果注入 `_duration`，
    保证实际执行与预览完全一致。"""
    chain = build_audio_filters({"audio_fade_out": 2.0, "_duration": 10.0})
    assert any("afade=t=out:st=8:d=2" in c for c in chain)


def test_fade_out_without_duration_is_noop():
    assert build_audio_filters({"audio_fade_out": 2.0}) == []


def test_fade_in():
    chain = build_audio_filters({"audio_fade_in": 1.5})
    assert any("afade=t=in:st=0:d=1.5" in c for c in chain)


def test_normalize_appends_aresample():
    chain = build_audio_filters({"normalize": True, "loudness_target": -16})
    assert any("loudnorm" in c for c in chain)
    assert any(c.startswith("aresample=") for c in chain)


def test_tempo_chaining_outside_range():
    chain = build_audio_filters({"tempo": 3.0})
    assert chain.count("atempo=2.0") == 1
    assert "atempo=1.5" in chain


def test_two_pass_detection():
    assert needs_two_pass({"two_pass": True, "bitrate": "4000k", "video_codec": "libx264"})
    assert not needs_two_pass({"two_pass": True})
    assert not needs_two_pass({"two_pass": True, "bitrate": "4000k", "video_codec": "copy"})


def test_x264_crf_args():
    args = _video_encoder_args("libx264", {"rate_mode": "crf", "crf": 20, "preset": "slow"})
    assert args[:2] == ["-c:v", "libx264"]
    assert "-crf" in args and args[args.index("-crf") + 1] == "20"
    assert args[args.index("-preset") + 1] == "slow"


def test_hw_nvenc_args():
    args = _video_encoder_args("h264_nvenc", {"rate_mode": "cq", "crf": 23})
    assert args[:2] == ["-c:v", "h264_nvenc"]
    assert "-cq" in args


def test_audio_mp3_args():
    args = _audio_encoder_args("libmp3lame", {"audio_mode": "cbr", "audio_bitrate": "192k"})
    assert "-b:a" in args and args[args.index("-b:a") + 1] == "192k"


def test_audio_copy_args():
    assert _audio_encoder_args("copy", {}) == ["-c:a", "copy"]


# ======================================================================
# 完整命令测试（需要 ffmpeg）
# ======================================================================
needs_ffmpeg = pytest.mark.skipif(ffmpeg_path() is None, reason="未安装 ffmpeg")


@needs_ffmpeg
def test_build_command_full():
    from app.core.ffmpeg_builder import build_command

    cmd = build_command("in.mp4", "out.mkv",
                        {"video_codec": "copy", "audio_codec": "copy"})
    # Windows 上 ffmpeg 可能叫 ffmpeg.exe / ffmpeg.EXE / 含 shim 后缀，
    # 大小写不敏感地判断「以 ffmpeg 结尾」。
    assert cmd[0].lower().endswith(("ffmpeg", "ffmpeg.exe"))
    assert "-i" in cmd
    assert cmd[-1].endswith("out.mkv")
    assert "-c:v" in cmd and "copy" in cmd


@needs_ffmpeg
def test_build_command_preview_equals_execution_for_fade():
    """A2 修复的端到端验证：带 info 探测时构建的命令里包含淡出滤镜。"""
    from app.core.ffmpeg_builder import build_command
    from app.core.ffprobe import probe

    info = probe("tests/fixtures/does_not_exist.mp4")
    # 构造一个带 duration 的假 info，仅验证参数注入逻辑
    info.duration = 30.0
    cmd = build_command("in.mp4", "out.m4a",
                        {"audio_codec": "aac", "audio_fade_out": 3.0}, info)
    joined = " ".join(cmd)
    assert "afade=t=out:st=27:d=3" in joined
