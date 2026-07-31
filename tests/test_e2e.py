"""端到端转换测试：真实调用 ffmpeg / Pillow 生成文件。"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import formats as F  # noqa: E402
from app.core.converter import Job, Status, run_job  # noqa: E402
from app.core.ffprobe import CREATE_NO_WINDOW, ffmpeg_path, probe  # noqa: E402

HAVE_FFMPEG = ffmpeg_path() is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="需要 ffmpeg")

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False
needs_pil = pytest.mark.skipif(not HAVE_PIL, reason="需要 Pillow")


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    out = d / "src.mp4"
    subprocess.run([ffmpeg_path(), "-y", "-v", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=15:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(out)], check=True, creationflags=CREATE_NO_WINDOW)
    return str(out)


@pytest.fixture(scope="module")
def audio(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    out = d / "src.flac"
    subprocess.run([ffmpeg_path(), "-y", "-v", "error",
                    "-f", "lavfi", "-i", "sine=frequency=330:duration=2",
                    "-c:a", "flac", str(out)], check=True,
                   creationflags=CREATE_NO_WINDOW)
    return str(out)


@pytest.fixture(scope="module")
def picture(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    out = d / "src.png"
    Image.new("RGBA", (320, 240), (10, 120, 220, 255)).save(out)
    return str(out)


def _run(src, dst, params, kind):
    job = run_job(Job(src=src, dst=dst, params=params, kind=kind))
    assert job.status is Status.DONE, f"转换失败：{job.message}"
    assert os.path.getsize(dst) > 0
    return job


# ---------------------------- 视频 ----------------------------
@needs_ffmpeg
@pytest.mark.parametrize("ext,vc,ac", [
    ("mkv", "libx264", "flac"),
    ("webm", "libvpx-vp9", "libopus"),
    ("avi", "mpeg4", "libmp3lame"),
    ("mov", "libx264", "aac"),
    ("ts", "libx264", "aac"),
])
def test_video_formats(video, tmp_path, ext, vc, ac):
    dst = str(tmp_path / f"out.{ext}")
    _run(video, dst, {"video_codec": vc, "audio_codec": ac,
                      "crf": 35, "preset": "ultrafast", "cpu_used": 8,
                      "width": 160, "height": 120}, F.VIDEO)


@needs_ffmpeg
def test_video_to_gif(video, tmp_path):
    dst = str(tmp_path / "out.gif")
    _run(video, dst, {"video_codec": "gif", "gif_palette": True,
                      "fps": "8", "width": 120}, F.VIDEO)


@needs_ffmpeg
def test_remux_is_lossless(video, tmp_path):
    """copy 模式应保持视频流不变。"""
    dst = str(tmp_path / "out.mkv")
    _run(video, dst, {"video_codec": "copy", "audio_codec": "copy"}, F.VIDEO)
    a, b = probe(video), probe(dst)
    if a.video and b.video:
        assert a.video.codec_name == b.video.codec_name


@needs_ffmpeg
def test_resize_applies(video, tmp_path):
    dst = str(tmp_path / "small.mp4")
    _run(video, dst, {"video_codec": "libx264", "audio_codec": "aac",
                      "preset": "ultrafast", "crf": 35,
                      "width": 160, "height": 120, "keep_aspect": False}, F.VIDEO)
    info = probe(dst)
    if info.video and info.video.width:
        assert (info.video.width, info.video.height) == (160, 120)


@needs_ffmpeg
def test_trim_shortens_output(video, tmp_path):
    dst = str(tmp_path / "cut.mp4")
    _run(video, dst, {"video_codec": "libx264", "audio_codec": "aac",
                      "preset": "ultrafast", "duration": "1"}, F.VIDEO)
    info = probe(dst)
    if info.duration:
        assert info.duration < 1.6


@needs_ffmpeg
def test_two_pass_encoding(video, tmp_path):
    dst = str(tmp_path / "2pass.mp4")
    _run(video, dst, {"video_codec": "libx264", "audio_codec": "aac",
                      "two_pass": True, "bitrate": "200k",
                      "preset": "ultrafast"}, F.VIDEO)


# ---------------------------- 音频 ----------------------------
@needs_ffmpeg
@pytest.mark.parametrize("ext,ac", [
    ("mp3", "libmp3lame"), ("opus", "libopus"), ("wav", "pcm_s16le"),
    ("m4a", "alac"), ("ogg", "libvorbis"), ("flac", "flac"),
])
def test_audio_formats(audio, tmp_path, ext, ac):
    dst = str(tmp_path / f"out.{ext}")
    _run(audio, dst, {"audio_codec": ac}, F.AUDIO)


@needs_ffmpeg
def test_extract_audio_from_video(video, tmp_path):
    dst = str(tmp_path / "track.mp3")
    _run(video, dst, {"audio_codec": "libmp3lame", "audio_bitrate": "128k"}, F.AUDIO)


@needs_ffmpeg
def test_loudnorm_with_vorbis(audio, tmp_path):
    """回归：loudnorm 输出 192kHz 曾导致 libvorbis 初始化失败。"""
    dst = str(tmp_path / "norm.ogg")
    _run(audio, dst, {"audio_codec": "libvorbis", "normalize": True,
                      "loudness_target": -16}, F.AUDIO)


@needs_ffmpeg
def test_tempo_change(audio, tmp_path):
    dst = str(tmp_path / "fast.mp3")
    _run(audio, dst, {"audio_codec": "libmp3lame", "tempo": 1.5}, F.AUDIO)
    info = probe(dst)
    if info.duration:
        assert info.duration < 1.8


# ---------------------------- 图片 ----------------------------
@needs_pil
@pytest.mark.parametrize("ext", ["jpg", "png", "webp", "bmp", "tiff", "gif",
                                 "ico", "pdf", "tga", "ppm"])
def test_image_formats(picture, tmp_path, ext):
    dst = str(tmp_path / f"out.{ext}")
    _run(picture, dst, {"quality": 85}, F.IMAGE)


@needs_pil
def test_image_resize(picture, tmp_path):
    dst = str(tmp_path / "small.jpg")
    _run(picture, dst, {"width": 100, "height": 80, "keep_aspect": False}, F.IMAGE)
    with Image.open(dst) as im:
        assert im.size == (100, 80)


@needs_pil
def test_image_keeps_aspect(picture, tmp_path):
    dst = str(tmp_path / "fit.png")
    _run(picture, dst, {"width": 160, "height": 160, "keep_aspect": True}, F.IMAGE)
    with Image.open(dst) as im:
        assert max(im.size) == 160
        assert abs(im.size[0] / im.size[1] - 320 / 240) < 0.05


@needs_pil
def test_transparency_flattened_for_jpeg(picture, tmp_path):
    dst = str(tmp_path / "flat.jpg")
    _run(picture, dst, {"background": "#FF0000"}, F.IMAGE)
    with Image.open(dst) as im:
        assert im.mode == "RGB"


@needs_pil
def test_grayscale_and_rotate(picture, tmp_path):
    dst = str(tmp_path / "gray.png")
    _run(picture, dst, {"grayscale": True, "rotate": "90"}, F.IMAGE)
    with Image.open(dst) as im:
        assert im.size == (240, 320)


@needs_pil
def test_quality_affects_size(picture, tmp_path):
    lo = str(tmp_path / "lo.jpg")
    hi = str(tmp_path / "hi.jpg")
    _run(picture, lo, {"quality": 20}, F.IMAGE)
    _run(picture, hi, {"quality": 98}, F.IMAGE)
    assert os.path.getsize(lo) < os.path.getsize(hi)


# ---------------------------- 错误处理 ----------------------------
def test_missing_source_fails_gracefully(tmp_path):
    job = run_job(Job(src=str(tmp_path / "nope.mp4"),
                      dst=str(tmp_path / "o.mp4"), params={}, kind=F.VIDEO))
    assert job.status is Status.FAILED
    assert "不存在" in job.message


@needs_pil
def test_same_source_and_target_rejected(picture):
    job = run_job(Job(src=picture, dst=picture, params={}, kind=F.IMAGE))
    assert job.status is Status.FAILED


@needs_pil
def test_no_overwrite_skips(picture, tmp_path):
    dst = tmp_path / "exists.png"
    dst.write_bytes(b"placeholder")
    job = run_job(Job(src=picture, dst=str(dst),
                      params={"overwrite": False}, kind=F.IMAGE))
    assert job.status is Status.SKIPPED
    assert dst.read_bytes() == b"placeholder"


@needs_ffmpeg
def test_invalid_params_reported(video, tmp_path):
    job = run_job(Job(src=video, dst=str(tmp_path / "bad.mp4"),
                      params={"video_codec": "libx264",
                              "extra_args": "-invalid_flag_xyz 1"}, kind=F.VIDEO))
    assert job.status is Status.FAILED
    assert job.message
