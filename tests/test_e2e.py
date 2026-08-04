"""端到端测试：真实转换。

- 图片转换使用 Pillow（无需 ffmpeg）；
- 音视频转换在缺少 ffmpeg 时自动跳过。
"""
from __future__ import annotations

import os
import subprocess
import threading

import pytest
from PIL import Image

from app.core import formats as F
from app.core import image_engine
from app.core.converter import ConversionQueue, Job, Status
from app.core.ffprobe import CREATE_NO_WINDOW, ffmpeg_path


def _make_png(tmp_path, size=(64, 48), color=(200, 30, 30)) -> str:
    p = tmp_path / "in.png"
    Image.new("RGB", size, color).save(p)
    return str(p)


# ---------------- 图片引擎 ----------------
def test_image_png_to_jpg(tmp_path):
    src = _make_png(tmp_path)
    dst = str(tmp_path / "out.jpg")
    image_engine.convert_image(src, dst, {"quality": 80, "optimize": True})
    assert os.path.isfile(dst)
    with Image.open(dst) as im:
        assert im.format == "JPEG"


def test_image_resize_keep_aspect(tmp_path):
    src = _make_png(tmp_path, size=(64, 48))
    dst = str(tmp_path / "out.png")
    image_engine.convert_image(src, dst, {"width": 32, "height": 32, "keep_aspect": True})
    with Image.open(dst) as im:
        # contain：等比缩放到 32 以内，宽 32 高 24
        assert im.size[0] == 32


def test_image_flatten_transparent_to_jpg(tmp_path):
    src = str(tmp_path / "t.png")
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(src)
    dst = str(tmp_path / "t.jpg")
    image_engine.convert_image(src, dst, {"background": "#FFFFFF"})
    with Image.open(dst) as im:
        assert im.mode == "RGB"


def test_image_cancel_raises(tmp_path):
    src = _make_png(tmp_path)
    dst = str(tmp_path / "out.jpg")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(image_engine.CanceledError):
        image_engine.convert_image(src, dst, {}, cancel)


# ---------------- 队列 ----------------
def test_queue_single_image_job(tmp_path):
    src = _make_png(tmp_path)
    dst = str(tmp_path / "out.jpg")
    queue = ConversionQueue(workers=1)
    queue.add(Job(src=src, dst=dst, params={"quality": 80}, kind=F.IMAGE))
    queue.start()
    queue.wait()
    assert queue.jobs[0].status is Status.DONE
    assert os.path.isfile(dst)


def test_queue_cancel_pending(tmp_path):
    src = _make_png(tmp_path)
    queue = ConversionQueue(workers=1)
    jobs = []
    for i in range(4):
        jobs.append(Job(src=src, dst=str(tmp_path / f"out{i}.jpg"),
                        params={}, kind=F.IMAGE))
        queue.add(jobs[-1])
    queue.start()
    queue.cancel()
    queue.wait()
    for j in jobs:
        assert j.status in (Status.DONE, Status.CANCELED)


# ---------------- 音视频（需要 ffmpeg） ----------------
needs_ffmpeg = pytest.mark.skipif(ffmpeg_path() is None, reason="未安装 ffmpeg")


def _pick_video_encoder() -> str:
    """选择当前 ffmpeg 实际支持的 H.264 类编码器（不同构建差异很大）。"""
    from app.core.ffprobe import available_encoders
    encs = available_encoders()
    for enc in ("libx264", "libopenh264", "libx265", "mpeg4", "flv"):
        if enc in encs:
            return enc
    return "mpeg4"


def _make_test_video(tmp_path) -> str:
    src = str(tmp_path / "sample.mp4")
    subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=duration=0.6:size=160x120:rate=15",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=0.6",
         "-c:v", _pick_video_encoder(), "-preset", "ultrafast", "-c:a", "aac",
         "-shortest", src],
        check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
    return src


@needs_ffmpeg
def test_video_remux_copy(tmp_path):
    from app.core.converter import run_job

    src = _make_test_video(tmp_path)
    dst = str(tmp_path / "sample.mkv")
    job = run_job(Job(src=src, dst=dst, kind=F.VIDEO,
                      params={"video_codec": "copy", "audio_codec": "copy"}))
    assert job.status is Status.DONE
    assert os.path.getsize(dst) > 0


@needs_ffmpeg
def test_video_extract_audio(tmp_path):
    from app.core.converter import run_job

    src = _make_test_video(tmp_path)
    dst = str(tmp_path / "audio.m4a")
    job = run_job(Job(src=src, dst=dst, kind=F.AUDIO,
                      params={"audio_codec": "aac"}))
    assert job.status is Status.DONE
    assert os.path.getsize(dst) > 0
