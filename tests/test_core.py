"""核心逻辑单元测试（不依赖 ffmpeg 是否安装）。"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import formats as F  # noqa: E402
from app.core import naming  # noqa: E402
from app.core.ffmpeg_builder import (  # noqa: E402
    build_audio_filters, build_video_filters,
)


# ---------------------------- 格式目录 ----------------------------
def test_format_catalog_not_empty():
    assert len(F.VIDEO_FORMATS) >= 15
    assert len(F.AUDIO_FORMATS) >= 15
    assert len(F.IMAGE_FORMATS) >= 15


def test_every_video_format_has_codecs():
    for f in F.VIDEO_FORMATS:
        assert f.video_codecs, f"{f.ext} 缺少视频编码器"


def test_codec_references_are_defined():
    """容器里列出的编码器必须都在编码器表中有定义。"""
    for f in F.VIDEO_FORMATS:
        for c in f.video_codecs:
            assert c in F.VIDEO_CODECS, f"{f.ext} 引用了未定义的视频编码器 {c}"
        for c in f.audio_codecs:
            assert c in F.AUDIO_CODECS, f"{f.ext} 引用了未定义的音频编码器 {c}"
    for f in F.AUDIO_FORMATS:
        for c in f.audio_codecs:
            assert c in F.AUDIO_CODECS, f"{f.ext} 引用了未定义的音频编码器 {c}"


def test_param_defaults_within_range():
    pools = [F.GENERAL_PARAMS, F.VIDEO_FILTER_PARAMS, F.AUDIO_FILTER_PARAMS, F.IMAGE_PARAMS]
    pools += [c.params for c in F.VIDEO_CODECS.values()]
    pools += [c.params for c in F.AUDIO_CODECS.values()]
    for pool in pools:
        for p in pool:
            if p.type in ("int", "float") and p.default is not None:
                if p.minimum is not None:
                    assert p.default >= p.minimum, f"{p.key} 默认值低于下限"
                if p.maximum is not None:
                    assert p.default <= p.maximum, f"{p.key} 默认值高于上限"
            if p.type == "choice" and p.choices and p.default is not None:
                assert str(p.default) in p.choices, f"{p.key} 默认值不在候选项内"


@pytest.mark.parametrize("path,expected", [
    ("a.mp4", F.VIDEO), ("a.mkv", F.VIDEO), ("a.avi", F.VIDEO),
    ("a.mp3", F.AUDIO), ("a.flac", F.AUDIO), ("a.wav", F.AUDIO),
    ("a.png", F.IMAGE), ("a.jpg", F.IMAGE), ("a.heic", F.IMAGE),
])
def test_detect_kind(path, expected):
    assert F.detect_kind(path) == expected


# ---------------------------- 滤镜链 ----------------------------
def test_scale_filter_keeps_aspect():
    vf = build_video_filters({"width": 1280, "height": 720, "keep_aspect": True})
    joined = ",".join(vf)
    assert "force_original_aspect_ratio=decrease" in joined
    assert "pad=1280:720" in joined


def test_scale_filter_stretch():
    vf = build_video_filters({"width": 1280, "height": 720, "keep_aspect": False})
    assert "scale=1280:720" in ",".join(vf)


def test_single_dimension_uses_auto():
    vf = build_video_filters({"width": 640, "keep_aspect": False})
    assert "scale=640:-2" in ",".join(vf)


def test_rotate_and_flip():
    vf = build_video_filters({"rotate": "90", "hflip": True, "vflip": True})
    joined = ",".join(vf)
    assert "transpose=1" in joined and "hflip" in joined and "vflip" in joined


def test_eq_filter_only_when_changed():
    assert not build_video_filters({"brightness": 0, "contrast": 1, "saturation": 1, "gamma": 1})
    vf = build_video_filters({"contrast": 1.5})
    assert "eq=contrast=1.5" in ",".join(vf)


def test_loudnorm_resamples_back():
    """loudnorm 输出 192kHz，必须重采样回去，否则 libvorbis 会失败。"""
    af = build_audio_filters({"normalize": True, "_sample_rate": 44100})
    joined = ",".join(af)
    assert "loudnorm" in joined
    assert "aresample=44100" in joined
    assert joined.index("loudnorm") < joined.index("aresample")


def test_atempo_chained_for_extreme_values():
    """atempo 单次只支持 0.5~2.0，超出范围需串联多个。"""
    af = build_audio_filters({"tempo": 4.0})
    assert len(af) == 2
    product = 1.0
    for f in af:
        assert f.startswith("atempo=")
        product *= float(f.split("=")[1])
    assert product == pytest.approx(4.0)

    af = build_audio_filters({"tempo": 0.25})
    product = 1.0
    for f in af:
        product *= float(f.split("=")[1])
    assert product == pytest.approx(0.25)


def test_volume_filter():
    assert "volume=-6dB" in ",".join(build_audio_filters({"volume": -6}))
    assert not build_audio_filters({"volume": 0})


# ---------------------------- 命名 ----------------------------
def test_build_output_path_pattern(tmp_path):
    src = tmp_path / "movie.mkv"
    src.write_bytes(b"x")
    out = naming.build_output_path(str(src), str(tmp_path), "mp4", "{name}_conv")
    assert os.path.basename(out) == "movie_conv.mp4"


def test_output_never_equals_input(tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"x")
    out = naming.build_output_path(str(src), str(tmp_path), "mp4", "{name}")
    assert os.path.abspath(out) != os.path.abspath(str(src))


def test_dedupe_avoids_collisions():
    taken: set[str] = set()
    a = naming.dedupe("/out/x.mp3", taken)
    b = naming.dedupe("/out/x.mp3", taken)
    c = naming.dedupe("/out/x.mp3", taken)
    assert a != b != c and len({a, b, c}) == 3


def test_sanitize_removes_illegal_chars():
    assert "/" not in naming.sanitize("a/b")
    assert ":" not in naming.sanitize("a:b")
    assert naming.sanitize("...") == "output"


def test_human_size():
    assert naming.human_size(0) == "0 B"
    assert naming.human_size(1536).startswith("1.50 KB")


def test_human_time():
    assert naming.human_time(0) == "--:--"
    assert naming.human_time(65) == "01:05"
    assert naming.human_time(3661) == "1:01:01"


def test_collect_files_filters_by_ext(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.txt").write_bytes(b"x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.mp3").write_bytes(b"x")
    found = naming.collect_files([str(tmp_path)], True, ("mp4", "mp3"))
    names = sorted(os.path.basename(f) for f in found)
    assert names == ["a.mp4", "c.mp3"]
