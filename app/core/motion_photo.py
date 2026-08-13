"""视频 → Live Photo（Google Motion Photo / 实况照片）转换。

生成单文件 Motion Photo：一个合法 JPEG（封面帧）在文件头，尾部拼接一个
MP4 微视频，并在 JPEG 的 APP1/XMP 段写入 GCamera 元数据（MotionPhoto 标志、
Container:Directory 中 video/mp4 的字节长度、代表帧时间戳）。该格式被
Google Photos、安卓相册、小红书等识别为「动态照片 / Live Photo」。

字节布局：
    JPEG(SOI .. EOI) + MP4(ftyp/moov/mdat)
    XMP 里的 Item:Length = MP4 的字节数。
"""
from __future__ import annotations

import os
import struct
import subprocess
import tempfile
from typing import Any

from . import formats as F
from .ffprobe import CREATE_NO_WINDOW, probe, require_ffmpeg

XMP_IDENT = b"http://ns.adobe.com/xap/1.0/\x00"


class Canceled(Exception):
    """Motion Photo 转换被用户取消。"""


def is_motion_photo_output(path: str) -> bool:
    return F.is_motion_photo(path)


def is_motion_photo_input(path: str) -> bool:
    return F.is_motion_photo(path)


# --------------------------------------------------------------------------
# ffmpeg 子进程封装
# --------------------------------------------------------------------------
def _run_ffmpeg(cmd: list[str], cancel: Any = None) -> None:
    """运行一次 ffmpeg；失败抛 RuntimeError；cancel 置位抛 Canceled。"""
    if cancel is not None and cancel.is_set():
        raise Canceled
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )
    tail: list[str] = []
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel is not None and cancel.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise Canceled
            line = line.rstrip()
            if line:
                tail.append(line)
                del tail[:-40]
    finally:
        proc.stdout and proc.stdout.close()
        code = proc.wait()

    if cancel is not None and cancel.is_set():
        raise Canceled
    if code != 0:
        raise RuntimeError("\n".join(tail[-12:]) or f"ffmpeg 退出码 {code}")


def _extract_cover(src: str, dst_jpg: str, ts_us: int, cancel: Any = None) -> None:
    ff = require_ffmpeg()
    ts = f"{ts_us / 1_000_000:.3f}"
    _run_ffmpeg([ff, "-y", "-hide_banner", "-loglevel", "error",
                 "-i", src, "-ss", ts, "-vframes", "1", "-q:v", "2", dst_jpg], cancel)


def _encode_mp4(src: str, dst_mp4: str, params: dict[str, Any], cancel: Any = None) -> None:
    ff = require_ffmpeg()
    crf = _num(params, "crf", 23)
    audio_bitrate = str(params.get("audio_bitrate") or "128k")
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-i", src,
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", audio_bitrate,
           "-movflags", "+faststart"]
    w, h = _int(params, "width"), _int(params, "height")
    if w or h:
        sw = str(w) if w else "-2"
        sh = str(h) if h else "-2"
        cmd += ["-vf", f"scale={sw}:{sh}"]
    cmd.append(dst_mp4)
    _run_ffmpeg(cmd, cancel)


