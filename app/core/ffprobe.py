"""ffmpeg / ffprobe 可执行文件定位与媒体信息探测。"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _bundle_dir() -> Path:
    """打包后 (PyInstaller) 的资源目录，开发环境下为项目根。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def _candidates(name: str) -> list[Path]:
    exe = f"{name}.exe" if os.name == "nt" else name
    base = _bundle_dir()
    out = [
        base / "bin" / exe,
        base / exe,
        Path(sys.executable).parent / "bin" / exe,
        Path(sys.executable).parent / exe,
    ]
    env = os.environ.get("MEDIAFORGE_FFMPEG_DIR")
    if env:
        out.insert(0, Path(env) / exe)
    return out


@lru_cache(maxsize=8)
def find_tool(name: str) -> str | None:
    """查找 ffmpeg/ffprobe：优先随程序分发的 bin/，其次 PATH。"""
    for p in _candidates(name):
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return shutil.which(name)


def ffmpeg_path() -> str | None:
    return find_tool("ffmpeg")


def ffprobe_path() -> str | None:
    return find_tool("ffprobe")


class FFmpegMissing(RuntimeError):
    """未找到 ffmpeg 可执行文件。"""


def require_ffmpeg() -> str:
    p = ffmpeg_path()
    if not p:
        raise FFmpegMissing(
            "未找到 ffmpeg。请安装 ffmpeg 并加入 PATH，"
            "或将 ffmpeg.exe 放到程序目录的 bin/ 子目录下。"
        )
    return p


@dataclass
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    bit_rate: int = 0
    pix_fmt: str = ""
    language: str = ""


@dataclass
class MediaInfo:
    path: str
    duration: float = 0.0
    size: int = 0
    bit_rate: int = 0
    format_name: str = ""
    streams: list[StreamInfo] = field(default_factory=list)
    tags: dict = field(default_factory=dict)

    @property
    def video(self) -> StreamInfo | None:
        return next((s for s in self.streams if s.codec_type == "video"), None)

    @property
    def audio(self) -> StreamInfo | None:
        return next((s for s in self.streams if s.codec_type == "audio"), None)

    @property
    def has_video(self) -> bool:
        return self.video is not None

    @property
    def has_audio(self) -> bool:
        return self.audio is not None


def _fraction(text: str) -> float:
    try:
        if "/" in text:
            a, b = text.split("/", 1)
            return float(a) / float(b) if float(b) else 0.0
        return float(text)
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe(path: str) -> MediaInfo:
    """用 ffprobe 读取媒体信息；失败时返回仅含路径与大小的对象。"""
    info = MediaInfo(path=path)
    try:
        info.size = os.path.getsize(path)
    except OSError:
        pass

    tool = ffprobe_path()
    if not tool:
        return _probe_with_ffmpeg(info)

    cmd = [tool, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    try:
        raw = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                             creationflags=CREATE_NO_WINDOW).stdout
        data = json.loads(raw or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return _probe_with_ffmpeg(info)

    fmt = data.get("format", {})
    info.duration = float(fmt.get("duration") or 0)
    info.bit_rate = int(float(fmt.get("bit_rate") or 0))
    info.format_name = fmt.get("format_name", "")
    info.tags = fmt.get("tags", {}) or {}

    for s in data.get("streams", []):
        si = StreamInfo(
            index=int(s.get("index", 0)),
            codec_type=s.get("codec_type", ""),
            codec_name=s.get("codec_name", ""),
            width=int(s.get("width") or 0),
            height=int(s.get("height") or 0),
            fps=_fraction(s.get("avg_frame_rate") or s.get("r_frame_rate") or "0"),
            sample_rate=int(s.get("sample_rate") or 0),
            channels=int(s.get("channels") or 0),
            bit_rate=int(float(s.get("bit_rate") or 0)),
            pix_fmt=s.get("pix_fmt", ""),
            language=(s.get("tags", {}) or {}).get("language", ""),
        )
        info.streams.append(si)
    return info


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")
_STREAM_RE = re.compile(r"Stream #\d+:(\d+)(?:\[[^\]]*\])?(?:\(([^)]*)\))?:\s*(\w+):\s*([\w-]+)")
_RES_RE = re.compile(r"(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"([\d.]+) fps")
_SR_RE = re.compile(r"(\d+) Hz")


def _probe_with_ffmpeg(info: MediaInfo) -> MediaInfo:
    """没有 ffprobe 时，解析 `ffmpeg -i` 的 stderr 兜底获取信息。"""
    tool = ffmpeg_path()
    if not tool:
        return info
    try:
        res = subprocess.run([tool, "-hide_banner", "-i", info.path],
                             capture_output=True, text=True, timeout=60,
                             creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return info
    text = (res.stderr or "") + (res.stdout or "")

    m = _DUR_RE.search(text)
    if m:
        info.duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("Stream #"):
            continue
        sm = _STREAM_RE.search(line)
        if not sm:
            continue
        kind = sm.group(3).lower()
        si = StreamInfo(index=int(sm.group(1)), codec_type=kind,
                        codec_name=sm.group(4), language=sm.group(2) or "")
        if kind == "video":
            r = _RES_RE.search(line)
            if r:
                si.width, si.height = int(r.group(1)), int(r.group(2))
            f = _FPS_RE.search(line)
            if f:
                si.fps = float(f.group(1))
        elif kind == "audio":
            s = _SR_RE.search(line)
            if s:
                si.sample_rate = int(s.group(1))
            if "stereo" in line:
                si.channels = 2
            elif "mono" in line:
                si.channels = 1
            elif "5.1" in line:
                si.channels = 6
        info.streams.append(si)
    return info


@lru_cache(maxsize=1)
def available_encoders() -> frozenset[str]:
    """查询当前 ffmpeg 实际支持的编码器名称集合。"""
    tool = ffmpeg_path()
    if not tool:
        return frozenset()
    try:
        out = subprocess.run([tool, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=30,
                             creationflags=CREATE_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS":
            names.add(parts[1])
    return frozenset(names)


@lru_cache(maxsize=1)
def ffmpeg_version() -> str:
    tool = ffmpeg_path()
    if not tool:
        return "未安装"
    try:
        out = subprocess.run([tool, "-version"], capture_output=True, text=True,
                             timeout=20, creationflags=CREATE_NO_WINDOW).stdout
        return out.splitlines()[0] if out else "未知"
    except (OSError, subprocess.SubprocessError):
        return "未知"
