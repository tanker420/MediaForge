package cn.mediaforge.app

/**
 * 格式、编解码器与参数目录 —— 桌面版 app/core/formats.py 的 Kotlin 1:1 移植。
 * UI 表单与命令翻译器都从这里读取，保证单一事实来源。
 */

data class Param(
    val key: String,
    val label: String,
    val type: String,                       // str | int | float | bool | choice
    val default: Any? = null,
    val choices: List<String> = emptyList(),
    val min: Double? = null,
    val max: Double? = null,
    val step: Double = 1.0,
    val help: String = "",
)

data class Codec(
    val encoder: String,
    val label: String,
    val kind: String,
    val params: List<Param> = emptyList(),
    val hardware: Boolean = false,
)

data class ContainerFormat(
    val ext: String,
    val label: String,
    val kind: String,
    val muxer: String? = null,
    val videoCodecs: List<String> = emptyList(),
    val audioCodecs: List<String> = emptyList(),
)

object Formats {
    const val VIDEO = "video"
    const val AUDIO = "audio"
    const val IMAGE = "image"

    private val H26X = listOf("libx264", "libx265", "libsvtav1", "libaom-av1", "libvpx-vp9", "mpeg4", "copy")
    private val COMMON_AUDIO = listOf("aac", "libmp3lame", "libopus", "libvorbis", "flac", "pcm_s16le", "ac3", "copy")

    val VIDEO_FORMATS: List<ContainerFormat> = listOf(
        ContainerFormat("mp4", "MP4 (H.264/H.265/AV1)", VIDEO, "mp4", H26X, listOf("aac", "libmp3lame", "libopus", "ac3", "copy")),
        ContainerFormat("mkv", "Matroska MKV (万能容器)", VIDEO, "matroska", H26X, COMMON_AUDIO),
        ContainerFormat("webm", "WebM (VP9/AV1)", VIDEO, "webm", listOf("libvpx-vp9", "libvpx", "libsvtav1", "libaom-av1", "copy"), listOf("libopus", "libvorbis", "copy")),
        ContainerFormat("mov", "QuickTime MOV", VIDEO, "mov", H26X + listOf("prores_ks", "dnxhd"), COMMON_AUDIO),
        ContainerFormat("avi", "AVI", VIDEO, "avi", listOf("mpeg4", "libxvid", "libx264", "huffyuv", "copy"), listOf("libmp3lame", "pcm_s16le", "ac3", "copy")),
        ContainerFormat("flv", "Flash Video FLV", VIDEO, "flv", listOf("libx264", "flv", "copy"), listOf("aac", "libmp3lame", "copy")),
        ContainerFormat("wmv", "Windows Media WMV", VIDEO, "asf", listOf("wmv2", "msmpeg4v3", "copy"), listOf("wmav2", "copy")),
        ContainerFormat("mpg", "MPEG-1/2 Program Stream", VIDEO, "mpeg", listOf("mpeg1video", "mpeg2video", "copy"), listOf("mp2", "libmp3lame", "copy")),
        ContainerFormat("ts", "MPEG-TS 传输流", VIDEO, "mpegts", listOf("libx264", "libx265", "mpeg2video", "copy"), listOf("aac", "ac3", "mp2", "copy")),
        ContainerFormat("m4v", "iTunes M4V", VIDEO, "mp4", listOf("libx264", "libx265", "copy"), listOf("aac", "copy")),
        ContainerFormat("3gp", "3GP 手机视频", VIDEO, "3gp", listOf("libx264", "mpeg4", "h263", "copy"), listOf("aac", "amr_nb", "copy")),
        ContainerFormat("ogv", "Ogg Video", VIDEO, "ogg", listOf("libtheora", "copy"), listOf("libvorbis", "libopus", "copy")),
        ContainerFormat("gif", "GIF 动画", VIDEO, "gif", listOf("gif")),
        ContainerFormat("webp", "WebP 动图", VIDEO, "webp", listOf("libwebp")),
        ContainerFormat("apng", "APNG 动图", VIDEO, "apng", listOf("apng")),
        ContainerFormat("mxf", "MXF 广播格式", VIDEO, "mxf", listOf("mpeg2video", "dnxhd", "libx264"), listOf("pcm_s16le")),
    )

