package cn.mediaforge.app

import kotlin.math.abs
import kotlin.math.pow

/** 参数字典 → ffmpeg 命令行（桌面版 app/core/ffmpeg_builder.py 的 Kotlin 移植）。 */
object Builder {

    fun s(p: Map<String, Any?>, key: String, default: String = ""): String {
        val v = p[key] ?: return default
        return v.toString().trim()
    }

    fun f(p: Map<String, Any?>, key: String, default: Double = 0.0): Double = try {
        (p[key] ?: default).toString().trim().toDouble()
    } catch (e: Exception) { default }

    fun i(p: Map<String, Any?>, key: String, default: Int = 0): Int = try {
        ((p[key] ?: default).toString().trim().toDouble()).toInt()
    } catch (e: Exception) { default }

    fun b(p: Map<String, Any?>, key: String, default: Boolean = false): Boolean {
        val v = p[key] ?: return default
        if (v is Boolean) return v
        return v.toString().trim().lowercase() in setOf("1", "true", "yes", "on")
    }

    /** 转义 filtergraph 中的路径特殊字符（字幕路径可能含 : ' [ ] , ;）。 */
    fun escapeFilterPath(p: String): String =
        p.replace("\\", "/")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace(",", "\\,")
            .replace(";", "\\;")

    fun buildVideoFilters(p: Map<String, Any?>): List<String> {
        val chain = mutableListOf<String>()
        if (b(p, "deinterlace")) chain += "yadif=mode=0:parity=-1:deint=0"
        val crop = s(p, "crop")
        if (crop.isNotEmpty()) chain += "crop=$crop"

        val w = i(p, "width"); val h = i(p, "height")
        if (w != 0 || h != 0) {
            val flags = s(p, "scale_flags", "bicubic").ifEmpty { "bicubic" }
            if (b(p, "keep_aspect", true) && w != 0 && h != 0) {
                chain += "scale=$w:$h:force_original_aspect_ratio=decrease:flags=$flags"
                chain += "pad=$w:$h:(ow-iw)/2:(oh-ih)/2"
            } else {
                val sw = if (w != 0) "$w" else "-2"
                val sh = if (h != 0) "$h" else "-2"
                chain += "scale=$sw:$sh:flags=$flags"
            }
        }
        val pad = s(p, "pad")
        if (pad.isNotEmpty()) chain += "pad=$pad"

        when (s(p, "rotate", "0")) {
            "90" -> chain += "transpose=1"
            "180" -> chain += "transpose=1,transpose=1"
            "270" -> chain += "transpose=2"
        }
        if (b(p, "hflip")) chain += "hflip"
        if (b(p, "vflip")) chain += "vflip"

        when (s(p, "denoise")) {
            "light" -> chain += "hqdn3d=2:1:2:3"
            "medium" -> chain += "hqdn3d=4:3:6:4.5"
            "strong" -> chain += "hqdn3d=8:6:12:9"
        }
        if (b(p, "sharpen")) chain += "unsharp=5:5:0.8:3:3:0.4"

        val eq = mutableListOf<String>()
        if (abs(f(p, "brightness")) > 1e-6) eq += "brightness=${fmt(f(p, "brightness"))}"
        if (abs(f(p, "contrast", 1.0)) > 1e-6) eq += "contrast=${fmt(f(p, "contrast", 1.0))}"
        if (abs(f(p, "saturation", 1.0)) > 1e-6) eq += "saturation=${fmt(f(p, "saturation", 1.0))}"
        if (abs(f(p, "gamma", 1.0)) > 1e-6) eq += "gamma=${fmt(f(p, "gamma", 1.0))}"
        if (eq.isNotEmpty()) chain += "eq=" + eq.joinToString(":")

        val fps = s(p, "fps")
        if (fps.isNotEmpty()) chain += "fps=$fps"

        if (p["subtitle_mode"] == "burn") {
            val sub = s(p, "subtitle_file")
            if (sub.isNotEmpty()) chain += "subtitles='${escapeFilterPath(sub)}'"
        }
        val custom = s(p, "video_filter")
        if (custom.isNotEmpty()) chain += custom
        return chain.filter { it.isNotEmpty() }
    }

