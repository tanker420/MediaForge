"""核心模块测试：格式目录、命名、预设（无需 ffmpeg / Qt）。"""
from __future__ import annotations

import os

from app.core import formats as F
from app.core import naming
from app.core import presets as P


# ---------------- 格式目录 ----------------
def test_formats_three_kinds():
    assert F.formats_for(F.VIDEO)
    assert F.formats_for(F.AUDIO)
    assert F.formats_for(F.IMAGE)


def test_find_format():
    assert F.find_format("mp4", F.VIDEO).ext == "mp4"
    assert F.find_format(".MP3", F.AUDIO).ext == "mp3"
    assert F.find_format("png", F.IMAGE).ext == "png"
    assert F.find_format("mp4", F.AUDIO) is None
    assert F.find_format("not_a_format") is None


def test_detect_kind():
    assert F.detect_kind("a.mp4") == F.VIDEO
    assert F.detect_kind("b.flac") == F.AUDIO
    assert F.detect_kind("c.png") == F.IMAGE


def test_default_params_cover_core_keys():
    d = F.default_params_for(F.VIDEO)
    assert "overwrite" in d and "extra_args" in d
    assert "video_codec" not in d  # 编码器由格式/用户显式指定
    d_img = F.default_params_for(F.IMAGE)
    assert "quality" in d_img and "overwrite" in d_img
    assert "extra_args" not in d_img


def test_every_codec_param_valid():
    for codec in list(F.VIDEO_CODECS.values()) + list(F.AUDIO_CODECS.values()):
        for p in codec.params:
            assert p.type in ("bool", "int", "float", "str", "choice"), codec.encoder
            if p.type == "choice":
                assert p.choices, f"{codec.encoder}.{p.key} 缺少选项"
            if p.type == "bool":
                assert isinstance(p.default, bool)


# ---------------- 命名 ----------------
def test_human_size():
    assert naming.human_size(512) == "512 B"
    assert naming.human_size(2048) == "2.00 KB"
    assert naming.human_size(5 * 1024 ** 3) == "5.00 GB"


def test_human_time():
    assert naming.human_time(0) == "--:--"
    assert naming.human_time(65) == "01:05"
    assert naming.human_time(3661) == "1:01:01"


def test_sanitize():
    # < > : " / \ | ? * 共 8 个非法字符 → 8 个下划线
    assert naming.sanitize('a<b>:"/\\|?*.mp4') == "a_b________.mp4"
    assert naming.sanitize("  ") == "output"


def test_build_output_path_same_dir_avoidance(tmp_path):
    src = tmp_path / "movie.mp4"
    src.write_bytes(b"x")
    out = naming.build_output_path(str(src), "", "mkv")
    assert out.endswith(".mkv") and out != str(src)
    # 同源同名时自动加 _converted
    same = naming.build_output_path(str(src), "", "mp4")
    assert same.endswith("_converted.mp4")


def test_build_output_path_pattern(tmp_path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"x")
    out = naming.build_output_path(str(src), str(tmp_path), "mp3",
                                   pattern="{name}_{date}")
    assert os.path.basename(out).startswith("clip_20")


def test_unique_path(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("1")
    assert naming.unique_path(str(p)) == str(tmp_path / "a (1).txt")


def test_dedupe(tmp_path):
    taken = {str(tmp_path / "a.mp4")}   # 已存在同名文件
    first = naming.dedupe(str(tmp_path / "a.mp4"), taken)
    second = naming.dedupe(str(tmp_path / "a.mp4"), taken)
    assert first == str(tmp_path / "a (1).mp4")
    assert second == str(tmp_path / "a (2).mp4")
    assert {first, second} <= taken


def test_collect_files_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "1.mp4").write_bytes(b"")
    (tmp_path / "2.png").write_bytes(b"")
    (tmp_path / "sub" / "3.mp4").write_bytes(b"")
    got = naming.collect_files([str(tmp_path)], recursive=True, exts=("mp4",))
    assert len(got) == 2
    assert all(f.endswith(".mp4") for f in got)


# ---------------- 预设 ----------------
def test_builtin_presets_cover_all_kinds():
    for kind in (F.VIDEO, F.AUDIO, F.IMAGE):
        assert P.all_presets(kind), f"{kind} 缺少预设"


def test_builtin_preset_params_valid():
    for p in P.BUILTIN:
        assert p.ext == F.find_format(p.ext, p.kind).ext, p.name
        for key in ("video_codec", "audio_codec"):
            enc = p.params.get(key)
            if enc and enc != "copy":
                pool = F.VIDEO_CODECS if key == "video_codec" else F.AUDIO_CODECS
                assert enc in pool, f"{p.name} 引用了未注册编码器 {enc}"


def test_find_preset():
    assert P.find_preset("MP4 通用高质量") is not None
    assert P.find_preset("不存在的预设") is None


# ---------------- CLI ----------------
def test_cli_overwrite_defaults_true():
    """CLI 的 --overwrite/--no-overwrite 互斥组，未显式指定时默认应为覆盖（True）。"""
    from app.cli import build_parser
    assert build_parser().parse_args(["-i", "x.mp4", "-F", "mp4"]).overwrite is True
    assert build_parser().parse_args(
        ["-i", "x.mp4", "-F", "mp4", "--overwrite"]).overwrite is True
    assert build_parser().parse_args(
        ["-i", "x.mp4", "-F", "mp4", "--no-overwrite"]).overwrite is False


def test_user_presets_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "config_dir", lambda: tmp_path)
    P.save_user_presets([P.Preset("我的预设", F.VIDEO, "mkv", {"crf": 18})])
    loaded = P.load_user_presets()
    assert len(loaded) == 1
    assert loaded[0].name == "我的预设"
    assert loaded[0].params["crf"] == 18
