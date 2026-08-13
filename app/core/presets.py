"""内置预设与用户预设的读写。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import formats as F


@dataclass
class Preset:
    name: str
    kind: str
    ext: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    builtin: bool = False


def _v(ext: str, vc: str, ac: str, **kw: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"video_codec": vc, "audio_codec": ac}
    d.update(kw)
    return d


BUILTIN: tuple[Preset, ...] = (
    Preset("MP4 通用高质量", F.VIDEO, "mp4",
           _v("mp4", "libx264", "aac", rate_mode="crf", crf=20, preset="slow",
              pix_fmt="yuv420p", audio_bitrate="192k", faststart=True),
           "H.264 + AAC，兼容性最好", True),
    Preset("MP4 压缩省空间", F.VIDEO, "mp4",
           _v("mp4", "libx265", "aac", rate_mode="crf", crf=28, preset="medium",
              audio_bitrate="128k"),
           "H.265，体积约为 H.264 的一半", True),
    Preset("1080p 网络上传", F.VIDEO, "mp4",
           _v("mp4", "libx264", "aac", rate_mode="vbr", bitrate="8000k",
              maxrate="10000k", bufsize="16000k", width=1920, height=1080,
              preset="medium", audio_bitrate="192k"),
           "YouTube/B 站推荐参数", True),
    Preset("720p 手机友好", F.VIDEO, "mp4",
           _v("mp4", "libx264", "aac", rate_mode="crf", crf=24, width=1280,
              height=720, preset="fast", profile="main", audio_bitrate="128k"),
           "体积小，移动端流畅播放", True),
    Preset("4K HEVC 10bit", F.VIDEO, "mkv",
           _v("mkv", "libx265", "libopus", rate_mode="crf", crf=22,
              preset="slow", pix_fmt="yuv420p10le", width=3840, height=2160),
           "高画质归档", True),
    Preset("WebM (VP9)", F.VIDEO, "webm",
           _v("webm", "libvpx-vp9", "libopus", rate_mode="crf", crf=31,
              cpu_used=2, audio_bitrate="128k"),
           "网页嵌入，开源格式", True),
    Preset("AV1 高压缩", F.VIDEO, "mkv",
           _v("mkv", "libsvtav1", "libopus", rate_mode="crf", crf=32, preset=7),
           "最新一代编码，体积最小", True),
    Preset("GIF 动图", F.VIDEO, "gif",
           _v("gif", "gif", "", fps="12", width=480, gif_palette=True,
              gif_dither="sierra2_4a", gif_max_colors=256),
           "调色板优化，画质更好", True),
    Preset("WebP 动图", F.VIDEO, "webp",
           _v("webp", "libwebp", "", fps="12", width=480, quality=75,
              compression_level=4, gif_loop=0),
           "体积比 GIF 更小，兼容现代浏览器", True),
    Preset("APNG 动图", F.VIDEO, "apng",
           _v("apng", "apng", "", fps="12", width=480, gif_loop=0),
           "无损动图，支持透明", True),
    Preset("Live Photo 动态照片", F.VIDEO, "mp.jpg",
           _v("mp.jpg", "libx264", "aac", crf=23, width=1080, audio_bitrate="128k"),
           "视频转实况照片，兼容 Google Photos / 安卓相册", True),
    Preset("无损归档 (FFV1/MKV)", F.VIDEO, "mkv",
           _v("mkv", "libx264", "flac", rate_mode="lossless", preset="veryslow"),
           "画质无损，体积很大", True),
    Preset("仅重封装（极快）", F.VIDEO, "mp4",
           _v("mp4", "copy", "copy"),
           "不重新编码，仅换容器，秒级完成", True),
    Preset("NVIDIA 显卡加速", F.VIDEO, "mp4",
           _v("mp4", "h264_nvenc", "aac", rate_mode="cq", crf=23,
              preset="p5", hwaccel="cuda"),
           "需 NVIDIA 显卡，速度极快", True),

    Preset("MP3 320k 高音质", F.AUDIO, "mp3",
           {"audio_codec": "libmp3lame", "audio_mode": "cbr",
            "audio_bitrate": "320k", "sample_rate": "44100"},
           "最高质量 MP3", True),
    Preset("MP3 V0 (VBR)", F.AUDIO, "mp3",
           {"audio_codec": "libmp3lame", "audio_mode": "vbr", "mp3_vbr_quality": 0},
           "体积与音质平衡最佳", True),
    Preset("AAC 256k", F.AUDIO, "m4a",
           {"audio_codec": "aac", "audio_bitrate": "256k", "sample_rate": "48000"},
           "苹果生态首选", True),
    Preset("FLAC 无损", F.AUDIO, "flac",
           {"audio_codec": "flac", "compression_level": 8},
           "无损压缩，适合收藏", True),
    Preset("WAV 44.1k 16bit", F.AUDIO, "wav",
           {"audio_codec": "pcm_s16le", "sample_rate": "44100", "channels": "2"},
           "CD 标准，无压缩", True),
    Preset("Opus 语音 64k", F.AUDIO, "opus",
           {"audio_codec": "libopus", "audio_bitrate": "64k",
            "opus_application": "voip", "channels": "1"},
           "播客/语音，极省空间", True),
    Preset("播客响度标准化", F.AUDIO, "mp3",
           {"audio_codec": "libmp3lame", "audio_bitrate": "128k",
            "normalize": True, "loudness_target": -16, "channels": "1"},
           "-16 LUFS，符合播客规范", True),
    Preset("提取音轨（不转码）", F.AUDIO, "mka",
           {"audio_codec": "copy"},
           "从视频里原样抽出音频", True),

    Preset("JPEG 高质量", F.IMAGE, "jpg",
           {"quality": 92, "optimize": True, "progressive": True,
            "subsampling": "4:4:4"},
           "照片首选", True),
    Preset("JPEG 网页压缩", F.IMAGE, "jpg",
           {"quality": 78, "optimize": True, "progressive": True,
            "width": 1920, "strip_metadata": True},
           "体积小，适合网页", True),
    Preset("PNG 无损压缩", F.IMAGE, "png",
           {"png_compress_level": 9, "optimize": True},
           "截图、透明图", True),
    Preset("WebP 有损", F.IMAGE, "webp",
           {"quality": 80, "webp_method": 6},
           "比 JPEG 小 30%", True),
    Preset("WebP 无损", F.IMAGE, "webp",
           {"lossless": True, "webp_method": 6}, "替代 PNG", True),
    Preset("AVIF 极致压缩", F.IMAGE, "avif",
           {"quality": 60, "avif_speed": 4}, "新一代图片格式", True),
    Preset("缩略图 400px", F.IMAGE, "jpg",
           {"width": 400, "height": 400, "keep_aspect": True,
            "quality": 85, "strip_metadata": True}, "批量生成缩略图", True),
    Preset("Windows 图标 ICO", F.IMAGE, "ico",
           {"ico_sizes": "16,32,48,64,128,256"}, "多尺寸图标", True),
    Preset("TIFF 印刷 300DPI", F.IMAGE, "tiff",
           {"tiff_compression": "tiff_lzw", "dpi": 300, "color_mode": "CMYK"},
           "送印用", True),
)


def config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "MediaForge"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _user_file() -> Path:
    return config_dir() / "presets.json"


def load_user_presets() -> list[Preset]:
    path = _user_file()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for item in data:
        try:
            out.append(Preset(item["name"], item["kind"], item["ext"],
                              item.get("params", {}), item.get("description", "")))
        except KeyError:
            continue
    return out


def save_user_presets(presets: list[Preset]) -> None:
    data = [{"name": p.name, "kind": p.kind, "ext": p.ext,
             "params": p.params, "description": p.description}
            for p in presets if not p.builtin]
    _user_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def _persist(presets: list[Preset]) -> None:
    """把列表里非内置的部分写入 presets.json。"""
    save_user_presets(presets)


def add_user_preset(preset: Preset) -> Preset:
    """新增用户预设；同名（含与内置冲突）会被拒绝。"""
    if preset.builtin:
        raise ValueError("不能添加内置预设")
    if not preset.name or not preset.name.strip():
        raise ValueError("预设名称不能为空")
    presets = load_user_presets()
    if any(p.name == preset.name for p in presets):
        raise ValueError(f"已存在同名预设：{preset.name}")
    if any(p.name == preset.name for p in BUILTIN):
        raise ValueError(f"与内置预设同名：{preset.name}")
    presets.append(preset)
    _persist(presets)
    return preset


def rename_user_preset(old_name: str, new_name: str) -> bool:
    """重命名用户预设；返回是否成功。"""
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("新名称不能为空")
    presets = load_user_presets()
    target = next((p for p in presets if p.name == old_name), None)
    if target is None:
        return False
    if old_name == new_name:
        return True
    if any(p.name == new_name for p in presets):
        raise ValueError(f"已存在同名预设：{new_name}")
    if any(p.name == new_name for p in BUILTIN):
        raise ValueError(f"与内置预设同名：{new_name}")
    target.name = new_name
    _persist(presets)
    return True


def delete_user_preset(name: str) -> bool:
    presets = load_user_presets()
    new_list = [p for p in presets if p.name != name]
    if len(new_list) == len(presets):
        return False
    _persist(new_list)
    return True


def overwrite_user_preset(name: str, preset: Preset) -> bool:
    """用同名预设覆盖已有用户预设；不存在则新建。"""
    preset.name = name
    preset.builtin = False
    presets = load_user_presets()
    for i, p in enumerate(presets):
        if p.name == name:
            presets[i] = preset
            _persist(presets)
            return True
    presets.append(preset)
    _persist(presets)
    return True


def export_presets(presets: list[Preset], path: str) -> None:
    """把若干预设导出为 JSON 文件（可分享给其它用户）。"""
    data = [{"name": p.name, "kind": p.kind, "ext": p.ext,
             "params": p.params, "description": p.description,
             "builtin": p.builtin} for p in presets]
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def import_presets(path: str) -> tuple[int, list[str]]:
    """从 JSON 文件导入预设；返回 (新增数量, 跳过的预设名列表)。

    跳过条件：与已有内置或用户预设同名；JSON 损坏；项字段不全。
    """
    try:
        data = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"无法解析文件：{exc}") from exc
    if not isinstance(data, list):
        raise ValueError("文件格式错误：根节点应为预设列表")

    existing = {p.name for p in BUILTIN} | {p.name for p in load_user_presets()}
    accepted: list[Preset] = []
    skipped: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            skipped.append(str(item))
            continue
        try:
            name = item["name"]
            kind = item["kind"]
            ext = item["ext"]
            params = item.get("params", {})
            desc = item.get("description", "")
        except KeyError:
            skipped.append(str(item.get("name", "?")))
            continue
        if name in existing:
            skipped.append(name)
            continue
        accepted.append(Preset(name=name, kind=kind, ext=ext,
                               params=params, description=desc))
        existing.add(name)

    if accepted:
        presets = load_user_presets() + accepted
        _persist(presets)
    return len(accepted), skipped


def all_presets(kind: str | None = None) -> list[Preset]:
    items = list(BUILTIN) + load_user_presets()
    if kind:
        items = [p for p in items if p.kind == kind]
    return items


def find_preset(name: str) -> Preset | None:
    return next((p for p in all_presets() if p.name == name), None)