    fun buildAudioFilters(p: Map<String, Any?>): List<String> {
        val chain = mutableListOf<String>()
        val vol = f(p, "volume")
        if (abs(vol) > 1e-6) chain += "volume=${fmt(vol)}dB"

        if (b(p, "normalize")) {
            val target = f(p, "loudness_target", -16.0)
            chain += "loudnorm=I=${fmt(target)}:TP=-1.5:LRA=11"
            val back = s(p, "sample_rate").ifEmpty { "${i(p, "_sample_rate", 48000).let { if (it == 0) 48000 else it }}" }
            chain += "aresample=$back"
        }

        var tempo = f(p, "tempo", 1.0)
        if (abs(tempo - 1.0) > 1e-6) {
            while (tempo > 2.0) { chain += "atempo=2.0"; tempo /= 2.0 }
            while (tempo < 0.5) { chain += "atempo=0.5"; tempo /= 0.5 }
            chain += "atempo=${fmt(tempo)}"
        }

        val baseSr = i(p, "_sample_rate", 48000).let { if (it == 0) 48000 else it }
        val semis = f(p, "pitch_semitones")
        if (abs(semis) > 1e-6) {
            val ratio = 2.0.pow(semis / 12.0)
            chain += "asetrate=$baseSr*${fmt(ratio)},aresample=$baseSr,atempo=${fmt(1 / ratio)}"
        }

        val fi = f(p, "audio_fade_in")
        if (fi > 0) chain += "afade=t=in:st=0:d=${fmt(fi)}"
        val fo = f(p, "audio_fade_out")
        if (fo > 0 && p["_duration"] != null) {
            val dur = f(p, "_duration")
            val start = maxOf(0.0, dur - fo)
            chain += "afade=t=out:st=${fmt(start)}:d=${fmt(fo)}"
        }

        val sr = s(p, "sample_rate")
        if (sr.isNotEmpty()) chain += "aresample=$sr"
        val custom = s(p, "audio_filter")
        if (custom.isNotEmpty()) chain += custom
        return chain.filter { it.isNotEmpty() }
    }

    private val QSCALE_CODECS = setOf("mpeg4", "libxvid", "mpeg2video", "mpeg1video", "libtheora",
        "wmv2", "msmpeg4v3", "h263", "flv")

    private fun doubleRate(rate: String): String = try {
        val num = rate.filter { it.isDigit() || it == '.' }.toDouble()
        val suffix = rate.filter { it.isLetter() }
        val doubled = num * 2
        "${if (doubled == doubled.toLong().toDouble()) doubled.toLong().toString() else doubled.toString()}$suffix"
    } catch (e: Exception) { rate }

    private fun fmt(v: Double): String =
        if (v == v.toLong().toDouble()) v.toLong().toString() else v.toString()

