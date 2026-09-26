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
        // 严格对齐 Google MotionPhotoMuxer 规范，并追加 OPPO ColorOS 相册识别的
        // OpCamera 扩展字段。OPPO 系统相册只认自家格式，缺 MotionPhotoOwner=oplus
        // / OLivePhotoVersion=2 会被当作静态图，无法播放。
        "<x:xmpmeta xmlns:x=\"adobe:ns:meta/\" x:xmptk=\"XMP Core 5.1.2\">" +
            "<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\">" +
            "<rdf:Description rdf:about=\"\"" +
            " xmlns:GCamera=\"http://ns.google.com/photos/1.0/camera/\"" +
            " xmlns:OpCamera=\"http://ns.oplus.com/photos/1.0/camera/\"" +
            " xmlns:Container=\"http://ns.google.com/photos/1.0/container/\"" +
            " xmlns:Item=\"http://ns.google.com/photos/1.0/container/item/\"" +
            " GCamera:MotionPhoto=\"1\" GCamera:MotionPhotoVersion=\"1\"" +
            " GCamera:MotionPhotoPresentationTimestampUs=\"$presentationTimestampUs\"" +
            " OpCamera:MotionPhotoOwner=\"oplus\" OpCamera:OLivePhotoVersion=\"2\"" +
            " OpCamera:MotionPhotoPrimaryPresentationTimestampUs=\"$presentationTimestampUs\"" +
            " OpCamera:VideoLength=\"$mp4Size\">" +
            "<Container:Directory><rdf:Seq>" +
            "<rdf:li rdf:parseType=\"Resource\"><Container:Item" +
            " Item:Mime=\"image/jpeg\" Item:Semantic=\"Primary\"" +
            " Item:Length=\"0\" Item:Padding=\"0\"/></rdf:li>" +
            "<rdf:li rdf:parseType=\"Resource\"><Container:Item" +
            " Item:Mime=\"video/mp4\" Item:Semantic=\"MotionPhoto\"" +
            " Item:Length=\"$mp4Size\" Item:Padding=\"0\"/></rdf:li>" +
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
            // 流式拼接：JPEG 很小可直接读；MP4 可能很大，边读边写避免 OOM
            val jpegData = jpg.readBytes()
            val mp4Size = mp4.length().toInt()
            val xmp = makeXmpSegment(buildXmp(mp4Size, tsUs))
            File(dst).outputStream().buffered().use { out ->
                // 手写 injectXmp 的流式版本：SOI + XMP APP1 + JPEG 剩余部分 + MP4
                out.write(jpegData, 0, 2)
                out.write(xmp)
                out.write(jpegData, 2, jpegData.size - 2)
                mp4.inputStream().buffered().use { it.copyTo(out) }
            }
            return true
        } finally {
            jpg.delete(); mp4.delete(); tmp.delete()
        }
    }

    /** 从 Motion Photo 里抽出内嵌 MP4 到临时文件，返回路径；失败返回 null。
     *  流式实现：优先读文件头部 XMP 中的视频长度字段定位（MediaForge 生成的
     *  文件含 OpCamera:VideoLength，标准 Google Motion Photo 含 Item:Length），
     *  避免全文件读入内存；解析失败时回退头部 1MB 扫描 ftyp。 */
    fun extractMicrovideo(src: String): String? {
        val f = File(src)
        val total = f.length()
        if (total <= 0) return null

        // 读文件头（JPEG + XMP 在前 256KB 内通常足够）
        val headSize = minOf(total, 256 * 1024L)
        val head = ByteArray(headSize.toInt())
        f.inputStream().use { it.readFully(head, headSize.toInt()) }

        // 1) 优先用 XMP 里的视频长度：MP4 = 文件末尾 videoLen 字节
        val headStr = String(head, Charsets.UTF_8)
        val videoLen = Regex("""OpCamera:VideoLength="(\d+)"""").find(headStr)
            ?.groupValues?.get(1)?.toLongOrNull()
            ?: Regex("""Item:Semantic="MotionPhoto"[^>]*Item:Length="(\d+)"""").find(headStr)
                ?.groupValues?.get(1)?.toLongOrNull()
            ?: Regex("""Item:Length="(\d+)"[^>]*Item:Semantic="MotionPhoto"""").find(headStr)
                ?.groupValues?.get(1)?.toLongOrNull()

        var start = -1L
        if (videoLen != null && videoLen in 1 until total) {
            val candidate = total - videoLen
            // 验证该位置确实是 ftyp 盒
            val probe = ByteArray(8)
            f.inputStream().use { ins ->
                ins.skipFully(candidate)
                ins.readFully(probe, 8)
            }
            if (probe[4] == 'f'.code.toByte() && probe[5] == 't'.code.toByte()
                && probe[6] == 'y'.code.toByte() && probe[7] == 'p'.code.toByte()) {
                start = candidate
            }
        }

        // 2) 回退：头部 1MB 内扫描 ftyp（MP4 紧跟在 JPEG 后面）
        if (start < 0) {
            val scanSize = minOf(total, 1024 * 1024L)
            val buf = ByteArray(scanSize.toInt())
            f.inputStream().use { it.readFully(buf, scanSize.toInt()) }
            val ftyp = byteArrayOf('f'.code.toByte(), 't'.code.toByte(),
                                   'y'.code.toByte(), 'p'.code.toByte())
            val pos = lastIndexOf(buf, ftyp).let { if (it >= 0) it else indexOf(buf, ftyp) }
            if (pos > 0) start = (pos - 4).toLong()
        }
        if (start < 0) return null

        val tmp = File.createTempFile("mf_mv_", ".mp4")
        f.inputStream().buffered().use { ins ->
            ins.skipFully(start)
            tmp.outputStream().buffered().use { out -> ins.copyTo(out) }
        }
        return tmp.absolutePath
    }

    private fun lastIndexOf(haystack: ByteArray, needle: ByteArray): Int {
        outer@ for (i in haystack.size - needle.size downTo 0) {
            for (j in needle.indices) if (haystack[i + j] != needle[j]) continue@outer
            return i
        }
        return -1
    }

    private fun indexOf(haystack: ByteArray, needle: ByteArray): Int {
        outer@ for (i in 0..haystack.size - needle.size) {
            for (j in needle.indices) if (haystack[i + j] != needle[j]) continue@outer
            return i
        }
        return -1
    }

    private fun java.io.InputStream.readFully(buf: ByteArray, n: Int) {
        var off = 0
        while (off < n) {
            val r = read(buf, off, n - off)
            if (r < 0) break
            off += r
        }
    }

    private fun java.io.InputStream.skipFully(n: Long) {
        var left = n
        while (left > 0) {
            val r = skip(left)
            if (r <= 0) { if (read() < 0) break } else left -= r
        }
    }
}
