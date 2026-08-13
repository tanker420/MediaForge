package cn.mediaforge.app

import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import java.io.File
import java.util.Locale

/**
 * 视频 → Live Photo（Google Motion Photo / 实况照片）转换 —— 桌面版
 * app/core/motion_photo.py 的 Kotlin 移植。
 *
 * 生成单文件 Motion Photo：合法 JPEG 在前，尾部拼接 MP4 微视频，并在 JPEG 的
 * APP1/XMP 段写入 GCamera 元数据。兼容 Google Photos / 安卓相册 / 小红书等。
 */
object MotionPhoto {

    private const val XMP_IDENT = "http://ns.adobe.com/xap/1.0/\u0000"

    fun buildXmp(mp4Size: Int, presentationTimestampUs: Long): String =
        "<x:xmpmeta xmlns:x=\"adobe:ns:meta/\">" +
            "<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"" +
            " xmlns:Camera=\"http://ns.google.com/photos/1.0/camera/\"" +
            " xmlns:Container=\"http://ns.google.com/photos/1.0/container/\"" +
            " xmlns:Item=\"http://ns.google.com/photos/1.0/container/item/\">" +
            "<rdf:Description Camera:MotionPhoto=\"1\" Camera:MotionPhotoVersion=\"1\"" +
            " Camera:MotionPhotoPresentationTimestampUs=\"$presentationTimestampUs\">" +
            "<Container:Directory><rdf:Seq>" +
            "<rdf:li rdf:parseType=\"Resource\"><Container:Item" +
            " Item:Mime=\"image/jpeg\" Item:Semantic=\"Primary\"/></rdf:li>" +
            "<rdf:li rdf:parseType=\"Resource\"><Container:Item" +
            " Item:Mime=\"video/mp4\" Item:Semantic=\"MotionPhoto\"" +
            " Item:Length=\"$mp4Size\"/></rdf:li>" +
            "</rdf:Seq></Container:Directory>" +
            "</rdf:Description></rdf:RDF></x:xmpmeta>"

    /** 把 XMP 字符串封装成 JPEG APP1 段（FFE1 + 长度 + 标识符 + XMP）。 */
    fun makeXmpSegment(xmp: String): ByteArray {
        val xmpBytes = xmp.toByteArray(Charsets.UTF_8)
        val ident = XMP_IDENT.toByteArray(Charsets.US_ASCII)
        val app1Data = ident + xmpBytes
        val length = app1Data.size + 2
        val out = ByteArray(2 + 2 + app1Data.size)
        out[0] = 0xFF.toByte(); out[1] = 0xE1.toByte()
        out[2] = ((length shr 8) and 0xFF).toByte()
        out[3] = (length and 0xFF).toByte()
        System.arraycopy(app1Data, 0, out, 4, app1Data.size)
        return out
    }

    /** 在 SOI（FFD8）之后插入 XMP APP1 段。 */
    fun injectXmp(jpeg: ByteArray, xmpSegment: ByteArray): ByteArray {
        require(jpeg.size >= 2 && jpeg[0] == 0xFF.toByte() && jpeg[1] == 0xD8.toByte()) {
            "不是有效的 JPEG 文件"
        }
        val out = ByteArray(jpeg.size + xmpSegment.size)
        System.arraycopy(jpeg, 0, out, 0, 2)
        System.arraycopy(xmpSegment, 0, out, 2, xmpSegment.size)
        System.arraycopy(jpeg, 2, out, 2 + xmpSegment.size, jpeg.size - 2)
        return out
    }

    private fun quote(a: String): String =
        if (a.matches(Regex("^[A-Za-z0-9_\\-./:=,@%+]+$"))) a
        else "\"" + a.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

    private fun run(cmd: List<String>): Boolean {
        val session = FFmpegKit.execute(cmd.joinToString(" ") { quote(it) })
        return ReturnCode.isSuccess(session.returnCode)
    }

