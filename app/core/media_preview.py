"""媒体预览数据生成：音频波形、视频缩略图、图片缩略图。

所有函数同步阻塞，调用方负责放到后台线程；返回的数据尽量小，
避免在主线程大块解码。
"""
from __future__ import annotations

import io
import os
import struct
import subprocess
import tempfile
from typing import Sequence

from PIL import Image

from . import formats as F
from .ffprobe import CREATE_NO_WINDOW, ffmpeg_path, ffprobe_path, probe

# 音频波形目标采样点数（每个采样点是一个浮点振幅 [-1, 1]）
WAVEFORM_BUCKETS = 360


def detect_kind(path: str) -> str:
    return F.detect_kind(path)


def make_image_thumbnail(path: str, *, max_size: tuple[int, int] = (480, 320)) -> bytes:
    """生成图片缩略图（PNG 字节）。"""
    with Image.open(path) as im:
        im.thumbnail(max_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if im.mode in ("RGBA", "LA", "P"):
            im.save(buf, "PNG")
        else:
            im = im.convert("RGB")
            im.save(buf, "PNG")
        return buf.getvalue()


def extract_video_thumbnail(path: str, *, max_w: int = 480) -> bytes:
    """从视频中截取一帧（默认 10% 位置）作为缩略图。"""
    ff = ffmpeg_path()
    if not ff:
        raise RuntimeError("未安装 ffmpeg，无法生成视频缩略图")
    duration = 0.0
    try:
        info = probe(path)
        duration = info.duration
    except Exception:  # noqa: BLE001
        pass
    seek = max(0.1, duration * 0.1) if duration > 1 else 0.0
    fd, png_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        cmd = [ff, "-y", "-ss", f"{seek:.3f}", "-i", path,
               "-frames:v", "1", "-vf", f"scale={max_w}:-2", png_path]
        subprocess.run(cmd, check=True, capture_output=True,
                       creationflags=CREATE_NO_WINDOW, timeout=30)
        with open(png_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(png_path)
        except OSError:
            pass


def decode_audio_waveform(path: str, *, buckets: int = WAVEFORM_BUCKETS,
                          sample_rate: int = 8000) -> Sequence[float]:
    """把音频解码为 8 kHz 单声道 PCM，再分桶计算 RMS，得到归一化的波形数组。

    失败抛 RuntimeError；返回长度为 buckets 的 list。
    """
    ff = ffmpeg_path()
    if not ff:
        raise RuntimeError("未安装 ffmpeg，无法生成波形")
    cmd = [ff, "-hide_banner", "-nostdin", "-i", path,
           "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-acodec", "pcm_s16le",
           "pipe:1"]
    proc = subprocess.run(cmd, capture_output=True, timeout=120,
                          creationflags=CREATE_NO_WINDOW)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError("ffmpeg 解码失败："
                           + (proc.stderr.decode("utf-8", "replace").splitlines()[-1]
                              if proc.stderr else "空输出"))
    raw = proc.stdout
    n_samples = len(raw) // 2
    if n_samples == 0:
        raise RuntimeError("音频时长为 0")
    samples = struct.unpack(f"<{n_samples}h", raw[:n_samples * 2])
    bucket_size = max(1, n_samples // buckets)
    out: list[float] = []
    peak = 1.0
    for i in range(0, n_samples, bucket_size):
        block = samples[i:i + bucket_size]
        if not block:
            break
        # RMS（更能反映响度）
        rms = (sum(s * s for s in block) / len(block)) ** 0.5
        out.append(rms)
        if rms > peak:
            peak = rms
    if peak > 0:
        out = [v / peak for v in out]
    # 截断/补齐到 buckets
    if len(out) > buckets:
        out = out[:buckets]
    elif len(out) < buckets:
        out.extend([0.0] * (buckets - len(out)))
    return out


__all__ = [
    "WAVEFORM_BUCKETS",
    "detect_kind",
    "make_image_thumbnail",
    "extract_video_thumbnail",
    "decode_audio_waveform",
]