    val AUDIO_FORMATS: List<ContainerFormat> = listOf(
        ContainerFormat("mp3", "MP3", AUDIO, "mp3", emptyList(), listOf("libmp3lame")),
        ContainerFormat("aac", "AAC (ADTS)", AUDIO, "adts", emptyList(), listOf("aac")),
        ContainerFormat("m4a", "M4A / AAC-ALAC", AUDIO, "ipod", emptyList(), listOf("aac", "alac", "copy")),
        ContainerFormat("flac", "FLAC 无损", AUDIO, "flac", emptyList(), listOf("flac")),
        ContainerFormat("wav", "WAV (PCM)", AUDIO, "wav", emptyList(), listOf("pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm_u8")),
        ContainerFormat("ogg", "Ogg Vorbis", AUDIO, "ogg", emptyList(), listOf("libvorbis", "libopus", "flac")),
        ContainerFormat("opus", "Opus", AUDIO, "opus", emptyList(), listOf("libopus")),
        ContainerFormat("wma", "Windows Media Audio", AUDIO, "asf", emptyList(), listOf("wmav2")),
        ContainerFormat("aiff", "AIFF", AUDIO, "aiff", emptyList(), listOf("pcm_s16be", "pcm_s24be")),
        ContainerFormat("ac3", "Dolby AC-3", AUDIO, "ac3", emptyList(), listOf("ac3")),
        ContainerFormat("eac3", "Dolby Digital Plus", AUDIO, "eac3", emptyList(), listOf("eac3")),
        ContainerFormat("amr", "AMR-NB 语音", AUDIO, "amr", emptyList(), listOf("amr_nb")),
        ContainerFormat("mka", "Matroska Audio", AUDIO, "matroska", emptyList(), listOf("flac", "libopus", "aac", "libmp3lame", "copy")),
        ContainerFormat("caf", "Apple CAF", AUDIO, "caf", emptyList(), listOf("alac", "pcm_s16le", "aac")),
        ContainerFormat("au", "Sun AU", AUDIO, "au", emptyList(), listOf("pcm_s16be")),
        ContainerFormat("mp2", "MPEG Audio Layer II", AUDIO, "mp2", emptyList(), listOf("mp2")),
        ContainerFormat("spx", "Speex", AUDIO, "ogg", emptyList(), listOf("libspeex")),
        ContainerFormat("tta", "True Audio 无损", AUDIO, "tta", emptyList(), listOf("tta")),
        ContainerFormat("wv", "WavPack 无损", AUDIO, "wv", emptyList(), listOf("wavpack")),
    )

