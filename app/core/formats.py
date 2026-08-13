"""格式、编解码器与参数目录。

集中定义程序支持的容器格式、编解码器，以及每个编解码器可暴露的参数，
UI 与 CLI 都从这里读取，保证两端一致。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------
# 媒体类别
# --------------------------------------------------------------------------
VIDEO = "video"
AUDIO = "audio"
IMAGE = "image"


@dataclass(frozen=True)
class ContainerFormat:
    """一个可输出的容器/文件格式。"""

    ext: str
    label: str
    kind: str
    muxer: str | None = None          # ffmpeg -f 名称，None 表示由扩展名推断
    video_codecs: tuple[str, ...] = ()
    audio_codecs: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class Param:
    """一个可设置的参数。

    type: str | int | float | bool | choice
    unit: 固定单位后缀（独立于输入框显示，手动输入只改数值、不改单位）
    tier: basic=一级常用设置；advanced=二级「高级设置」折叠区
    """

    key: str
    label: str
    type: str
    default: Any = None
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    step: float = 1
    help: str = ""
    unit: str = ""
    tier: str = "advanced"


BASIC = "basic"
ADVANCED = "advanced"


@dataclass(frozen=True)
class Codec:
    encoder: str                       # 传给 ffmpeg -c:v / -c:a 的名称
    label: str
    kind: str                          # video / audio
    params: tuple[Param, ...] = ()
    lossless_capable: bool = False
    hardware: bool = False


# --------------------------------------------------------------------------
# 视频容器
# --------------------------------------------------------------------------
_H26X = ("libx264", "libx265", "libsvtav1", "libaom-av1", "libvpx-vp9", "mpeg4", "copy")
_COMMON_AUDIO = ("aac", "libmp3lame", "libopus", "libvorbis", "flac", "pcm_s16le", "ac3", "copy")

VIDEO_FORMATS: tuple[ContainerFormat, ...] = (
    ContainerFormat("mp4", "MP4 (H.264/H.265/AV1)", VIDEO, "mp4", _H26X, ("aac", "libmp3lame", "libopus", "ac3", "copy")),
    ContainerFormat("mkv", "Matroska MKV (万能容器)", VIDEO, "matroska", _H26X, _COMMON_AUDIO),
    ContainerFormat("webm", "WebM (VP9/AV1)", VIDEO, "webm", ("libvpx-vp9", "libvpx", "libsvtav1", "libaom-av1", "copy"), ("libopus", "libvorbis", "copy")),
    ContainerFormat("mov", "QuickTime MOV", VIDEO, "mov", _H26X + ("prores_ks", "dnxhd"), _COMMON_AUDIO),
    ContainerFormat("avi", "AVI", VIDEO, "avi", ("mpeg4", "libxvid", "libx264", "huffyuv", "copy"), ("libmp3lame", "pcm_s16le", "ac3", "copy")),
    ContainerFormat("flv", "Flash Video FLV", VIDEO, "flv", ("libx264", "flv", "copy"), ("aac", "libmp3lame", "copy")),
    ContainerFormat("wmv", "Windows Media WMV", VIDEO, "asf", ("wmv2", "msmpeg4v3", "copy"), ("wmav2", "copy")),
    ContainerFormat("mpg", "MPEG-1/2 Program Stream", VIDEO, "mpeg", ("mpeg1video", "mpeg2video", "copy"), ("mp2", "libmp3lame", "copy")),
    ContainerFormat("ts", "MPEG-TS 传输流", VIDEO, "mpegts", ("libx264", "libx265", "mpeg2video", "copy"), ("aac", "ac3", "mp2", "copy")),
    ContainerFormat("m4v", "iTunes M4V", VIDEO, "mp4", ("libx264", "libx265", "copy"), ("aac", "copy")),
    ContainerFormat("3gp", "3GP 手机视频", VIDEO, "3gp", ("libx264", "mpeg4", "h263", "copy"), ("aac", "amr_nb", "copy")),
    ContainerFormat("ogv", "Ogg Video", VIDEO, "ogg", ("libtheora", "copy"), ("libvorbis", "libopus", "copy")),
    ContainerFormat("gif", "GIF 动画", VIDEO, "gif", ("gif",), ()),
    ContainerFormat("webp", "WebP 动图", VIDEO, "webp", ("libwebp",), ()),
    ContainerFormat("apng", "APNG 动图", VIDEO, "apng", ("apng",), ()),
    ContainerFormat("mp.jpg", "Live Photo 动态照片", VIDEO, video_codecs=("libx264",), audio_codecs=("aac", "copy"), notes="视频转实况照片，兼容 Google Photos / 安卓相册"),
    ContainerFormat("mxf", "MXF 广播格式", VIDEO, "mxf", ("mpeg2video", "dnxhd", "libx264"), ("pcm_s16le",)),
)

# --------------------------------------------------------------------------
# 音频容器
# --------------------------------------------------------------------------
AUDIO_FORMATS: tuple[ContainerFormat, ...] = (
    ContainerFormat("mp3", "MP3", AUDIO, "mp3", (), ("libmp3lame",)),
    ContainerFormat("aac", "AAC (ADTS)", AUDIO, "adts", (), ("aac",)),
    ContainerFormat("m4a", "M4A / AAC-ALAC", AUDIO, "ipod", (), ("aac", "alac", "copy")),
    ContainerFormat("flac", "FLAC 无损", AUDIO, "flac", (), ("flac",)),
    ContainerFormat("wav", "WAV (PCM)", AUDIO, "wav", (), ("pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm_u8")),
    ContainerFormat("ogg", "Ogg Vorbis", AUDIO, "ogg", (), ("libvorbis", "libopus", "flac")),
    ContainerFormat("opus", "Opus", AUDIO, "opus", (), ("libopus",)),
    ContainerFormat("wma", "Windows Media Audio", AUDIO, "asf", (), ("wmav2",)),
    ContainerFormat("aiff", "AIFF", AUDIO, "aiff", (), ("pcm_s16be", "pcm_s24be")),
    ContainerFormat("ac3", "Dolby AC-3", AUDIO, "ac3", (), ("ac3",)),
    ContainerFormat("eac3", "Dolby Digital Plus", AUDIO, "eac3", (), ("eac3",)),
    ContainerFormat("amr", "AMR-NB 语音", AUDIO, "amr", (), ("amr_nb",)),
    ContainerFormat("mka", "Matroska Audio", AUDIO, "matroska", (), ("flac", "libopus", "aac", "libmp3lame", "copy")),
    ContainerFormat("caf", "Apple CAF", AUDIO, "caf", (), ("alac", "pcm_s16le", "aac")),
    ContainerFormat("au", "Sun AU", AUDIO, "au", (), ("pcm_s16be",)),
    ContainerFormat("mp2", "MPEG Audio Layer II", AUDIO, "mp2", (), ("mp2",)),
    ContainerFormat("spx", "Speex", AUDIO, "ogg", (), ("libspeex",)),
    ContainerFormat("tta", "True Audio 无损", AUDIO, "tta", (), ("tta",)),
    ContainerFormat("wv", "WavPack 无损", AUDIO, "wv", (), ("wavpack",)),
)

# --------------------------------------------------------------------------
# 图片格式
# --------------------------------------------------------------------------
IMAGE_FORMATS: tuple[ContainerFormat, ...] = (
    ContainerFormat("jpg", "JPEG", IMAGE, notes="有损，支持质量/渐进/色度抽样"),
    ContainerFormat("jpeg", "JPEG (.jpeg)", IMAGE),
    ContainerFormat("png", "PNG", IMAGE, notes="无损，支持压缩级别/位深/交错"),
    ContainerFormat("webp", "WebP", IMAGE, notes="支持有损与无损"),
    ContainerFormat("avif", "AVIF", IMAGE, notes="AV1 图像，高压缩比"),
    ContainerFormat("heif", "HEIF/HEIC", IMAGE),
    ContainerFormat("bmp", "BMP 位图", IMAGE),
    ContainerFormat("gif", "GIF", IMAGE),
    ContainerFormat("tiff", "TIFF", IMAGE, notes="支持多种压缩方式与多页"),
    ContainerFormat("tga", "Targa TGA", IMAGE),
    ContainerFormat("ico", "Windows 图标 ICO", IMAGE),
    ContainerFormat("ppm", "Netpbm PPM", IMAGE),
    ContainerFormat("pgm", "Netpbm PGM", IMAGE),
    ContainerFormat("pcx", "PCX", IMAGE),
    ContainerFormat("jp2", "JPEG 2000", IMAGE),
    ContainerFormat("dds", "DDS 纹理", IMAGE),
    ContainerFormat("eps", "EPS", IMAGE),
    ContainerFormat("pdf", "PDF (图片页)", IMAGE),
    ContainerFormat("im", "IM", IMAGE),
    ContainerFormat("sgi", "SGI", IMAGE),
)

# Motion Photo（实况照片 / 动态照片）的文件名后缀（Google 惯例 *.MP.jpg）。
# 这类文件本质是「JPEG + 尾部拼接 MP4」，识别时按视频处理（取内嵌视频）。
MOTION_PHOTO_SUFFIXES = ("mp.jpg", "mp.jpeg", "mpjpeg")


def is_motion_photo(path: str) -> bool:
    """判断文件是否为 Motion Photo（Live Photo 单文件格式）。"""
    return path.lower().endswith(MOTION_PHOTO_SUFFIXES)


def input_ext(path: str) -> str:
    """返回用于白名单匹配的扩展名；Motion Photo 特判为完整后缀（mp.jpg）。"""
    if is_motion_photo(path):
        return "mp.jpg"
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


# 可读取的输入扩展名（比可写的更宽）
INPUT_VIDEO_EXT = tuple(sorted({f.ext for f in VIDEO_FORMATS} | {
    "m2ts", "mts", "vob", "rmvb", "rm", "asf", "divx", "f4v", "h264", "hevc",
    "m2v", "mpeg", "mpv", "ogm", "swf", "y4m", "dv", "amv", "nut",
} | set(MOTION_PHOTO_SUFFIXES)))
INPUT_AUDIO_EXT = tuple(sorted({f.ext for f in AUDIO_FORMATS} | {
    "ape", "dts", "mpc", "ra", "shn", "voc", "w64", "gsm", "oga", "m4b", "8svx",
}))
INPUT_IMAGE_EXT = tuple(sorted({f.ext for f in IMAGE_FORMATS} | {
    "heic", "jfif", "pbm", "xbm", "xpm", "blp", "cur", "fits", "icns", "j2k",
    "jpf", "jpx", "msp", "pfm", "psd", "qoi", "svg", "wmf", "emf",
}))


# --------------------------------------------------------------------------
# 编解码器参数
# --------------------------------------------------------------------------
_X26X_PRESETS = ("ultrafast", "superfast", "veryfast", "faster", "fast",
                 "medium", "slow", "slower", "veryslow", "placebo")
_X264_TUNES = ("", "film", "animation", "grain", "stillimage", "fastdecode",
               "zerolatency", "psnr", "ssim")


def _rate_params(default_crf: float, crf_max: float = 63, crf_label: str = "CRF 质量") -> tuple[Param, ...]:
    return (
        Param("rate_mode", "码率控制模式", "choice", "crf",
              ("crf", "cbr", "vbr", "cq", "lossless"),
              help="crf=恒定质量；cbr=恒定码率；vbr=平均码率；cq=恒定量化；lossless=无损",
              tier=BASIC),
        Param("crf", crf_label, "float", default_crf, minimum=0, maximum=crf_max, step=1,
              help="数值越小质量越高、文件越大", tier=BASIC),
        Param("bitrate", "目标码率", "str", "", help="如 4000k、8M；CBR/VBR 模式下使用",
              tier=BASIC),
        Param("maxrate", "最大码率", "str", "", help="配合 bufsize 限制峰值"),
        Param("bufsize", "缓冲区大小", "str", "", help="通常为 maxrate 的 1~2 倍"),
        Param("minrate", "最小码率", "str", ""),
        Param("two_pass", "两遍编码", "bool", False, help="更精确命中目标码率，耗时翻倍"),
    )


VIDEO_CODECS: dict[str, Codec] = {}
AUDIO_CODECS: dict[str, Codec] = {}


def _reg_v(codec: Codec) -> None:
    VIDEO_CODECS[codec.encoder] = codec


def _reg_a(codec: Codec) -> None:
    AUDIO_CODECS[codec.encoder] = codec


_reg_v(Codec("libx264", "H.264 / AVC (libx264)", VIDEO, _rate_params(23, 51) + (
    Param("preset", "编码预设", "choice", "medium", _X26X_PRESETS, help="越慢压缩率越好"),
    Param("tune", "调优", "choice", "", _X264_TUNES),
    Param("profile", "Profile", "choice", "", ("", "baseline", "main", "high", "high10", "high422", "high444")),
    Param("level", "Level", "choice", "", ("", "3.0", "3.1", "4.0", "4.1", "4.2", "5.0", "5.1", "5.2", "6.0", "6.2")),
    Param("pix_fmt", "像素格式", "choice", "yuv420p", ("yuv420p", "yuv422p", "yuv444p", "yuv420p10le", "yuv444p10le", "nv12")),
    Param("gop", "关键帧间隔 GOP", "int", 0, minimum=0, maximum=1200, help="0=自动"),
    Param("bframes", "B 帧数量", "int", -1, minimum=-1, maximum=16, help="-1=编码器默认"),
    Param("refs", "参考帧数量", "int", 0, minimum=0, maximum=16, help="0=默认"),
    Param("x264_params", "x264 额外参数", "str", "", help="形如 aq-mode=3:psy-rd=1.0"),
), lossless_capable=True))

_reg_v(Codec("libx265", "H.265 / HEVC (libx265)", VIDEO, _rate_params(28, 51) + (
    Param("preset", "编码预设", "choice", "medium", _X26X_PRESETS),
    Param("tune", "调优", "choice", "", ("", "psnr", "ssim", "grain", "fastdecode", "zerolatency", "animation")),
    Param("profile", "Profile", "choice", "", ("", "main", "main10", "main12", "main444-8")),
    Param("pix_fmt", "像素格式", "choice", "yuv420p", ("yuv420p", "yuv420p10le", "yuv422p10le", "yuv444p10le")),
    Param("gop", "关键帧间隔 GOP", "int", 0, minimum=0, maximum=1200),
    Param("x265_params", "x265 额外参数", "str", ""),
), lossless_capable=True))

_reg_v(Codec("libsvtav1", "AV1 (SVT-AV1，快)", VIDEO, _rate_params(35, 63) + (
    Param("preset", "速度预设 0-13", "int", 8, minimum=0, maximum=13, help="数值越小越慢越好"),
    Param("pix_fmt", "像素格式", "choice", "yuv420p", ("yuv420p", "yuv420p10le")),
    Param("gop", "关键帧间隔 GOP", "int", 0, minimum=0, maximum=1200),
    Param("svtav1_params", "SVT-AV1 额外参数", "str", "", help="形如 tune=0:film-grain=8"),
)))

_reg_v(Codec("libaom-av1", "AV1 (libaom，慢/高质量)", VIDEO, _rate_params(30, 63) + (
    Param("cpu_used", "cpu-used 0-8", "int", 4, minimum=0, maximum=8),
    Param("row_mt", "行多线程", "bool", True),
    Param("tiles", "分块 tiles", "str", "", help="如 2x2"),
    Param("pix_fmt", "像素格式", "choice", "yuv420p", ("yuv420p", "yuv420p10le", "yuv422p", "yuv444p")),
), lossless_capable=True))

_reg_v(Codec("libvpx-vp9", "VP9 (libvpx)", VIDEO, _rate_params(31, 63) + (
    Param("cpu_used", "cpu-used -8~8", "int", 1, minimum=-8, maximum=8),
    Param("row_mt", "行多线程", "bool", True),
    Param("deadline", "编码模式", "choice", "good", ("good", "best", "realtime")),
    Param("pix_fmt", "像素格式", "choice", "yuv420p", ("yuv420p", "yuv422p", "yuv444p", "yuv420p10le")),
), lossless_capable=True))

_reg_v(Codec("libvpx", "VP8 (libvpx)", VIDEO, _rate_params(10, 63) + (
    Param("cpu_used", "cpu-used", "int", 1, minimum=-16, maximum=16),
    Param("pix_fmt", "像素格式", "choice", "yuv420p", ("yuv420p",)),
)))

_reg_v(Codec("mpeg4", "MPEG-4 Part 2", VIDEO, _rate_params(6, 31, "量化 qscale") + (
    Param("pix_fmt", "像素格式", "choice", "yuv420p", ("yuv420p",)),
)))
_reg_v(Codec("libxvid", "Xvid", VIDEO, _rate_params(6, 31, "量化 qscale")))
_reg_v(Codec("mpeg2video", "MPEG-2", VIDEO, _rate_params(5, 31, "量化 qscale")))
_reg_v(Codec("mpeg1video", "MPEG-1", VIDEO, _rate_params(5, 31, "量化 qscale")))
_reg_v(Codec("libtheora", "Theora", VIDEO, _rate_params(7, 10, "质量 qscale")))
_reg_v(Codec("wmv2", "Windows Media Video 8", VIDEO, _rate_params(5, 31, "量化 qscale")))
_reg_v(Codec("msmpeg4v3", "MS MPEG-4 v3 (DivX3)", VIDEO, _rate_params(5, 31, "量化 qscale")))
_reg_v(Codec("h263", "H.263", VIDEO, _rate_params(5, 31, "量化 qscale")))
_reg_v(Codec("flv", "Sorenson Spark (FLV1)", VIDEO, _rate_params(5, 31, "量化 qscale")))
_reg_v(Codec("huffyuv", "HuffYUV 无损", VIDEO, (), lossless_capable=True))
_reg_v(Codec("prores_ks", "Apple ProRes", VIDEO, (
    Param("profile", "ProRes Profile", "choice", "3",
          ("0", "1", "2", "3", "4", "5"),
          help="0=Proxy 1=LT 2=422 3=422HQ 4=4444 5=4444XQ"),
    Param("pix_fmt", "像素格式", "choice", "yuv422p10le", ("yuv422p10le", "yuv444p10le", "yuva444p10le")),
    Param("qscale", "质量 qscale", "int", 9, minimum=0, maximum=32),
)))
_reg_v(Codec("dnxhd", "Avid DNxHD/DNxHR", VIDEO, (
    Param("profile", "DNxHR Profile", "choice", "dnxhr_hq", ("dnxhr_lb", "dnxhr_sq", "dnxhr_hq", "dnxhr_hqx", "dnxhr_444")),
    Param("pix_fmt", "像素格式", "choice", "yuv422p", ("yuv422p", "yuv422p10le", "yuv444p10le")),
)))
_reg_v(Codec("gif", "GIF 编码", VIDEO, (
    Param("gif_palette", "生成最优调色板", "bool", True, help="显著提升 GIF 画质"),
    Param("gif_dither", "抖动算法", "choice", "sierra2_4a",
          ("none", "bayer", "floyd_steinberg", "sierra2", "sierra2_4a")),
    Param("gif_max_colors", "最大颜色数", "int", 256, minimum=2, maximum=256),
    Param("gif_loop", "循环次数", "int", 0, minimum=-1, maximum=1000, help="0=无限循环，-1=不循环"),
)))
_reg_v(Codec("libwebp", "WebP 动图编码", VIDEO, (
    Param("quality", "质量 0-100", "int", 75, minimum=0, maximum=100),
    Param("lossless", "无损", "bool", False),
    Param("compression_level", "压缩级别 0-6", "int", 4, minimum=0, maximum=6),
    Param("gif_loop", "循环次数", "int", 0, minimum=-1, maximum=1000),
), lossless_capable=True))
_reg_v(Codec("apng", "APNG 编码", VIDEO, (
    Param("gif_loop", "循环次数", "int", 0, minimum=0, maximum=1000),
)))
_reg_v(Codec("copy", "直接复制视频流（不重编码）", VIDEO, ()))

# 硬件编码器
for _hw, _label in (
    ("h264_nvenc", "H.264 (NVIDIA NVENC)"),
    ("hevc_nvenc", "H.265 (NVIDIA NVENC)"),
    ("av1_nvenc", "AV1 (NVIDIA NVENC)"),
    ("h264_qsv", "H.264 (Intel QuickSync)"),
    ("hevc_qsv", "H.265 (Intel QuickSync)"),
    ("av1_qsv", "AV1 (Intel QuickSync)"),
    ("h264_amf", "H.264 (AMD AMF)"),
    ("hevc_amf", "H.265 (AMD AMF)"),
    ("av1_amf", "AV1 (AMD AMF)"),
):
    _reg_v(Codec(_hw, _label, VIDEO, (
        Param("rate_mode", "码率控制模式", "choice", "cq", ("cq", "cbr", "vbr"), tier=BASIC),
        Param("crf", "质量 CQ/QP", "float", 23, minimum=0, maximum=51, step=1, tier=BASIC),
        Param("bitrate", "目标码率", "str", "6000k", tier=BASIC),
        Param("maxrate", "最大码率", "str", ""),
        Param("bufsize", "缓冲区大小", "str", ""),
        Param("preset", "硬件预设", "choice", "", ("", "p1", "p2", "p3", "p4", "p5", "p6", "p7",
                                                   "quality", "balanced", "speed", "veryfast", "slow")),
        Param("pix_fmt", "像素格式", "choice", "yuv420p", ("yuv420p", "p010le", "nv12", "yuv444p")),
        Param("gop", "关键帧间隔 GOP", "int", 0, minimum=0, maximum=1200),
    ), hardware=True))

# ---------------------------- 音频编码器 ----------------------------------
_A_COMMON = (
    Param("audio_bitrate", "音频码率", "str", "192k", help="如 128k、320k", tier=BASIC),
    Param("sample_rate", "采样率", "choice", "", ("", "8000", "11025", "16000", "22050", "32000",
                                                     "44100", "48000", "88200", "96000", "176400", "192000"),
          unit="Hz"),
    Param("channels", "声道数", "choice", "", ("", "1", "2", "4", "6", "8"),
          help="1=单声道 2=立体声 6=5.1 8=7.1"),
    Param("volume", "音量调整", "float", 0, minimum=-40, maximum=40, step=0.5, unit="dB",
          tier=BASIC),
)

_reg_a(Codec("libmp3lame", "MP3 (LAME)", AUDIO, _A_COMMON + (
    Param("audio_mode", "码率模式", "choice", "cbr", ("cbr", "vbr", "abr")),
    Param("mp3_vbr_quality", "VBR 质量 0-9", "int", 2, minimum=0, maximum=9, help="0 最好"),
    Param("joint_stereo", "联合立体声", "bool", True),
)))
_reg_a(Codec("aac", "AAC-LC (原生)", AUDIO, _A_COMMON + (
    Param("audio_mode", "码率模式", "choice", "cbr", ("cbr", "vbr")),
    Param("aac_vbr_quality", "VBR 质量 1-5", "int", 4, minimum=1, maximum=5),
    Param("aac_profile", "AAC Profile", "choice", "aac_low", ("aac_low", "mpeg2_aac_low", "aac_ltp", "aac_main")),
)))
_reg_a(Codec("libfdk_aac", "AAC (libfdk，需支持)", AUDIO, _A_COMMON + (
    Param("audio_mode", "码率模式", "choice", "cbr", ("cbr", "vbr")),
    Param("fdk_vbr", "VBR 等级 1-5", "int", 4, minimum=1, maximum=5),
    Param("he_aac", "HE-AAC", "choice", "", ("", "aac_he", "aac_he_v2")),
)))
_reg_a(Codec("libopus", "Opus", AUDIO, _A_COMMON + (
    Param("audio_mode", "码率模式", "choice", "vbr", ("vbr", "cvbr", "cbr")),
    Param("opus_application", "应用场景", "choice", "audio", ("audio", "voip", "lowdelay")),
    Param("opus_compression", "压缩级别 0-10", "int", 10, minimum=0, maximum=10),
    Param("frame_duration", "帧长 ms", "choice", "20", ("2.5", "5", "10", "20", "40", "60")),
)))
_reg_a(Codec("libvorbis", "Vorbis", AUDIO, _A_COMMON + (
    Param("audio_mode", "码率模式", "choice", "vbr", ("vbr", "cbr")),
    Param("vorbis_quality", "VBR 质量 -1~10", "float", 5, minimum=-1, maximum=10, step=0.5),
)))
_reg_a(Codec("flac", "FLAC 无损", AUDIO, (
    Param("sample_rate", "采样率", "choice", "", ("", "44100", "48000", "88200", "96000", "192000"),
          unit="Hz"),
    Param("channels", "声道数", "choice", "", ("", "1", "2", "6", "8")),
    Param("volume", "音量调整", "float", 0, minimum=-40, maximum=40, step=0.5, unit="dB",
          tier=BASIC),
    Param("compression_level", "压缩级别 0-12", "int", 5, minimum=0, maximum=12),
    Param("sample_fmt", "采样格式", "choice", "s16", ("s16", "s32")),
), lossless_capable=True))
_reg_a(Codec("alac", "Apple 无损 ALAC", AUDIO, (
    Param("sample_rate", "采样率", "choice", "", ("", "44100", "48000", "96000", "192000"),
          unit="Hz"),
    Param("channels", "声道数", "choice", "", ("", "1", "2", "6")),
    Param("volume", "音量调整", "float", 0, minimum=-40, maximum=40, step=0.5, unit="dB",
          tier=BASIC),
), lossless_capable=True))
for _pcm, _lbl in (("pcm_s16le", "PCM 16-bit"), ("pcm_s24le", "PCM 24-bit"),
                   ("pcm_s32le", "PCM 32-bit"), ("pcm_f32le", "PCM 32-bit 浮点"),
                   ("pcm_u8", "PCM 8-bit 无符号"), ("pcm_s16be", "PCM 16-bit 大端"),
                   ("pcm_s24be", "PCM 24-bit 大端")):
    _reg_a(Codec(_pcm, _lbl, AUDIO, (
        Param("sample_rate", "采样率", "choice", "", ("", "8000", "16000", "22050", "44100", "48000", "96000", "192000"),
              unit="Hz"),
        Param("channels", "声道数", "choice", "", ("", "1", "2", "6", "8")),
        Param("volume", "音量调整", "float", 0, minimum=-40, maximum=40, step=0.5, unit="dB",
              tier=BASIC),
    ), lossless_capable=True))
_reg_a(Codec("ac3", "Dolby AC-3", AUDIO, _A_COMMON))
_reg_a(Codec("eac3", "Dolby Digital Plus", AUDIO, _A_COMMON))
_reg_a(Codec("wmav2", "WMA v2", AUDIO, _A_COMMON))
_reg_a(Codec("mp2", "MPEG Audio Layer II", AUDIO, _A_COMMON))
_reg_a(Codec("amr_nb", "AMR 窄带语音", AUDIO, (
    Param("audio_bitrate", "音频码率", "str", "12.2k"),
    Param("sample_rate", "采样率 Hz", "choice", "8000", ("8000",)),
    Param("channels", "声道数", "choice", "1", ("1",)),
)))
_reg_a(Codec("libspeex", "Speex 语音", AUDIO, _A_COMMON))
_reg_a(Codec("tta", "True Audio 无损", AUDIO, (), lossless_capable=True))
_reg_a(Codec("wavpack", "WavPack 无损", AUDIO, (
    Param("compression_level", "压缩级别 0-8", "int", 2, minimum=0, maximum=8),
), lossless_capable=True))
_reg_a(Codec("copy", "直接复制音频流（不重编码）", AUDIO, ()))


# --------------------------------------------------------------------------
# 通用（与编码器无关）的处理参数
# --------------------------------------------------------------------------
VIDEO_FILTER_PARAMS: tuple[Param, ...] = (
    Param("width", "宽度", "int", 0, minimum=0, maximum=16384, help="0=保持原样", unit="px",
          tier=BASIC),
    Param("height", "高度", "int", 0, minimum=0, maximum=16384,
          help="0=保持原样；宽高其一填 -1 可等比", unit="px", tier=BASIC),
    Param("keep_aspect", "保持宽高比", "bool", True, tier=BASIC),
    Param("scale_flags", "缩放算法", "choice", "bicubic",
          ("fast_bilinear", "bilinear", "bicubic", "neighbor", "area", "bicublin", "gauss", "sinc", "lanczos", "spline")),
    Param("fps", "帧率", "str", "", help="留空=保持原帧率，可填 24、30000/1001", unit="fps",
          tier=BASIC),
    Param("crop", "裁剪", "str", "", help="格式 w:h:x:y"),
    Param("pad", "填充", "str", "", help="格式 w:h:x:y:color"),
    Param("rotate", "旋转", "choice", "0", ("0", "90", "180", "270"), tier=BASIC),
    Param("hflip", "水平翻转", "bool", False),
    Param("vflip", "垂直翻转", "bool", False),
    Param("deinterlace", "去隔行 (yadif)", "bool", False),
    Param("denoise", "降噪强度", "choice", "", ("", "light", "medium", "strong")),
    Param("sharpen", "锐化", "bool", False),
    Param("brightness", "亮度", "float", 0, minimum=-1, maximum=1, step=0.05,
          help="-1~1，0=原始画面"),
    Param("contrast", "对比度", "float", 1, minimum=0, maximum=4, step=0.05,
          help="0~4，1=原始画面"),
    Param("saturation", "饱和度", "float", 1, minimum=0, maximum=3, step=0.05,
          help="0~3，1=原始画面"),
    Param("gamma", "伽马", "float", 1, minimum=0.1, maximum=10, step=0.05,
          help="0.1~10，1=原始画面"),
    Param("video_filter", "自定义视频滤镜链", "str", "", help="追加到 -vf 之后的原始 filtergraph"),
)

AUDIO_FILTER_PARAMS: tuple[Param, ...] = (
    Param("normalize", "响度归一化 (EBU R128)", "bool", False),
    Param("loudness_target", "目标响度", "float", -16, minimum=-70, maximum=-5, step=0.5,
          unit="LUFS"),
    Param("audio_fade_in", "淡入", "float", 0, minimum=0, maximum=60, step=0.1, unit="秒"),
    Param("audio_fade_out", "淡出", "float", 0, minimum=0, maximum=60, step=0.1, unit="秒"),
    Param("tempo", "变速（不变调）", "float", 1.0, minimum=0.5, maximum=2.0, step=0.05,
          unit="倍"),
    Param("pitch_semitones", "变调", "float", 0, minimum=-12, maximum=12, step=1, unit="半音"),
    Param("audio_filter", "自定义音频滤镜链", "str", ""),
)

GENERAL_PARAMS: tuple[Param, ...] = (
    Param("start_time", "起始时间", "str", "", help="如 00:00:10 或 10.5，留空=从头",
          tier=BASIC),
    Param("end_time", "结束时间", "str", "", help="与时长二选一", tier=BASIC),
    Param("duration", "截取时长", "str", "", help="如 00:00:30", tier=BASIC),
    Param("threads", "线程数", "int", 0, minimum=0, maximum=64, help="0=自动"),
    Param("overwrite", "覆盖已存在文件", "bool", True),
    Param("strip_metadata", "移除元数据", "bool", False),
    Param("copy_chapters", "保留章节", "bool", True),
    Param("subtitle_mode", "字幕处理", "choice", "copy", ("copy", "none", "burn"),
          help="burn=硬字幕烧录（需外挂字幕文件）"),
    Param("subtitle_file", "外挂字幕文件", "str", ""),
    Param("faststart", "MP4 faststart", "bool", True, help="把索引移到文件头，便于网络播放"),
    Param("hwaccel", "解码硬件加速", "choice", "", ("", "auto", "cuda", "qsv", "d3d11va", "dxva2", "vulkan")),
    Param("extra_args", "自定义 ffmpeg 参数", "str", "", help="原样追加到命令行，专家使用"),
)

# ---------------------------- 图片参数 ------------------------------------
IMAGE_PARAMS: tuple[Param, ...] = (
    Param("width", "宽度", "int", 0, minimum=0, maximum=60000, help="0=保持原样", unit="px",
          tier=BASIC),
    Param("height", "高度", "int", 0, minimum=0, maximum=60000, unit="px",
          tier=BASIC),
    Param("keep_aspect", "保持宽高比", "bool", True, tier=BASIC),
    Param("resample", "重采样算法", "choice", "lanczos",
          ("nearest", "box", "bilinear", "hamming", "bicubic", "lanczos")),
    Param("quality", "质量", "int", 90, minimum=1, maximum=100,
          help="1~100，越高画质越好（JPEG/WebP/AVIF 等有损格式）", tier=BASIC),
    Param("lossless", "无损模式", "bool", False, help="WebP/AVIF 支持"),
    Param("optimize", "优化体积", "bool", True),
    Param("progressive", "渐进式 JPEG", "bool", False),
    Param("subsampling", "色度抽样", "choice", "auto", ("auto", "4:4:4", "4:2:2", "4:2:0")),
    Param("png_compress_level", "PNG 压缩级别 0-9", "int", 6, minimum=0, maximum=9),
    Param("webp_method", "WebP 压缩方法 0-6", "int", 4, minimum=0, maximum=6),
    Param("avif_speed", "AVIF 速度 0-10", "int", 6, minimum=0, maximum=10),
    Param("tiff_compression", "TIFF 压缩", "choice", "tiff_deflate",
          ("none", "tiff_lzw", "tiff_deflate", "jpeg", "packbits")),
    Param("color_mode", "颜色模式", "choice", "", ("", "RGB", "RGBA", "L", "LA", "CMYK", "P", "1")),
    Param("bit_depth", "调色板位深", "choice", "", ("", "1", "2", "4", "8"), help="P 模式量化颜色数"),
    Param("dpi", "DPI", "int", 0, minimum=0, maximum=4800, help="0=不写入"),
    Param("background", "透明背景填充色", "str", "#FFFFFF",
          help="转为无透明通道格式（如 JPEG）时使用"),
    Param("rotate", "旋转", "choice", "0", ("0", "90", "180", "270")),
    Param("hflip", "水平翻转", "bool", False),
    Param("vflip", "垂直翻转", "bool", False),
    Param("auto_orient", "按 EXIF 自动摆正", "bool", True),
    Param("strip_metadata", "移除 EXIF/元数据", "bool", False),
    Param("keep_icc", "保留 ICC 色彩配置", "bool", True),
    Param("brightness", "亮度倍率", "float", 1.0, minimum=0, maximum=3, step=0.05),
    Param("contrast", "对比度倍率", "float", 1.0, minimum=0, maximum=3, step=0.05),
    Param("saturation", "饱和度倍率", "float", 1.0, minimum=0, maximum=3, step=0.05),
    Param("sharpness", "锐度倍率", "float", 1.0, minimum=0, maximum=3, step=0.05),
    Param("blur", "高斯模糊半径", "float", 0, minimum=0, maximum=50, step=0.5),
    Param("grayscale", "转灰度", "bool", False),
    Param("ico_sizes", "ICO 尺寸集合", "str", "16,32,48,64,128,256"),
    Param("overwrite", "覆盖已存在文件", "bool", True),
)


# --------------------------------------------------------------------------
# 查询辅助
# --------------------------------------------------------------------------
ALL_FORMATS: tuple[ContainerFormat, ...] = VIDEO_FORMATS + AUDIO_FORMATS + IMAGE_FORMATS


def formats_for(kind: str) -> tuple[ContainerFormat, ...]:
    return {VIDEO: VIDEO_FORMATS, AUDIO: AUDIO_FORMATS, IMAGE: IMAGE_FORMATS}[kind]


def find_format(ext: str, kind: str | None = None) -> ContainerFormat | None:
    ext = ext.lower().lstrip(".")
    pool = formats_for(kind) if kind else ALL_FORMATS
    for f in pool:
        if f.ext == ext:
            return f
    return None


def detect_kind(path: str) -> str:
    if is_motion_photo(path):
        return VIDEO
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext in INPUT_IMAGE_EXT and ext not in ("gif", "webp", "apng"):
        return IMAGE
    if ext in INPUT_VIDEO_EXT:
        return VIDEO
    if ext in INPUT_AUDIO_EXT:
        return AUDIO
    if ext in INPUT_IMAGE_EXT:
        return IMAGE
    return VIDEO


def codec_params(encoder: str) -> tuple[Param, ...]:
    c = VIDEO_CODECS.get(encoder) or AUDIO_CODECS.get(encoder)
    return c.params if c else ()


def default_params_for(kind: str) -> dict[str, Any]:
    """返回该类别所有参数的默认值字典。"""
    out: dict[str, Any] = {}
    if kind == IMAGE:
        pool: tuple[Param, ...] = IMAGE_PARAMS
    else:
        pool = GENERAL_PARAMS + VIDEO_FILTER_PARAMS + AUDIO_FILTER_PARAMS
    for p in pool:
        out[p.key] = p.default
    return out