    fun videoEncoderArgs(enc: String, p: Map<String, Any?>, passNo: Int = 0): List<String> {
        val args = mutableListOf("-c:v", enc)
        if (enc == "copy") return args

        var mode = s(p, "rate_mode", "crf").ifEmpty { "crf" }
        val crf = f(p, "crf", 23.0)
        val bitrate = s(p, "bitrate")
        if (passNo != 0 && bitrate.isNotEmpty() && mode in setOf("crf", "cq", "lossless")) mode = "vbr"

        when {
            enc in setOf("libx264", "libx265") -> {
                when {
                    mode == "lossless" -> if (enc == "libx264") args += listOf("-crf", "0")
                    else args += listOf("-x265-params", "lossless=1")
                    mode in setOf("cbr", "vbr") && bitrate.isNotEmpty() -> {
                        args += listOf("-b:v", bitrate)
                        if (mode == "cbr") args += listOf("-maxrate", bitrate, "-bufsize",
                            s(p, "bufsize").ifEmpty { doubleRate(bitrate) }, "-nal-hrd", "cbr")
                    }
                    else -> args += listOf("-crf", fmt(crf))
                }
                s(p, "preset").let { if (it.isNotEmpty()) args += listOf("-preset", it) }
                s(p, "tune").let { if (it.isNotEmpty()) args += listOf("-tune", it) }
                s(p, "profile").let { if (it.isNotEmpty()) args += listOf("-profile:v", it) }
                s(p, "level").let { if (it.isNotEmpty()) args += listOf("-level", it) }
                if (i(p, "bframes", -1) >= 0) args += listOf("-bf", "${i(p, "bframes", -1)}")
                if (i(p, "refs") > 0) args += listOf("-refs", "${i(p, "refs")}")
                val extra = if (enc == "libx264") s(p, "x264_params") else s(p, "x265_params")
                if (extra.isNotEmpty()) args += listOf(
                    if (enc == "libx264") "-x264-params" else "-x265-params", extra)
            }
            enc == "libsvtav1" -> {
                if (mode in setOf("cbr", "vbr") && bitrate.isNotEmpty()) args += listOf("-b:v", bitrate)
                else args += listOf("-crf", fmt(crf))
                args += listOf("-preset", "${i(p, "preset", 8)}")
                s(p, "svtav1_params").let { if (it.isNotEmpty()) args += listOf("-svtav1-params", it) }
            }
            enc == "libaom-av1" -> {
                when {
                    mode == "lossless" -> args += listOf("-lossless", "1")
                    mode in setOf("cbr", "vbr") && bitrate.isNotEmpty() -> args += listOf("-b:v", bitrate)
                    else -> args += listOf("-crf", fmt(crf), "-b:v", "0")
                }
                args += listOf("-cpu-used", "${i(p, "cpu_used", 4)}")
                if (b(p, "row_mt", true)) args += listOf("-row-mt", "1")
                s(p, "tiles").let { if (it.isNotEmpty()) args += listOf("-tiles", it) }
            }
            enc in setOf("libvpx-vp9", "libvpx") -> {
                when {
                    mode == "lossless" && enc == "libvpx-vp9" -> args += listOf("-lossless", "1")
                    mode in setOf("cbr", "vbr") && bitrate.isNotEmpty() -> args += listOf("-b:v", bitrate)
                    else -> args += listOf("-crf", fmt(crf), "-b:v", "0")
                }
                args += listOf("-cpu-used", "${i(p, "cpu_used", 1)}")
                if (b(p, "row_mt", true) && enc == "libvpx-vp9") args += listOf("-row-mt", "1")
                s(p, "deadline").let { if (it.isNotEmpty()) args += listOf("-deadline", it) }
            }
            enc.endsWith("_nvenc") -> {
                when (mode) {
                    "cq" -> args += listOf("-rc", "vbr", "-cq", fmt(crf), "-b:v", bitrate.ifEmpty { "0" })
                    "cbr" -> args += listOf("-rc", "cbr", "-b:v", bitrate.ifEmpty { "6000k" })
                    else -> args += listOf("-rc", "vbr", "-b:v", bitrate.ifEmpty { "6000k" })
                }
                s(p, "preset").let { if (it.isNotEmpty()) args += listOf("-preset", it) }
            }
            enc.endsWith("_qsv") -> {
                if (mode == "cq") args += listOf("-global_quality", fmt(crf))
                else args += listOf("-b:v", bitrate.ifEmpty { "6000k" })
                s(p, "preset").let { if (it.isNotEmpty()) args += listOf("-preset", it) }
            }
            enc.endsWith("_amf") -> {
                if (mode == "cq") args += listOf("-rc", "cqp", "-qp_i", fmt(crf), "-qp_p", fmt(crf))
                else args += listOf("-rc", if (mode == "cbr") "cbr" else "vbr_peak",
                    "-b:v", bitrate.ifEmpty { "6000k" })
                s(p, "preset").let { if (it.isNotEmpty()) args += listOf("-quality", it) }
            }
            enc == "prores_ks" -> args += listOf("-profile:v", s(p, "profile", "3").ifEmpty { "3" },
                "-qscale:v", "${i(p, "qscale", 9)}")
            enc == "dnxhd" -> args += listOf("-profile:v", s(p, "profile", "dnxhr_hq").ifEmpty { "dnxhr_hq" })
            enc in QSCALE_CODECS -> if (bitrate.isNotEmpty()) args += listOf("-b:v", bitrate)
            else args += listOf("-qscale:v", fmt(crf))
            enc == "libwebp" -> {
                args += listOf("-quality", "${i(p, "quality", 75)}",
                    "-compression_level", "${i(p, "compression_level", 4)}")
                if (b(p, "lossless")) args += listOf("-lossless", "1")
            }
        }

        val maxrate = s(p, "maxrate")
        if (maxrate.isNotEmpty() && "-maxrate" !in args) args += listOf("-maxrate", maxrate)
        val bufsize = s(p, "bufsize")
        if (bufsize.isNotEmpty() && "-bufsize" !in args) args += listOf("-bufsize", bufsize)
        val minrate = s(p, "minrate")
        if (minrate.isNotEmpty()) args += listOf("-minrate", minrate)

        val pix = s(p, "pix_fmt")
        if (pix.isNotEmpty() && enc !in setOf("gif", "apng")) args += listOf("-pix_fmt", pix)
        val gop = i(p, "gop")
        if (gop > 0) args += listOf("-g", "$gop")
        if (passNo != 0) args += listOf("-pass", "$passNo")
        return args
    }