    val IMAGE_FORMATS: List<ContainerFormat> = listOf(
        ContainerFormat("jpg", "JPEG", IMAGE),
        ContainerFormat("jpeg", "JPEG (.jpeg)", IMAGE),
        ContainerFormat("png", "PNG", IMAGE),
        ContainerFormat("webp", "WebP", IMAGE),
        ContainerFormat("avif", "AVIF", IMAGE),
        ContainerFormat("heif", "HEIF/HEIC", IMAGE),
        ContainerFormat("bmp", "BMP 位图", IMAGE),
        ContainerFormat("gif", "GIF", IMAGE),
        ContainerFormat("tiff", "TIFF", IMAGE),
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

    val INPUT_VIDEO_EXT: Set<String> = VIDEO_FORMATS.map { it.ext }.toSet() + setOf(
        "m2ts", "mts", "vob", "rmvb", "rm", "asf", "divx", "f4v", "h264", "hevc",
        "m2v", "mpeg", "mpv", "ogm", "swf", "y4m", "dv", "amv", "nut")
    val INPUT_AUDIO_EXT: Set<String> = AUDIO_FORMATS.map { it.ext }.toSet() + setOf(
        "ape", "dts", "mpc", "ra", "shn", "voc", "w64", "gsm", "oga", "m4b", "8svx")
    val INPUT_IMAGE_EXT: Set<String> = IMAGE_FORMATS.map { it.ext }.toSet() + setOf(
        "heic", "jfif", "pbm", "xbm", "xpm", "blp", "cur", "fits", "icns", "j2k",
        "jpf", "jpx", "msp", "pfm", "psd", "qoi", "svg", "wmf", "emf")

    // ------------------------------------------------------------------
    // 编码器参数
    // ------------------------------------------------------------------
    private val X26X_PRESETS = listOf("ultrafast", "superfast", "veryfast", "faster", "fast",
        "medium", "slow", "slower", "veryslow", "placebo")
    private val X264_TUNES = listOf("", "film", "animation", "grain", "stillimage", "fastdecode",
        "zerolatency", "psnr", "ssim")

    private fun rateParams(defaultCrf: Double, crfMax: Double = 63.0, crfLabel: String = "CRF 质量"): List<Param> = listOf(
        Param("rate_mode", "码率控制模式", "choice", "crf",
            listOf("crf", "cbr", "vbr", "cq", "lossless"),
            help = "crf=恒定质量；cbr=恒定码率；vbr=平均码率；cq=恒定量化；lossless=无损"),
        Param("crf", crfLabel, "float", defaultCrf, min = 0.0, max = crfMax),
        Param("bitrate", "目标码率", "str", "", help = "如 4000k、8M；CBR/VBR 模式下使用"),
        Param("maxrate", "最大码率", "str", ""),
        Param("bufsize", "缓冲区大小", "str", ""),
        Param("minrate", "最小码率", "str", ""),
        Param("two_pass", "两遍编码", "bool", false),
    )

    val VIDEO_CODECS: Map<String, Codec>
    val AUDIO_CODECS: Map<String, Codec>

    private val A_COMMON = listOf(
        Param("audio_bitrate", "音频码率", "str", "192k"),
        Param("sample_rate", "采样率 Hz", "choice", "", listOf("", "8000", "11025", "16000", "22050", "32000",
            "44100", "48000", "88200", "96000", "176400", "192000")),
        Param("channels", "声道数", "choice", "", listOf("", "1", "2", "4", "6", "8")),
        Param("volume", "音量调整 dB", "float", 0.0, min = -40.0, max = 40.0, step = 0.5),
    )

    init {
        val v = mutableListOf<Codec>()
        v += Codec("libx264", "H.264 / AVC (libx264)", VIDEO, rateParams(23.0, 51.0) + listOf(
            Param("preset", "编码预设", "choice", "medium", X26X_PRESETS),
            Param("tune", "调优", "choice", "", X264_TUNES),
            Param("profile", "Profile", "choice", "", listOf("", "baseline", "main", "high", "high10", "high422", "high444")),
            Param("level", "Level", "choice", "", listOf("", "3.0", "3.1", "4.0", "4.1", "4.2", "5.0", "5.1", "5.2", "6.0", "6.2")),
            Param("pix_fmt", "像素格式", "choice", "yuv420p", listOf("yuv420p", "yuv422p", "yuv444p", "yuv420p10le", "yuv444p10le", "nv12")),
            Param("gop", "关键帧间隔 GOP", "int", 0, min = 0.0, max = 1200.0),
            Param("bframes", "B 帧数量", "int", -1, min = -1.0, max = 16.0),
            Param("refs", "参考帧数量", "int", 0, min = 0.0, max = 16.0),
            Param("x264_params", "x264 额外参数", "str", ""),
        ))
        v += Codec("libx265", "H.265 / HEVC (libx265)", VIDEO, rateParams(28.0, 51.0) + listOf(
            Param("preset", "编码预设", "choice", "medium", X26X_PRESETS),
            Param("tune", "调优", "choice", "", listOf("", "psnr", "ssim", "grain", "fastdecode", "zerolatency", "animation")),
            Param("profile", "Profile", "choice", "", listOf("", "main", "main10", "main12", "main444-8")),
            Param("pix_fmt", "像素格式", "choice", "yuv420p", listOf("yuv420p", "yuv420p10le", "yuv422p10le", "yuv444p10le")),
            Param("gop", "关键帧间隔 GOP", "int", 0, min = 0.0, max = 1200.0),
            Param("x265_params", "x265 额外参数", "str", ""),
        ))
        v += Codec("libsvtav1", "AV1 (SVT-AV1，快)", VIDEO, rateParams(35.0, 63.0) + listOf(
            Param("preset", "速度预设 0-13", "int", 8, min = 0.0, max = 13.0),
            Param("pix_fmt", "像素格式", "choice", "yuv420p", listOf("yuv420p", "yuv420p10le")),
            Param("gop", "关键帧间隔 GOP", "int", 0, min = 0.0, max = 1200.0),
            Param("svtav1_params", "SVT-AV1 额外参数", "str", ""),
        ))
        v += Codec("libaom-av1", "AV1 (libaom，慢/高质量)", VIDEO, rateParams(30.0, 63.0) + listOf(
            Param("cpu_used", "cpu-used 0-8", "int", 4, min = 0.0, max = 8.0),
            Param("row_mt", "行多线程", "bool", true),
            Param("tiles", "分块 tiles", "str", ""),
            Param("pix_fmt", "像素格式", "choice", "yuv420p", listOf("yuv420p", "yuv420p10le", "yuv422p", "yuv444p")),
        ))
        v += Codec("libvpx-vp9", "VP9 (libvpx)", VIDEO, rateParams(31.0, 63.0) + listOf(
            Param("cpu_used", "cpu-used -8~8", "int", 1, min = -8.0, max = 8.0),
            Param("row_mt", "行多线程", "bool", true),
            Param("deadline", "编码模式", "choice", "good", listOf("good", "best", "realtime")),
            Param("pix_fmt", "像素格式", "choice", "yuv420p", listOf("yuv420p", "yuv422p", "yuv444p", "yuv420p10le")),
        ))
        v += Codec("libvpx", "VP8 (libvpx)", VIDEO, rateParams(10.0, 63.0) + listOf(
            Param("cpu_used", "cpu-used", "int", 1, min = -16.0, max = 16.0),
            Param("pix_fmt", "像素格式", "choice", "yuv420p", listOf("yuv420p")),
        ))
        v += Codec("mpeg4", "MPEG-4 Part 2", VIDEO, rateParams(6.0, 31.0, "量化 qscale") + listOf(
            Param("pix_fmt", "像素格式", "choice", "yuv420p", listOf("yuv420p"))))
        v += Codec("libxvid", "Xvid", VIDEO, rateParams(6.0, 31.0, "量化 qscale"))
        v += Codec("mpeg2video", "MPEG-2", VIDEO, rateParams(5.0, 31.0, "量化 qscale"))
        v += Codec("mpeg1video", "MPEG-1", VIDEO, rateParams(5.0, 31.0, "量化 qscale"))
        v += Codec("libtheora", "Theora", VIDEO, rateParams(7.0, 10.0, "质量 qscale"))
        v += Codec("wmv2", "Windows Media Video 8", VIDEO, rateParams(5.0, 31.0, "量化 qscale"))
        v += Codec("msmpeg4v3", "MS MPEG-4 v3 (DivX3)", VIDEO, rateParams(5.0, 31.0, "量化 qscale"))
        v += Codec("h263", "H.263", VIDEO, rateParams(5.0, 31.0, "量化 qscale"))
        v += Codec("flv", "Sorenson Spark (FLV1)", VIDEO, rateParams(5.0, 31.0, "量化 qscale"))
        v += Codec("huffyuv", "HuffYUV 无损", VIDEO)
        v += Codec("prores_ks", "Apple ProRes", VIDEO, listOf(
            Param("profile", "ProRes Profile", "choice", "3", listOf("0", "1", "2", "3", "4", "5")),
            Param("pix_fmt", "像素格式", "choice", "yuv422p10le", listOf("yuv422p10le", "yuv444p10le", "yuva444p10le")),
            Param("qscale", "质量 qscale", "int", 9, min = 0.0, max = 32.0),
        ))
        v += Codec("dnxhd", "Avid DNxHD/DNxHR", VIDEO, listOf(
            Param("profile", "DNxHR Profile", "choice", "dnxhr_hq", listOf("dnxhr_lb", "dnxhr_sq", "dnxhr_hq", "dnxhr_hqx", "dnxhr_444")),
            Param("pix_fmt", "像素格式", "choice", "yuv422p", listOf("yuv422p", "yuv422p10le", "yuv444p10le")),
        ))
        v += Codec("gif", "GIF 编码", VIDEO, listOf(
            Param("gif_palette", "生成最优调色板", "bool", true),
            Param("gif_dither", "抖动算法", "choice", "sierra2_4a",
                listOf("none", "bayer", "floyd_steinberg", "sierra2", "sierra2_4a")),
            Param("gif_max_colors", "最大颜色数", "int", 256, min = 2.0, max = 256.0),
            Param("gif_loop", "循环次数", "int", 0, min = -1.0, max = 1000.0),
        ))
        v += Codec("libwebp", "WebP 动图编码", VIDEO, listOf(
            Param("quality", "质量 0-100", "int", 75, min = 0.0, max = 100.0),
            Param("lossless", "无损", "bool", false),
            Param("compression_level", "压缩级别 0-6", "int", 4, min = 0.0, max = 6.0),
            Param("gif_loop", "循环次数", "int", 0, min = -1.0, max = 1000.0),
        ))
        v += Codec("apng", "APNG 编码", VIDEO, listOf(
            Param("gif_loop", "循环次数", "int", 0, min = 0.0, max = 1000.0)))
        v += Codec("copy", "直接复制视频流（不重编码）", VIDEO)
        for ((hw, label) in listOf(
            "h264_nvenc" to "H.264 (NVIDIA NVENC)", "hevc_nvenc" to "H.265 (NVIDIA NVENC)",
            "av1_nvenc" to "AV1 (NVIDIA NVENC)", "h264_qsv" to "H.264 (Intel QuickSync)",
            "hevc_qsv" to "H.265 (Intel QuickSync)", "av1_qsv" to "AV1 (Intel QuickSync)",
            "h264_amf" to "H.264 (AMD AMF)", "hevc_amf" to "H.265 (AMD AMF)",
            "av1_amf" to "AV1 (AMD AMF)")) {
            v += Codec(hw, label, VIDEO, listOf(
                Param("rate_mode", "码率控制模式", "choice", "cq", listOf("cq", "cbr", "vbr")),
                Param("crf", "质量 CQ/QP", "float", 23.0, min = 0.0, max = 51.0),
                Param("bitrate", "目标码率", "str", "6000k"),
                Param("maxrate", "最大码率", "str", ""),
                Param("bufsize", "缓冲区大小", "str", ""),
                Param("preset", "硬件预设", "choice", "", listOf("", "p1", "p2", "p3", "p4", "p5", "p6", "p7",
                    "quality", "balanced", "speed", "veryfast", "slow")),
                Param("pix_fmt", "像素格式", "choice", "yuv420p", listOf("yuv420p", "p010le", "nv12", "yuv444p")),
                Param("gop", "关键帧间隔 GOP", "int", 0, min = 0.0, max = 1200.0),
            ), hardware = true)
        }
        VIDEO_CODECS = v.associateBy { it.encoder }

        val a = mutableListOf<Codec>()
        a += Codec("libmp3lame", "MP3 (LAME)", AUDIO, A_COMMON + listOf(
            Param("audio_mode", "码率模式", "choice", "cbr", listOf("cbr", "vbr", "abr")),
            Param("mp3_vbr_quality", "VBR 质量 0-9", "int", 2, min = 0.0, max = 9.0),
            Param("joint_stereo", "联合立体声", "bool", true),
        ))
        a += Codec("aac", "AAC-LC (原生)", AUDIO, A_COMMON + listOf(
            Param("audio_mode", "码率模式", "choice", "cbr", listOf("cbr", "vbr")),
            Param("aac_vbr_quality", "VBR 质量 1-5", "int", 4, min = 1.0, max = 5.0),
            Param("aac_profile", "AAC Profile", "choice", "aac_low", listOf("aac_low", "mpeg2_aac_low", "aac_ltp", "aac_main")),
        ))
        a += Codec("libfdk_aac", "AAC (libfdk，需支持)", AUDIO, A_COMMON + listOf(
            Param("audio_mode", "码率模式", "choice", "cbr", listOf("cbr", "vbr")),
            Param("fdk_vbr", "VBR 等级 1-5", "int", 4, min = 1.0, max = 5.0),
            Param("he_aac", "HE-AAC", "choice", "", listOf("", "aac_he", "aac_he_v2")),
        ))
        a += Codec("libopus", "Opus", AUDIO, A_COMMON + listOf(
            Param("audio_mode", "码率模式", "choice", "vbr", listOf("vbr", "cvbr", "cbr")),
            Param("opus_application", "应用场景", "choice", "audio", listOf("audio", "voip", "lowdelay")),
            Param("opus_compression", "压缩级别 0-10", "int", 10, min = 0.0, max = 10.0),
            Param("frame_duration", "帧长 ms", "choice", "20", listOf("2.5", "5", "10", "20", "40", "60")),
        ))
        a += Codec("libvorbis", "Vorbis", AUDIO, A_COMMON + listOf(
            Param("audio_mode", "码率模式", "choice", "vbr", listOf("vbr", "cbr")),
            Param("vorbis_quality", "VBR 质量 -1~10", "float", 5.0, min = -1.0, max = 10.0, step = 0.5),
        ))
        a += Codec("flac", "FLAC 无损", AUDIO, listOf(
            Param("sample_rate", "采样率 Hz", "choice", "", listOf("", "44100", "48000", "88200", "96000", "192000")),
            Param("channels", "声道数", "choice", "", listOf("", "1", "2", "6", "8")),
            Param("volume", "音量调整 dB", "float", 0.0, min = -40.0, max = 40.0, step = 0.5),
            Param("compression_level", "压缩级别 0-12", "int", 5, min = 0.0, max = 12.0),
            Param("sample_fmt", "采样格式", "choice", "s16", listOf("s16", "s32")),
        ))
        a += Codec("alac", "Apple 无损 ALAC", AUDIO, listOf(
            Param("sample_rate", "采样率 Hz", "choice", "", listOf("", "44100", "48000", "96000", "192000")),
            Param("channels", "声道数", "choice", "", listOf("", "1", "2", "6")),
            Param("volume", "音量调整 dB", "float", 0.0, min = -40.0, max = 40.0, step = 0.5),
        ))
        for ((pcm, lbl) in listOf("pcm_s16le" to "PCM 16-bit", "pcm_s24le" to "PCM 24-bit",
            "pcm_s32le" to "PCM 32-bit", "pcm_f32le" to "PCM 32-bit 浮点",
            "pcm_u8" to "PCM 8-bit 无符号", "pcm_s16be" to "PCM 16-bit 大端",
            "pcm_s24be" to "PCM 24-bit 大端")) {
            a += Codec(pcm, lbl, AUDIO, listOf(
                Param("sample_rate", "采样率 Hz", "choice", "", listOf("", "8000", "16000", "22050", "44100", "48000", "96000", "192000")),
                Param("channels", "声道数", "choice", "", listOf("", "1", "2", "6", "8")),
                Param("volume", "音量调整 dB", "float", 0.0, min = -40.0, max = 40.0, step = 0.5),
            ))
        }
        a += Codec("ac3", "Dolby AC-3", AUDIO, A_COMMON)
        a += Codec("eac3", "Dolby Digital Plus", AUDIO, A_COMMON)
        a += Codec("wmav2", "WMA v2", AUDIO, A_COMMON)
        a += Codec("mp2", "MPEG Audio Layer II", AUDIO, A_COMMON)
        a += Codec("amr_nb", "AMR 窄带语音", AUDIO, listOf(
            Param("audio_bitrate", "音频码率", "str", "12.2k"),
            Param("sample_rate", "采样率 Hz", "choice", "8000", listOf("8000")),
            Param("channels", "声道数", "choice", "1", listOf("1")),
        ))
        a += Codec("libspeex", "Speex 语音", AUDIO, A_COMMON)
        a += Codec("tta", "True Audio 无损", AUDIO)
        a += Codec("wavpack", "WavPack 无损", AUDIO, listOf(
            Param("compression_level", "压缩级别 0-8", "int", 2, min = 0.0, max = 8.0)))
        a += Codec("copy", "直接复制音频流（不重编码）", AUDIO)
        AUDIO_CODECS = a.associateBy { it.encoder }
    }

    // ------------------------------------------------------------------
    // 通用处理参数
    // ------------------------------------------------------------------
    val VIDEO_FILTER_PARAMS: List<Param> = listOf(
        Param("width", "宽度 px", "int", 0, min = 0.0, max = 16384.0),
        Param("height", "高度 px", "int", 0, min = 0.0, max = 16384.0),
        Param("keep_aspect", "保持宽高比", "bool", true),
        Param("scale_flags", "缩放算法", "choice", "bicubic",
            listOf("fast_bilinear", "bilinear", "bicubic", "neighbor", "area", "bicublin", "gauss", "sinc", "lanczos", "spline")),
        Param("fps", "帧率 fps", "str", ""),
        Param("crop", "裁剪", "str", "", help = "格式 w:h:x:y"),
        Param("pad", "填充", "str", "", help = "格式 w:h:x:y:color"),
        Param("rotate", "旋转", "choice", "0", listOf("0", "90", "180", "270")),
        Param("hflip", "水平翻转", "bool", false),
        Param("vflip", "垂直翻转", "bool", false),
        Param("deinterlace", "去隔行 (yadif)", "bool", false),
        Param("denoise", "降噪强度", "choice", "", listOf("", "light", "medium", "strong")),
        Param("sharpen", "锐化", "bool", false),
        Param("brightness", "亮度 -1~1", "float", 0.0, min = -1.0, max = 1.0, step = 0.05),
        Param("contrast", "对比度 0~4", "float", 1.0, min = 0.0, max = 4.0, step = 0.05),
        Param("saturation", "饱和度 0~3", "float", 1.0, min = 0.0, max = 3.0, step = 0.05),
        Param("gamma", "伽马 0.1~10", "float", 1.0, min = 0.1, max = 10.0, step = 0.05),
        Param("video_filter", "自定义视频滤镜链", "str", ""),
    )

    val AUDIO_FILTER_PARAMS: List<Param> = listOf(
        Param("normalize", "响度归一化 (EBU R128)", "bool", false),
        Param("loudness_target", "目标响度 LUFS", "float", -16.0, min = -70.0, max = -5.0, step = 0.5),
        Param("audio_fade_in", "淡入秒数", "float", 0.0, min = 0.0, max = 60.0, step = 0.1),
        Param("audio_fade_out", "淡出秒数", "float", 0.0, min = 0.0, max = 60.0, step = 0.1),
        Param("tempo", "变速倍率（不变调）", "float", 1.0, min = 0.5, max = 2.0, step = 0.05),
        Param("pitch_semitones", "变调半音", "float", 0.0, min = -12.0, max = 12.0, step = 1.0),
        Param("audio_filter", "自定义音频滤镜链", "str", ""),
    )

    val GENERAL_PARAMS: List<Param> = listOf(
        Param("start_time", "起始时间", "str", ""),
        Param("end_time", "结束时间", "str", ""),
        Param("duration", "截取时长", "str", ""),
        Param("threads", "线程数", "int", 0, min = 0.0, max = 64.0),
        Param("overwrite", "覆盖已存在文件", "bool", true),
        Param("strip_metadata", "移除元数据", "bool", false),
        Param("copy_chapters", "保留章节", "bool", true),
        Param("subtitle_mode", "字幕处理", "choice", "copy", listOf("copy", "none", "burn")),
        Param("subtitle_file", "外挂字幕文件", "str", ""),
        Param("faststart", "MP4 faststart", "bool", true),
        Param("hwaccel", "解码硬件加速", "choice", "", listOf("", "auto", "cuda", "qsv", "d3d11va", "dxva2", "vulkan")),
        Param("extra_args", "自定义 ffmpeg 参数", "str", ""),
    )

    val IMAGE_PARAMS: List<Param> = listOf(
        Param("width", "宽度 px", "int", 0, min = 0.0, max = 60000.0),
        Param("height", "高度 px", "int", 0, min = 0.0, max = 60000.0),
        Param("keep_aspect", "保持宽高比", "bool", true),
        Param("resample", "重采样算法", "choice", "lanczos",
            listOf("nearest", "box", "bilinear", "hamming", "bicubic", "lanczos")),
        Param("quality", "质量 1-100", "int", 90, min = 1.0, max = 100.0),
        Param("lossless", "无损模式", "bool", false),
        Param("optimize", "优化体积", "bool", true),
        Param("progressive", "渐进式 JPEG", "bool", false),
        Param("subsampling", "色度抽样", "choice", "auto", listOf("auto", "4:4:4", "4:2:2", "4:2:0")),
        Param("png_compress_level", "PNG 压缩级别 0-9", "int", 6, min = 0.0, max = 9.0),
        Param("webp_method", "WebP 压缩方法 0-6", "int", 4, min = 0.0, max = 6.0),
        Param("avif_speed", "AVIF 速度 0-10", "int", 6, min = 0.0, max = 10.0),
        Param("tiff_compression", "TIFF 压缩", "choice", "tiff_deflate",
            listOf("none", "tiff_lzw", "tiff_deflate", "jpeg", "packbits")),
        Param("color_mode", "颜色模式", "choice", "", listOf("", "RGB", "RGBA", "L", "LA", "CMYK", "P", "1")),
        Param("bit_depth", "调色板位深", "choice", "", listOf("", "1", "2", "4", "8")),
        Param("dpi", "DPI", "int", 0, min = 0.0, max = 4800.0),
        Param("background", "透明背景填充色", "str", "#FFFFFF"),
        Param("rotate", "旋转", "choice", "0", listOf("0", "90", "180", "270")),
        Param("hflip", "水平翻转", "bool", false),
        Param("vflip", "垂直翻转", "bool", false),
        Param("auto_orient", "按 EXIF 自动摆正", "bool", true),
        Param("strip_metadata", "移除 EXIF/元数据", "bool", false),
        Param("keep_icc", "保留 ICC 色彩配置", "bool", true),
        Param("brightness", "亮度倍率", "float", 1.0, min = 0.0, max = 3.0, step = 0.05),
        Param("contrast", "对比度倍率", "float", 1.0, min = 0.0, max = 3.0, step = 0.05),
        Param("saturation", "饱和度倍率", "float", 1.0, min = 0.0, max = 3.0, step = 0.05),
        Param("sharpness", "锐度倍率", "float", 1.0, min = 0.0, max = 3.0, step = 0.05),
        Param("blur", "高斯模糊半径", "float", 0.0, min = 0.0, max = 50.0, step = 0.5),
        Param("grayscale", "转灰度", "bool", false),
        Param("ico_sizes", "ICO 尺寸集合", "str", "16,32,48,64,128,256"),
        Param("overwrite", "覆盖已存在文件", "bool", true),
    )

    val ALL_FORMATS: List<ContainerFormat> = VIDEO_FORMATS + AUDIO_FORMATS + IMAGE_FORMATS

    fun formatsFor(kind: String): List<ContainerFormat> = when (kind) {
        VIDEO -> VIDEO_FORMATS
        AUDIO -> AUDIO_FORMATS
        else -> IMAGE_FORMATS
    }

    fun findFormat(ext: String): ContainerFormat? {
        val e = ext.lowercase().removePrefix(".")
        return ALL_FORMATS.firstOrNull { it.ext == e }
    }

    fun detectKind(path: String): String {
        val ext = path.substringAfterLast('.', "").lowercase()
        val animated = ext in setOf("gif", "webp", "apng")
        if (ext in INPUT_IMAGE_EXT && !animated) return IMAGE
        if (ext in INPUT_VIDEO_EXT) return VIDEO
        if (ext in INPUT_AUDIO_EXT) return AUDIO
        if (ext in INPUT_IMAGE_EXT) return IMAGE
        return VIDEO
    }

    fun codecParams(encoder: String): List<Param> =
        VIDEO_CODECS[encoder]?.params ?: AUDIO_CODECS[encoder]?.params ?: emptyList()

    fun defaultParamsFor(kind: String): MutableMap<String, Any?> {
        val pool = if (kind == IMAGE) IMAGE_PARAMS
        else GENERAL_PARAMS + VIDEO_FILTER_PARAMS + AUDIO_FILTER_PARAMS
        return pool.associate { it.key to it.default }.toMutableMap()
    }
}