    private fun num(p: Map<String, Any?>, key: String, def: Int): Int =
        ((p[key] as? Number)?.toDouble()?.toInt()) ?: def

    /**
     * 视频 → Motion Photo。isCancelled 在步骤间被检查。
     * 返回是否成功；取消返回 false（由调用方把任务标记为「已取消」）。
     */
    fun convert(src: String, dst: String, params: Map<String, Any?>,
                isCancelled: () -> Boolean): Boolean {
        val duration = Converter.probeDuration(src) ?: 0.0
        var tsUs = (params["presentation_timestamp_us"] as? Number)?.toLong() ?: 1_000_000L
        if (tsUs <= 0) tsUs = 1_000_000L
        if (duration > 0 && tsUs / 1_000_000.0 >= duration)
            tsUs = maxOf(0L, ((duration - 0.05) * 1_000_000).toLong())

        File(dst).parentFile?.mkdirs()
        val tmp = File.createTempFile("mf_mp_", ".bin")
        val jpg = File(tmp.parentFile, tmp.name + ".jpg")
        val mp4 = File(tmp.parentFile, tmp.name + ".mp4")
        try {
            if (isCancelled()) return false
            val ts = String.format(Locale.US, "%.3f", tsUs / 1_000_000.0)
            if (!run(listOf("-y", "-hide_banner", "-loglevel", "error",
                    "-i", src, "-ss", ts, "-vframes", "1", "-q:v", "2",
                    jpg.absolutePath))) return false

            if (isCancelled()) return false
            val crf = num(params, "crf", 23)
            val ab = (params["audio_bitrate"] as? String).takeIf { !it.isNullOrBlank() } ?: "128k"
            val cmd = mutableListOf(
                "-y", "-hide_banner", "-loglevel", "error",
                "-i", src,
                "-c:v", "libx264", "-preset", "medium", "-crf", "$crf",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", ab,
                "-movflags", "+faststart")
            val w = num(params, "width", 0)
            val h = num(params, "height", 0)
            if (w != 0 || h != 0) {
                cmd += listOf("-vf",
                    "scale=${if (w != 0) "$w" else "-2"}:${if (h != 0) "$h" else "-2"}")
            }
            cmd += mp4.absolutePath
            if (!run(cmd)) return false

            if (isCancelled()) return false
            val jpegData = jpg.readBytes()
            val mp4Data = mp4.readBytes()
            val xmp = makeXmpSegment(buildXmp(mp4Data.size, tsUs))
            val out = injectXmp(jpegData, xmp) + mp4Data
            File(dst).writeBytes(out)
            return true
        } finally {
            jpg.delete(); mp4.delete(); tmp.delete()
        }
    }

    /** 从 Motion Photo 里抽出内嵌 MP4 到临时文件，返回路径；失败返回 null。 */
    fun extractMicrovideo(src: String): String? {
        val data = File(src).readBytes()
        val ftyp = byteArrayOf(
            'f'.code.toByte(), 't'.code.toByte(), 'y'.code.toByte(), 'p'.code.toByte())
        var pos = -1
        for (i in data.size - 4 downTo 0) {
            if (data[i] == ftyp[0] && data[i + 1] == ftyp[1] &&
                data[i + 2] == ftyp[2] && data[i + 3] == ftyp[3]) { pos = i; break }
        }
        if (pos <= 0) {
            for (i in 0..data.size - 4) {
                if (data[i] == ftyp[0] && data[i + 1] == ftyp[1] &&
                    data[i + 2] == ftyp[2] && data[i + 3] == ftyp[3]) { pos = i; break }
            }
        }
        if (pos <= 0) return null
        val start = maxOf(0, pos - 4)
        val tmp = File.createTempFile("mf_mv_", ".mp4")
        tmp.writeBytes(data.copyOfRange(start, data.size))
        return tmp.absolutePath
    }
}
