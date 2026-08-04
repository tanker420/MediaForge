"""把参数字典翻译成 ffmpeg 命令行。"""
from __future__ import annotations

import shlex
from typing import Any

from . import formats as F
from .ffprobe import MediaInfo, require_ffmpeg


def _s(params: dict[str, Any], key: str, default: str = "") -> str:
    v = params.get(key, default)
    return "" if v is None else str(v).strip()


def _f(params: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default


def _i(params: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(float(params.get(key, default)))
    except (TypeError, ValueError):
        return default


def _b(params: dict[str, Any], key: str, default: bool = False) -> bool:
    v = params.get(key, default)
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes", "on")
    return bool(v)


# --------------------------------------------------------------------------
# 滤镜链
# --------------------------------------------------------------------------
def _escape_filter_path(p: str) -> str:
    """转义 filtergraph 中的路径特殊字符。

    字幕文件路径可能包含 ``: ' [ ] , ;`` 等字符（如 ``C:\\videos\\[1080p] 片.srt``），
    这些在 filtergraph 里都有特殊含义，必须转义，否则 subtitles 滤镜解析失败。
    """
    return (p.replace("\\", "/")
             .replace(":", r"\:")
             .replace("'", r"\'")
             .replace("[", r"\[")
             .replace("]", r"\]")
             .replace(",", r"\,")
             .replace(";", r"\;"))


def build_video_filters(params: dict[str, Any]) -> list[str]:
    chain: list[str] = []

    if _b(params, "deinterlace"):
        chain.append("yadif=mode=0:parity=-1:deint=0")

    crop = _s(params, "crop")
    if crop:
        chain.append(f"crop={crop}")

    w, h = _i(params, "width"), _i(params, "height")
    if w or h:
        sw = str(w) if w else "-2"
        sh = str(h) if h else "-2"
        if _b(params, "keep_aspect", True) and w and h:
            # 等比缩放后补边，保证不变形
            flags = _s(params, "scale_flags", "bicubic") or "bicubic"
            chain.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags={flags}")
            chain.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")
        else:
            flags = _s(params, "scale_flags", "bicubic") or "bicubic"
            chain.append(f"scale={sw}:{sh}:flags={flags}")

    pad = _s(params, "pad")
    if pad:
        chain.append(f"pad={pad}")

    rotate = _s(params, "rotate", "0")
    if rotate == "90":
        chain.append("transpose=1")
    elif rotate == "180":
        chain.append("transpose=1,transpose=1")
    elif rotate == "270":
        chain.append("transpose=2")

    if _b(params, "hflip"):
        chain.append("hflip")
    if _b(params, "vflip"):
        chain.append("vflip")

    denoise = _s(params, "denoise")
    if denoise:
        chain.append({"light": "hqdn3d=2:1:2:3",
                      "medium": "hqdn3d=4:3:6:4.5",
                      "strong": "hqdn3d=8:6:12:9"}.get(denoise, ""))
    if _b(params, "sharpen"):
        chain.append("unsharp=5:5:0.8:3:3:0.4")

    eq_bits = []
    for key, name, neutral in (("brightness", "brightness", 0.0),
                               ("contrast", "contrast", 1.0),
                               ("saturation", "saturation", 1.0),
                               ("gamma", "gamma", 1.0)):
        val = _f(params, key, neutral)
        if abs(val - neutral) > 1e-6:
            eq_bits.append(f"{name}={val:g}")
    if eq_bits:
        chain.append("eq=" + ":".join(eq_bits))

    fps = _s(params, "fps")
    if fps:
        chain.append(f"fps={fps}")

    if params.get("subtitle_mode") == "burn":
        sub = _s(params, "subtitle_file")
        if sub:
            esc = _escape_filter_path(sub)
            chain.append(f"subtitles='{esc}'")

    custom = _s(params, "video_filter")
    if custom:
        chain.append(custom)

    return [c for c in chain if c]


def build_audio_filters(params: dict[str, Any]) -> list[str]:
    chain: list[str] = []

    vol = _f(params, "volume", 0.0)
    if abs(vol) > 1e-6:
        chain.append(f"volume={vol:g}dB")

    if _b(params, "normalize"):
        target = _f(params, "loudness_target", -16)
        chain.append(f"loudnorm=I={target:g}:TP=-1.5:LRA=11")
        # loudnorm 内部按 192kHz 处理，必须重采样回目标采样率，
        # 否则 libvorbis 等只支持常规采样率的编码器会初始化失败。
        back = _s(params, "sample_rate") or str(_i(params, "_sample_rate", 0) or 48000)
        chain.append(f"aresample={back}")

    tempo = _f(params, "tempo", 1.0)
    if abs(tempo - 1.0) > 1e-6:
        # atempo 单次仅支持 0.5~2.0，超范围时串联
        remaining = tempo
        while remaining > 2.0:
            chain.append("atempo=2.0")
            remaining /= 2.0
        while remaining < 0.5:
            chain.append("atempo=0.5")
            remaining /= 0.5
        chain.append(f"atempo={remaining:g}")

    base_sr = _i(params, "_sample_rate", 0) or 48000
    semis = _f(params, "pitch_semitones", 0)
    if abs(semis) > 1e-6:
        ratio = 2 ** (semis / 12.0)
        chain.append(f"asetrate={base_sr}*{ratio:g},aresample={base_sr},atempo={1/ratio:g}")

    fi = _f(params, "audio_fade_in", 0)
    if fi > 0:
        chain.append(f"afade=t=in:st=0:d={fi:g}")
    fo = _f(params, "audio_fade_out", 0)
    if fo > 0 and params.get("_duration"):
        start = max(0.0, float(params["_duration"]) - fo)
        chain.append(f"afade=t=out:st={start:g}:d={fo:g}")

    sr = _s(params, "sample_rate")
    if sr:
        chain.append(f"aresample={sr}")

    custom = _s(params, "audio_filter")
    if custom:
        chain.append(custom)

    return [c for c in chain if c]


# --------------------------------------------------------------------------
# 编码器参数
# --------------------------------------------------------------------------
_QSCALE_CODECS = {"mpeg4", "libxvid", "mpeg2video", "mpeg1video", "libtheora",
                  "wmv2", "msmpeg4v3", "h263", "flv"}


def _video_encoder_args(enc: str, params: dict[str, Any], pass_no: int = 0) -> list[str]:
    args: list[str] = ["-c:v", enc]
    if enc == "copy":
        return args

    mode = _s(params, "rate_mode", "crf") or "crf"
    crf = _f(params, "crf", 23)
    bitrate = _s(params, "bitrate")
    if pass_no and bitrate:
        # 两遍编码必须使用目标码率而非恒定质量
        mode = "vbr" if mode in ("crf", "cq", "lossless") else mode

    if enc in ("libx264", "libx265"):
        if mode == "lossless":
            args += ["-crf", "0"] if enc == "libx264" else ["-x265-params", "lossless=1"]
        elif mode in ("cbr", "vbr") and bitrate:
            args += ["-b:v", bitrate]
            if mode == "cbr":
                args += ["-maxrate", bitrate, "-bufsize",
                         _s(params, "bufsize") or _double_rate(bitrate), "-nal-hrd", "cbr"]
        else:
            args += ["-crf", f"{crf:g}"]
        preset = _s(params, "preset")
        if preset:
            args += ["-preset", preset]
        tune = _s(params, "tune")
        if tune:
            args += ["-tune", tune]
        profile = _s(params, "profile")
        if profile:
            args += ["-profile:v", profile]
        level = _s(params, "level")
        if level:
            args += ["-level", level]
        bframes = _i(params, "bframes", -1)
        if bframes >= 0:
            args += ["-bf", str(bframes)]
        refs = _i(params, "refs", 0)
        if refs > 0:
            args += ["-refs", str(refs)]
        extra = _s(params, "x264_params") if enc == "libx264" else _s(params, "x265_params")
        if extra:
            args += [f"-{'x264' if enc == 'libx264' else 'x265'}-params", extra]

    elif enc == "libsvtav1":
        if mode in ("cbr", "vbr") and bitrate:
            args += ["-b:v", bitrate]
        else:
            args += ["-crf", f"{crf:g}"]
        args += ["-preset", str(_i(params, "preset", 8))]
        sp = _s(params, "svtav1_params")
        if sp:
            args += ["-svtav1-params", sp]

    elif enc == "libaom-av1":
        if mode == "lossless":
            args += ["-lossless", "1"]
        elif mode in ("cbr", "vbr") and bitrate:
            args += ["-b:v", bitrate]
        else:
            args += ["-crf", f"{crf:g}", "-b:v", "0"]
        args += ["-cpu-used", str(_i(params, "cpu_used", 4))]
        if _b(params, "row_mt", True):
            args += ["-row-mt", "1"]
        tiles = _s(params, "tiles")
        if tiles:
            args += ["-tiles", tiles]

    elif enc in ("libvpx-vp9", "libvpx"):
        if mode == "lossless" and enc == "libvpx-vp9":
            args += ["-lossless", "1"]
        elif mode in ("cbr", "vbr") and bitrate:
            args += ["-b:v", bitrate]
        else:
            args += ["-crf", f"{crf:g}", "-b:v", "0"]
        args += ["-cpu-used", str(_i(params, "cpu_used", 1))]
        if _b(params, "row_mt", True) and enc == "libvpx-vp9":
            args += ["-row-mt", "1"]
        dl = _s(params, "deadline")
        if dl:
            args += ["-deadline", dl]

    elif enc.endswith(("_nvenc", "_qsv", "_amf")):
        preset = _s(params, "preset")
        if enc.endswith("_nvenc"):
            if mode == "cq":
                args += ["-rc", "vbr", "-cq", f"{crf:g}", "-b:v", bitrate or "0"]
            elif mode == "cbr":
                args += ["-rc", "cbr", "-b:v", bitrate or "6000k"]
            else:
                args += ["-rc", "vbr", "-b:v", bitrate or "6000k"]
            if preset:
                args += ["-preset", preset]
        elif enc.endswith("_qsv"):
            if mode == "cq":
                args += ["-global_quality", f"{crf:g}"]
            else:
                args += ["-b:v", bitrate or "6000k"]
            if preset:
                args += ["-preset", preset]
        else:  # amf
            if mode == "cq":
                args += ["-rc", "cqp", "-qp_i", f"{crf:g}", "-qp_p", f"{crf:g}"]
            else:
                args += ["-rc", "cbr" if mode == "cbr" else "vbr_peak", "-b:v", bitrate or "6000k"]
            if preset:
                args += ["-quality", preset]

    elif enc == "prores_ks":
        args += ["-profile:v", _s(params, "profile", "3") or "3",
                 "-qscale:v", str(_i(params, "qscale", 9))]

    elif enc == "dnxhd":
        prof = _s(params, "profile", "dnxhr_hq") or "dnxhr_hq"
        args += ["-profile:v", prof]

    elif enc in _QSCALE_CODECS:
        if bitrate:
            args += ["-b:v", bitrate]
        else:
            args += ["-qscale:v", f"{crf:g}"]

    elif enc == "libwebp":
        args += ["-quality", str(_i(params, "quality", 75)),
                 "-compression_level", str(_i(params, "compression_level", 4))]
        if _b(params, "lossless"):
            args += ["-lossless", "1"]

    # 通用
    maxrate = _s(params, "maxrate")
    if maxrate and "-maxrate" not in args:
        args += ["-maxrate", maxrate]
    bufsize = _s(params, "bufsize")
    if bufsize and "-bufsize" not in args:
        args += ["-bufsize", bufsize]
    minrate = _s(params, "minrate")
    if minrate:
        args += ["-minrate", minrate]

    pix = _s(params, "pix_fmt")
    if pix and enc not in ("gif", "apng"):
        args += ["-pix_fmt", pix]

    gop = _i(params, "gop", 0)
    if gop > 0:
        args += ["-g", str(gop)]

    if pass_no:
        args += ["-pass", str(pass_no)]

    return args


def _double_rate(rate: str) -> str:
    """把 '4000k' 变成 '8000k'，用于默认 bufsize。"""
    try:
        num = float("".join(ch for ch in rate if ch.isdigit() or ch == "."))
        suffix = "".join(ch for ch in rate if ch.isalpha())
        return f"{num * 2:g}{suffix}"
    except ValueError:
        return rate


def _audio_encoder_args(enc: str, params: dict[str, Any]) -> list[str]:
    if enc == "copy":
        return ["-c:a", "copy"]
    if enc == "none":
        return ["-an"]

    args: list[str] = ["-c:a", enc]
    mode = _s(params, "audio_mode", "cbr")
    br = _s(params, "audio_bitrate")

    if enc == "libmp3lame":
        if mode == "vbr":
            args += ["-q:a", str(_i(params, "mp3_vbr_quality", 2))]
        else:
            args += ["-b:a", br or "192k"]
            if mode == "abr":
                args += ["-abr", "1"]
        args += ["-joint_stereo", "1" if _b(params, "joint_stereo", True) else "0"]
    elif enc in ("aac", "libfdk_aac"):
        if mode == "vbr":
            key = "aac_vbr_quality" if enc == "aac" else "fdk_vbr"
            args += ["-vbr", str(_i(params, key, 4))] if enc == "libfdk_aac" \
                else ["-q:a", str(_i(params, key, 4))]
        else:
            args += ["-b:a", br or "192k"]
        prof = _s(params, "he_aac") or _s(params, "aac_profile")
        if prof and prof != "aac_low":
            args += ["-profile:a", prof]
    elif enc == "libopus":
        args += ["-b:a", br or "128k"]
        if mode == "cbr":
            args += ["-vbr", "off"]
        elif mode == "cvbr":
            args += ["-vbr", "constrained"]
        else:
            args += ["-vbr", "on"]
        args += ["-application", _s(params, "opus_application", "audio") or "audio",
                 "-compression_level", str(_i(params, "opus_compression", 10))]
        fd = _s(params, "frame_duration")
        if fd:
            args += ["-frame_duration", fd]
    elif enc == "libvorbis":
        if mode == "vbr":
            args += ["-q:a", f"{_f(params, 'vorbis_quality', 5):g}"]
        else:
            args += ["-b:a", br or "192k"]
    elif enc == "flac":
        args += ["-compression_level", str(_i(params, "compression_level", 5))]
        sf = _s(params, "sample_fmt")
        if sf:
            args += ["-sample_fmt", sf]
    elif enc == "wavpack":
        args += ["-compression_level", str(_i(params, "compression_level", 2))]
    elif enc.startswith("pcm_") or enc in ("alac", "tta"):
        pass  # 无损，无码率参数
    else:
        if br:
            args += ["-b:a", br]

    sr = _s(params, "sample_rate")
    if sr:
        args += ["-ar", sr]
    ch = _s(params, "channels")
    if ch:
        args += ["-ac", ch]
    return args


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------
def build_command(src: str, dst: str, params: dict[str, Any],
                  info: MediaInfo | None = None, pass_no: int = 0,
                  passlog: str | None = None) -> list[str]:
    """构建完整 ffmpeg 命令行。

    pass_no: 0=单遍；1/2=两遍编码的第几遍。
    """
    ff = require_ffmpeg()
    cmd: list[str] = [ff, "-hide_banner", "-nostdin"]
    cmd += ["-y"] if _b(params, "overwrite", True) else ["-n"]

    hw = _s(params, "hwaccel")
    if hw:
        cmd += ["-hwaccel", hw]

    start = _s(params, "start_time")
    if start:
        cmd += ["-ss", start]

    cmd += ["-i", src]

    end = _s(params, "end_time")
    dur = _s(params, "duration")
    if dur:
        cmd += ["-t", dur]
    elif end:
        cmd += ["-to", end]

    # 注入内部推导参数：媒体总时长（用于音频淡出等依赖时长的滤镜）。
    # 这样 GUI 预览 / CLI dry-run 生成的命令与实际执行完全一致。
    if info is not None and info.duration and not params.get("_duration"):
        params = dict(params)
        params["_duration"] = info.duration

    out_ext = dst.rsplit(".", 1)[-1].lower()
    fmt = F.find_format(out_ext)
    kind = fmt.kind if fmt else F.detect_kind(dst)

    want_video = kind == F.VIDEO
    want_audio = kind in (F.VIDEO, F.AUDIO)
    if fmt and kind == F.VIDEO and not fmt.audio_codecs:
        want_audio = False   # gif / apng / webp 动图无音轨
    # 仅在探测确实拿到流信息时，才据此判断有无音轨
    if info is not None and info.streams and not info.has_audio:
        want_audio = False

    v_enc = _s(params, "video_codec") or (fmt.video_codecs[0] if fmt and fmt.video_codecs else "")
    a_enc = _s(params, "audio_codec") or (fmt.audio_codecs[0] if fmt and fmt.audio_codecs else "")

    # ---- 视频 ----
    if want_video and v_enc:
        vf = build_video_filters(params)
        if v_enc == "gif" and _b(params, "gif_palette", True):
            colors = _i(params, "gif_max_colors", 256)
            dither = _s(params, "gif_dither", "sierra2_4a") or "sierra2_4a"
            pre = ",".join(vf) + "," if vf else ""
            cmd += ["-filter_complex",
                    f"[0:v]{pre}split[a][b];[a]palettegen=max_colors={colors}[p];"
                    f"[b][p]paletteuse=dither={dither}"]
        elif vf and v_enc != "copy":
            cmd += ["-vf", ",".join(vf)]
        cmd += _video_encoder_args(v_enc, params, pass_no)
        loop = params.get("gif_loop")
        if loop is not None and out_ext in ("gif", "webp", "apng"):
            cmd += ["-loop", str(_i(params, "gif_loop", 0))]
    elif kind == F.AUDIO:
        cmd += ["-vn"]
    elif not want_video:
        cmd += ["-vn"]

    # ---- 音频 ----
    if pass_no == 1:
        want_audio = False   # 第一遍只做视频分析，丢弃音频以节省时间
    if want_audio and a_enc:
        af = build_audio_filters(params)
        if af and a_enc != "copy":
            cmd += ["-af", ",".join(af)]
        cmd += _audio_encoder_args(a_enc, params)
    elif not want_audio:
        cmd += ["-an"]

    # ---- 字幕 / 章节 / 元数据 ----
    sub_mode = "none" if pass_no == 1 else _s(params, "subtitle_mode", "copy")
    if kind == F.VIDEO and sub_mode == "copy" and out_ext in ("mkv", "mp4", "mov", "webm"):
        cmd += ["-c:s", "copy" if out_ext == "mkv" else "mov_text", "-map", "0", "-map", "-0:d?"]
    elif sub_mode in ("none", "burn"):
        cmd += ["-sn"]

    if _b(params, "strip_metadata"):
        cmd += ["-map_metadata", "-1"]
    if not _b(params, "copy_chapters", True):
        cmd += ["-map_chapters", "-1"]

    threads = _i(params, "threads", 0)
    if threads > 0:
        cmd += ["-threads", str(threads)]

    if out_ext in ("mp4", "m4v", "mov", "m4a") and _b(params, "faststart", True):
        cmd += ["-movflags", "+faststart"]

    if pass_no == 1:
        cmd += ["-f", "null"]        # 第一遍不写实际文件
    elif fmt and fmt.muxer:
        cmd += ["-f", fmt.muxer]

    extra = _s(params, "extra_args")
    if extra:
        cmd += shlex.split(extra)

    if pass_no == 1:
        null_out = "NUL" if _null_is_nul() else "/dev/null"
        if passlog:
            cmd += ["-passlogfile", passlog]
        cmd += [null_out]
    else:
        if pass_no == 2 and passlog:
            cmd += ["-passlogfile", passlog]
        cmd += [dst]
    return cmd


def _null_is_nul() -> bool:
    import os
    return os.name == "nt"


def needs_two_pass(params: dict[str, Any]) -> bool:
    return _b(params, "two_pass") and bool(_s(params, "bitrate")) \
        and _s(params, "video_codec") != "copy"


def preview_command(src: str, dst: str, params: dict[str, Any]) -> str:
    """给 UI 展示的可读命令行。"""
    try:
        cmd = build_command(src, dst, params)
    except Exception as exc:  # noqa: BLE001
        return f"（无法生成命令：{exc}）"
    return " ".join(shlex.quote(c) for c in cmd)