    fun audioEncoderArgs(enc: String, p: Map<String, Any?>): List<String> {
        if (enc == "copy") return listOf("-c:a", "copy")
        if (enc == "none") return listOf("-an")
        val args = mutableListOf("-c:a", enc)
        val mode = s(p, "audio_mode", "cbr")
        val br = s(p, "audio_bitrate")

        when {
            enc == "libmp3lame" -> {
                if (mode == "vbr") args += listOf("-q:a", "${i(p, "mp3_vbr_quality", 2)}")
                else {
                    args += listOf("-b:a", br.ifEmpty { "192k" })
                    if (mode == "abr") args += listOf("-abr", "1")
                }
                args += listOf("-joint_stereo", if (b(p, "joint_stereo", true)) "1" else "0")
            }
            enc in setOf("aac", "libfdk_aac") -> {
                if (mode == "vbr") {
                    if (enc == "libfdk_aac") args += listOf("-vbr", "${i(p, "fdk_vbr", 4)}")
                    else args += listOf("-q:a", "${i(p, "aac_vbr_quality", 4)}")
                } else args += listOf("-b:a", br.ifEmpty { "192k" })
                val prof = s(p, "he_aac").ifEmpty { s(p, "aac_profile") }
                if (prof.isNotEmpty() && prof != "aac_low") args += listOf("-profile:a", prof)
            }
            enc == "libopus" -> {
                args += listOf("-b:a", br.ifEmpty { "128k" })
                args += when (mode) {
                    "cbr" -> listOf("-vbr", "off")
                    "cvbr" -> listOf("-vbr", "constrained")
                    else -> listOf("-vbr", "on")
                }
                args += listOf("-application", s(p, "opus_application", "audio").ifEmpty { "audio" },
                    "-compression_level", "${i(p, "opus_compression", 10)}")
                s(p, "frame_duration").let { if (it.isNotEmpty()) args += listOf("-frame_duration", it) }
            }
            enc == "libvorbis" -> if (mode == "vbr") args += listOf("-q:a", fmt(f(p, "vorbis_quality", 5.0)))
            else args += listOf("-b:a", br.ifEmpty { "192k" })
            enc == "flac" -> {
                args += listOf("-compression_level", "${i(p, "compression_level", 5)}")
                s(p, "sample_fmt").let { if (it.isNotEmpty()) args += listOf("-sample_fmt", it) }
            }
            enc == "wavpack" -> args += listOf("-compression_level", "${i(p, "compression_level", 2)}")
            enc.startsWith("pcm_") || enc in setOf("alac", "tta") -> Unit
            else -> if (br.isNotEmpty()) args += listOf("-b:a", br)
        }

        s(p, "sample_rate").let { if (it.isNotEmpty()) args += listOf("-ar", it) }
        s(p, "channels").let { if (it.isNotEmpty()) args += listOf("-ac", it) }
        return args
    }

