"""ffmpeg 命令构建测试 —— 保证参数被正确翻译。"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import formats as F  # noqa: E402
from app.core import ffmpeg_builder as B  # noqa: E402
from app.core.ffprobe import MediaInfo, StreamInfo, ffmpeg_path  # noqa: E402

pytestmark = pytest.mark.skipif(ffmpeg_path() is None, reason="需要 ffmpeg")


def cmd(params, src="in.mkv", dst="out.mp4", info=None, pass_no=0):
    return B.build_command(src, dst, params, info, pass_no)


def test_basic_h264_command():
    c = cmd({"video_codec": "libx264", "audio_codec": "aac",
             "crf": 20, "preset": "slow"})
    assert "-c:v" in c and c[c.index("-c:v") + 1] == "libx264"
    assert c[c.index("-crf") + 1] == "20"
    assert c[c.index("-preset") + 1] == "slow"
    assert c[-1] == "out.mp4"


def test_copy_codec_skips_filters():
    c = cmd({"video_codec": "copy", "audio_codec": "copy", "width": 640})
    assert "-vf" not in c
    assert c[c.index("-c:v") + 1] == "copy"


def test_bitrate_mode_uses_bv():
    c = cmd({"video_codec": "libx264", "rate_mode": "cbr", "bitrate": "4000k"})
    assert c[c.index("-b:v") + 1] == "4000k"
    assert "-maxrate" in c


def test_two_pass_first_pass_discards_output():
    p = {"video_codec": "libx264", "audio_codec": "aac",
         "two_pass": True, "bitrate": "2000k"}
    c1 = cmd(p, pass_no=1)
    assert c1[c1.index("-pass") + 1] == "1"
    assert "-an" in c1, "第一遍应禁用音频"
    assert c1[c1.index("-f") + 1] == "null"
    assert c1[-1] in ("/dev/null", "NUL")


def test_two_pass_uses_bitrate_not_crf():
    """两遍编码必须走码率模式，否则 -pass 无意义。"""
    c = cmd({"video_codec": "libx264", "two_pass": True,
             "bitrate": "2000k", "rate_mode": "crf"}, pass_no=2)
    assert "-b:v" in c
    assert "-crf" not in c


def test_gif_palette_uses_filter_complex():
    c = cmd({"video_codec": "gif", "gif_palette": True, "width": 320},
            dst="out.gif")
    fc = c[c.index("-filter_complex") + 1]
    assert "palettegen" in fc and "paletteuse" in fc


def test_audio_only_output_disables_video():
    c = cmd({"audio_codec": "libmp3lame", "audio_bitrate": "320k"}, dst="out.mp3")
    assert "-vn" in c
    assert c[c.index("-b:a") + 1] == "320k"


def test_mp3_vbr_mode():
    c = cmd({"audio_codec": "libmp3lame", "audio_mode": "vbr",
             "mp3_vbr_quality": 0}, dst="out.mp3")
    assert c[c.index("-q:a") + 1] == "0"
    assert "-b:a" not in c


def test_opus_vbr_flag():
    c = cmd({"audio_codec": "libopus", "audio_mode": "cbr"}, dst="out.opus")
    assert c[c.index("-vbr") + 1] == "off"


def test_flac_compression_level():
    c = cmd({"audio_codec": "flac", "compression_level": 8}, dst="out.flac")
    assert c[c.index("-compression_level") + 1] == "8"


def test_trim_options():
    c = cmd({"video_codec": "libx264", "start_time": "10", "duration": "5"})
    assert c[c.index("-ss") + 1] == "10"
    assert c[c.index("-t") + 1] == "5"
    assert c.index("-ss") < c.index("-i"), "-ss 应放在 -i 之前以加速定位"


def test_faststart_for_mp4():
    c = cmd({"video_codec": "libx264", "faststart": True})
    assert c[c.index("-movflags") + 1] == "+faststart"


def test_no_audio_when_source_has_none():
    info = MediaInfo(path="in.mkv", streams=[StreamInfo(0, "video", "h264")])
    c = cmd({"video_codec": "libx264", "audio_codec": "aac"}, info=info)
    assert "-an" in c


def test_audio_kept_when_probe_returned_nothing():
    """探测失败（无 ffprobe）时不能误判为无音轨。"""
    info = MediaInfo(path="in.mkv", streams=[])
    c = cmd({"video_codec": "libx264", "audio_codec": "aac"}, info=info)
    assert "-an" not in c
    assert c[c.index("-c:a") + 1] == "aac"


def test_extra_args_appended():
    c = cmd({"video_codec": "libx264", "extra_args": "-tag:v hvc1"})
    assert "-tag:v" in c and "hvc1" in c


def test_overwrite_flag():
    assert "-y" in cmd({"video_codec": "libx264", "overwrite": True})
    assert "-n" in cmd({"video_codec": "libx264", "overwrite": False})


@pytest.mark.parametrize("ext", [f.ext for f in F.VIDEO_FORMATS])
def test_every_video_format_builds(ext):
    fmt = F.find_format(ext, F.VIDEO)
    c = cmd({"video_codec": fmt.video_codecs[0],
             "audio_codec": fmt.audio_codecs[0] if fmt.audio_codecs else ""},
            dst=f"out.{ext}")
    assert c[-1] == f"out.{ext}"


@pytest.mark.parametrize("ext", [f.ext for f in F.AUDIO_FORMATS])
def test_every_audio_format_builds(ext):
    fmt = F.find_format(ext, F.AUDIO)
    c = cmd({"audio_codec": fmt.audio_codecs[0]}, dst=f"out.{ext}")
    assert "-vn" in c