def _num(params: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def _int(params: dict[str, Any], key: str) -> int:
    try:
        return int(float(params.get(key, 0)))
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------
# XMP 生成与 JPEG 注入
# --------------------------------------------------------------------------
def build_xmp(mp4_size: int, presentation_timestamp_us: int) -> str:
    return (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        ' xmlns:Camera="http://ns.google.com/photos/1.0/camera/"'
        ' xmlns:Container="http://ns.google.com/photos/1.0/container/"'
        ' xmlns:Item="http://ns.google.com/photos/1.0/container/item/">'
        '<rdf:Description'
        ' Camera:MotionPhoto="1"'
        ' Camera:MotionPhotoVersion="1"'
        f' Camera:MotionPhotoPresentationTimestampUs="{presentation_timestamp_us}">'
        '<Container:Directory><rdf:Seq>'
        '<rdf:li rdf:parseType="Resource"><Container:Item'
        ' Item:Mime="image/jpeg" Item:Semantic="Primary"/></rdf:li>'
        '<rdf:li rdf:parseType="Resource"><Container:Item'
        ' Item:Mime="video/mp4" Item:Semantic="MotionPhoto"'
        f' Item:Length="{mp4_size}"/></rdf:li>'
        '</rdf:Seq></Container:Directory>'
        '</rdf:Description>'
        '</rdf:RDF></x:xmpmeta>'
    )


def make_xmp_segment(xmp_str: str) -> bytes:
    """把 XMP 字符串封装成 JPEG APP1 段（FFE1 + 长度 + 标识符 + XMP）。"""
    xmp_bytes = xmp_str.encode("utf-8")
    app1_data = XMP_IDENT + xmp_bytes
    length = len(app1_data) + 2
    return b"\xff\xe1" + struct.pack(">H", length) + app1_data


def inject_xmp(jpeg_data: bytes, xmp_segment: bytes) -> bytes:
    """在 SOI（FFD8）之后插入 XMP APP1 段。"""
    if jpeg_data[:2] != b"\xff\xd8":
        raise ValueError("不是有效的 JPEG 文件")
    return jpeg_data[:2] + xmp_segment + jpeg_data[2:]


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------
def convert(src: str, dst: str, params: dict[str, Any],
            cancel: Any = None, on_progress: Any = None) -> str:
    """把视频转成 Google Motion Photo，返回输出路径。

    on_progress: 可选回调 on_progress(0.0~1.0)。
    """
    if not os.path.isfile(src):
        raise FileNotFoundError(f"源文件不存在：{src}")
    if cancel is not None and cancel.is_set():
        raise Canceled

    info = probe(src)
    duration = info.duration or 0.0
    ts_us = _int(params, "presentation_timestamp_us")
    if ts_us <= 0:
        ts_us = 1_000_000
    # 封面时间点不超过视频末尾
    if duration > 0 and ts_us / 1_000_000 >= duration:
        ts_us = max(0, int((duration - 0.05) * 1_000_000))

    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        jpg_path = os.path.join(tmp, "cover.jpg")
        mp4_path = os.path.join(tmp, "video.mp4")

        _extract_cover(src, jpg_path, ts_us, cancel)
        if on_progress:
            on_progress(0.25)

        _encode_mp4(src, mp4_path, params, cancel)
        if on_progress:
            on_progress(0.85)

        with open(jpg_path, "rb") as f:
            jpeg_data = f.read()
        with open(mp4_path, "rb") as f:
            mp4_data = f.read()

        xmp = make_xmp_segment(build_xmp(len(mp4_data), ts_us))
        jpeg_with_xmp = inject_xmp(jpeg_data, xmp)

        with open(dst, "wb") as out:
            out.write(jpeg_with_xmp)
            out.write(mp4_data)

    if on_progress:
        on_progress(1.0)
    return dst


def extract_microvideo(src: str, cancel: Any = None) -> str:
    """从 Motion Photo 里抽出内嵌 MP4 到临时文件，返回路径（供转 GIF/WebP 等）。"""
    if cancel is not None and cancel.is_set():
        raise Canceled
    with open(src, "rb") as f:
        data = f.read()
    # 从尾部定位 ftyp 盒（MP4 开头），向前搜索最近的一个即可
    pos = data.rfind(b"ftyp")
    if pos <= 0 or pos + 12 > len(data):
        # 回退：以 "ftyp" 首次出现位置作为 MP4 起点
        pos = data.find(b"ftyp")
    if pos <= 0:
        raise ValueError("未能从 Motion Photo 中找到内嵌视频")
    # ftyp 盒前应有 4 字节 box size
    start = pos - 4
    if start < 0:
        start = 0
    fd, tmp = tempfile.mkstemp(suffix=".mp4", prefix="mediaforge_mv_")
    with os.fdopen(fd, "wb") as out:
        out.write(data[start:])
    return tmp