    /** 图片参数 → ffmpeg 参数（桌面版用 Pillow，移动端用 ffmpeg 图像编码器对齐主要能力）。 */
    fun imageArgs(p: Map<String, Any?>, outExt: String): List<String> {
        val args = mutableListOf<String>()
        val vf = mutableListOf<String>()
        val w = i(p, "width"); val h = i(p, "height")
        if (w != 0 || h != 0) {
            val flags = when (s(p, "resample", "lanczos")) {
                "nearest" -> "neighbor"; "box" -> "area"; "bilinear" -> "bilinear"
                "hamming" -> "hamming"; "bicubic" -> "bicubic"; else -> "lanczos"
            }
            if (b(p, "keep_aspect", true) && w != 0 && h != 0)
                vf += "scale=$w:$h:force_original_aspect_ratio=decrease:flags=$flags"
            else
                vf += "scale=${if (w != 0) "$w" else "-2"}:${if (h != 0) "$h" else "-2"}:flags=$flags"
        }
        when (s(p, "rotate", "0")) {
            "90" -> vf += "transpose=1"; "180" -> vf += "transpose=1,transpose=1"; "270" -> vf += "transpose=2"
        }
        if (b(p, "hflip")) vf += "hflip"
        if (b(p, "vflip")) vf += "vflip"
        val eq = mutableListOf<String>()
        // 桌面版图片亮度/对比度/饱和度为倍率（中性 1.0）；ffmpeg eq 亮度中性为 0，
        // 倍率→加法的近似映射：contrast/saturation 直接传，brightness 传 (v-1) 的缩放。
        val br = f(p, "brightness", 1.0)
        if (abs(br - 1.0) > 1e-6) eq += "brightness=${fmt((br - 1.0) * 0.5)}"
        val ct = f(p, "contrast", 1.0)
        if (abs(ct - 1.0) > 1e-6) eq += "contrast=${fmt(ct)}"
        val st = f(p, "saturation", 1.0)
        if (abs(st - 1.0) > 1e-6) eq += "saturation=${fmt(st)}"
        if (eq.isNotEmpty()) vf += "eq=" + eq.joinToString(":")
        val blur = f(p, "blur")
        if (blur > 0) vf += "gblur=sigma=${fmt(blur)}"
        if (b(p, "grayscale")) vf += "format=gray"
        if (vf.isNotEmpty()) args += listOf("-vf", vf.joinToString(","))

        when (outExt) {
            "jpg", "jpeg" -> {
                val q = i(p, "quality", 90)
                // mjpeg qscale 1(最好)~31(最差) 的近似映射
                args += listOf("-q:v", "${maxOf(1, minOf(31, (100 - q) / 3 + 1))}")
                when (s(p, "subsampling")) {
                    "4:4:4" -> args += listOf("-pix_fmt", "yuvj444p")
                    "4:2:2" -> args += listOf("-pix_fmt", "yuvj422p")
                    "4:2:0" -> args += listOf("-pix_fmt", "yuvj420p")
                }
            }
            "webp" -> {
                args += listOf("-quality", "${i(p, "quality", 90)}",
                    "-method", "${i(p, "webp_method", 4)}")
                if (b(p, "lossless")) args += listOf("-lossless", "1")
            }
            "png" -> args += listOf("-compression_level", "${i(p, "png_compress_level", 6)}")
            "tiff" -> s(p, "tiff_compression").let { if (it.isNotEmpty()) args += listOf("-compression", it) }
        }
        if (b(p, "strip_metadata")) args += listOf("-map_metadata", "-1")
        args += listOf("-frames:v", "1")
        return args
    }

    /** 构建完整 ffmpeg 参数（不含可执行文件路径，FFmpegKit 直接接收参数数组）。 */
    fun buildCommand(src: String, dst: String, p: Map<String, Any?>,
                     duration: Double? = null, passNo: Int = 0,
                     passlog: String? = null): List<String> {
        val params = if (duration != null && p["_duration"] == null) p + ("_duration" to duration) else p
        val cmd = mutableListOf("-hide_banner", "-nostdin")
        cmd += if (b(params, "overwrite", true)) "-y" else "-n"

        val hw = s(params, "hwaccel")
        if (hw.isNotEmpty()) cmd += listOf("-hwaccel", hw)
        s(params, "start_time").let { if (it.isNotEmpty()) cmd += listOf("-ss", it) }
        cmd += listOf("-i", src)
        val dur = s(params, "duration")
        val end = s(params, "end_time")
        if (dur.isNotEmpty()) cmd += listOf("-t", dur)
        else if (end.isNotEmpty()) cmd += listOf("-to", end)

        val outExt = dst.substringAfterLast('.', "").lowercase()
        val fmt = Formats.findFormat(outExt)
        val kind = fmt?.kind ?: Formats.detectKind(dst)

        var wantVideo = kind == Formats.VIDEO
        var wantAudio = kind != Formats.IMAGE
        if (fmt != null && kind == Formats.VIDEO && fmt.audioCodecs.isEmpty()) wantAudio = false

        val vEnc = s(params, "video_codec").ifEmpty { fmt?.videoCodecs?.firstOrNull() ?: "" }
        val aEnc = s(params, "audio_codec").ifEmpty { fmt?.audioCodecs?.firstOrNull() ?: "" }

        if (kind == Formats.IMAGE) {
            cmd += imageArgs(params, outExt)
        } else {
            if (wantVideo && vEnc.isNotEmpty()) {
                val vf = buildVideoFilters(params)
                if (vEnc == "gif" && b(params, "gif_palette", true)) {
                    val colors = i(params, "gif_max_colors", 256)
                    val dither = s(params, "gif_dither", "sierra2_4a").ifEmpty { "sierra2_4a" }
                    val pre = if (vf.isNotEmpty()) vf.joinToString(",") + "," else ""
                    cmd += listOf("-filter_complex",
                        "[0:v]${pre}split[a][b];[a]palettegen=max_colors=$colors[p];[b][p]paletteuse=dither=$dither")
                } else if (vf.isNotEmpty() && vEnc != "copy") {
                    cmd += listOf("-vf", vf.joinToString(","))
                }
                cmd += videoEncoderArgs(vEnc, params, passNo)
                if (params["gif_loop"] != null && outExt in setOf("gif", "webp", "apng"))
                    cmd += listOf("-loop", "${i(params, "gif_loop", 0)}")
            } else {
                cmd += "-vn"
            }

            if (passNo == 1) wantAudio = false
            if (wantAudio && aEnc.isNotEmpty()) {
                val af = buildAudioFilters(params)
                if (af.isNotEmpty() && aEnc != "copy") cmd += listOf("-af", af.joinToString(","))
                cmd += audioEncoderArgs(aEnc, params)
            } else if (!wantAudio) {
                cmd += "-an"
            }

            val subMode = if (passNo == 1) "none" else s(params, "subtitle_mode", "copy")
            if (kind == Formats.VIDEO && subMode == "copy" && outExt in setOf("mkv", "mp4", "mov", "webm")) {
                cmd += listOf("-c:s", if (outExt == "mkv") "copy" else "mov_text",
                    "-map", "0", "-map", "-0:d?")
            } else if (subMode in setOf("none", "burn")) {
                cmd += "-sn"
            }
        }

        if (b(params, "strip_metadata") && kind != Formats.IMAGE) cmd += listOf("-map_metadata", "-1")
        if (!b(params, "copy_chapters", true)) cmd += listOf("-map_chapters", "-1")
        val threads = i(params, "threads")
        if (threads > 0) cmd += listOf("-threads", "$threads")
        if (outExt in setOf("mp4", "m4v", "mov", "m4a") && b(params, "faststart", true))
            cmd += listOf("-movflags", "+faststart")

        if (passNo == 1) cmd += listOf("-f", "null")
        else if (fmt?.muxer != null && kind != Formats.IMAGE) cmd += listOf("-f", fmt.muxer)

        val extra = s(params, "extra_args")
        if (extra.isNotEmpty()) cmd += extra.split(Regex("\\s+")).filter { it.isNotEmpty() }

        if (passNo == 1) {
            if (passlog != null) cmd += listOf("-passlogfile", passlog)
            cmd += "/dev/null"
        } else {
            if (passNo == 2 && passlog != null) cmd += listOf("-passlogfile", passlog)
            cmd += dst
        }
        return cmd
    }

    fun needsTwoPass(p: Map<String, Any?>): Boolean =
        b(p, "two_pass") && s(p, "bitrate").isNotEmpty() && s(p, "video_codec") != "copy"
}
