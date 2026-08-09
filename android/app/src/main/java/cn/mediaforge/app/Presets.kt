package cn.mediaforge.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * 内置预设与用户预设读写 —— 桌面版 app/core/presets.py 的 Kotlin 1:1 移植。
 * 用户预设存于应用私有目录 presets.json，JSON 结构与桌面端完全一致，可互相导入导出。
 */
data class Preset(
    var name: String,
    val kind: String,
    val ext: String,
    val params: MutableMap<String, Any?> = mutableMapOf(),
    val description: String = "",
    val builtin: Boolean = false,
)

object Presets {
    private lateinit var file: File

    fun init(context: Context) {
        file = File(context.filesDir, "presets.json")
    }

    private fun v(ext: String, vc: String, ac: String, vararg kv: Pair<String, Any?>): MutableMap<String, Any?> {
        val m = mutableMapOf<String, Any?>("video_codec" to vc, "audio_codec" to ac)
        kv.forEach { m[it.first] = it.second }
        return m
    }

    val BUILTIN: List<Preset> = listOf(
        Preset("MP4 通用高质量", Formats.VIDEO, "mp4",
            v("mp4", "libx264", "aac", "rate_mode" to "crf", "crf" to 20.0, "preset" to "slow",
                "pix_fmt" to "yuv420p", "audio_bitrate" to "192k", "faststart" to true),
            "H.264 + AAC，兼容性最好", true),
        Preset("MP4 压缩省空间", Formats.VIDEO, "mp4",
            v("mp4", "libx265", "aac", "rate_mode" to "crf", "crf" to 28.0, "preset" to "medium",
                "audio_bitrate" to "128k"),
            "H.265，体积约为 H.264 的一半", true),
        Preset("1080p 网络上传", Formats.VIDEO, "mp4",
            v("mp4", "libx264", "aac", "rate_mode" to "vbr", "bitrate" to "8000k",
                "maxrate" to "10000k", "bufsize" to "16000k", "width" to 1920, "height" to 1080,
                "preset" to "medium", "audio_bitrate" to "192k"),
            "YouTube/B 站推荐参数", true),
        Preset("720p 手机友好", Formats.VIDEO, "mp4",
            v("mp4", "libx264", "aac", "rate_mode" to "crf", "crf" to 24.0, "width" to 1280,
                "height" to 720, "preset" to "fast", "profile" to "main", "audio_bitrate" to "128k"),
            "体积小，移动端流畅播放", true),
        Preset("4K HEVC 10bit", Formats.VIDEO, "mkv",
            v("mkv", "libx265", "libopus", "rate_mode" to "crf", "crf" to 22.0,
                "preset" to "slow", "pix_fmt" to "yuv420p10le", "width" to 3840, "height" to 2160),
            "高画质归档", true),
        Preset("WebM (VP9)", Formats.VIDEO, "webm",
            v("webm", "libvpx-vp9", "libopus", "rate_mode" to "crf", "crf" to 31.0,
                "cpu_used" to 2, "audio_bitrate" to "128k"),
            "网页嵌入，开源格式", true),
        Preset("AV1 高压缩", Formats.VIDEO, "mkv",
            v("mkv", "libsvtav1", "libopus", "rate_mode" to "crf", "crf" to 32.0, "preset" to 7),
            "最新一代编码，体积最小", true),
        Preset("GIF 动图", Formats.VIDEO, "gif",
            v("gif", "gif", "", "fps" to "12", "width" to 480, "gif_palette" to true,
                "gif_dither" to "sierra2_4a", "gif_max_colors" to 256),
            "调色板优化，画质更好", true),
        Preset("无损归档 (FFV1/MKV)", Formats.VIDEO, "mkv",
            v("mkv", "libx264", "flac", "rate_mode" to "lossless", "preset" to "veryslow"),
            "画质无损，体积很大", true),
        Preset("仅重封装（极快）", Formats.VIDEO, "mp4",
            v("mp4", "copy", "copy"),
            "不重新编码，仅换容器，秒级完成", true),
        Preset("NVIDIA 显卡加速", Formats.VIDEO, "mp4",
            v("mp4", "h264_nvenc", "aac", "rate_mode" to "cq", "crf" to 23.0,
                "preset" to "p5", "hwaccel" to "cuda"),
            "需 NVIDIA 显卡，速度极快", true),

        Preset("MP3 320k 高音质", Formats.AUDIO, "mp3",
            mutableMapOf("audio_codec" to "libmp3lame", "audio_mode" to "cbr",
                "audio_bitrate" to "320k", "sample_rate" to "44100"),
            "最高质量 MP3", true),
        Preset("MP3 V0 (VBR)", Formats.AUDIO, "mp3",
            mutableMapOf("audio_codec" to "libmp3lame", "audio_mode" to "vbr", "mp3_vbr_quality" to 0),
            "体积与音质平衡最佳", true),
        Preset("AAC 256k", Formats.AUDIO, "m4a",
            mutableMapOf("audio_codec" to "aac", "audio_bitrate" to "256k", "sample_rate" to "48000"),
            "苹果生态首选", true),
        Preset("FLAC 无损", Formats.AUDIO, "flac",
            mutableMapOf("audio_codec" to "flac", "compression_level" to 8),
            "无损压缩，适合收藏", true),
        Preset("WAV 44.1k 16bit", Formats.AUDIO, "wav",
            mutableMapOf("audio_codec" to "pcm_s16le", "sample_rate" to "44100", "channels" to "2"),
            "CD 标准，无压缩", true),
        Preset("Opus 语音 64k", Formats.AUDIO, "opus",
            mutableMapOf("audio_codec" to "libopus", "audio_bitrate" to "64k",
                "opus_application" to "voip", "channels" to "1"),
            "播客/语音，极省空间", true),
        Preset("播客响度标准化", Formats.AUDIO, "mp3",
            mutableMapOf("audio_codec" to "libmp3lame", "audio_bitrate" to "128k",
                "normalize" to true, "loudness_target" to -16.0, "channels" to "1"),
            "-16 LUFS，符合播客规范", true),
        Preset("提取音轨（不转码）", Formats.AUDIO, "mka",
            mutableMapOf("audio_codec" to "copy"),
            "从视频里原样抽出音频", true),

        Preset("JPEG 高质量", Formats.IMAGE, "jpg",
            mutableMapOf("quality" to 92, "optimize" to true, "progressive" to true,
                "subsampling" to "4:4:4"),
            "照片首选", true),
        Preset("JPEG 网页压缩", Formats.IMAGE, "jpg",
            mutableMapOf("quality" to 78, "optimize" to true, "progressive" to true,
                "width" to 1920, "strip_metadata" to true),
            "体积小，适合网页", true),
        Preset("PNG 无损压缩", Formats.IMAGE, "png",
            mutableMapOf("png_compress_level" to 9, "optimize" to true),
            "截图、透明图", true),
        Preset("WebP 有损", Formats.IMAGE, "webp",
            mutableMapOf("quality" to 80, "webp_method" to 6),
            "比 JPEG 小 30%", true),
        Preset("WebP 无损", Formats.IMAGE, "webp",
            mutableMapOf("lossless" to true, "webp_method" to 6), "替代 PNG", true),
        Preset("AVIF 极致压缩", Formats.IMAGE, "avif",
            mutableMapOf("quality" to 60, "avif_speed" to 4), "新一代图片格式", true),
        Preset("缩略图 400px", Formats.IMAGE, "jpg",
            mutableMapOf("width" to 400, "height" to 400, "keep_aspect" to true,
                "quality" to 85, "strip_metadata" to true), "批量生成缩略图", true),
        Preset("Windows 图标 ICO", Formats.IMAGE, "ico",
            mutableMapOf("ico_sizes" to "16,32,48,64,128,256"), "多尺寸图标", true),
        Preset("TIFF 印刷 300DPI", Formats.IMAGE, "tiff",
            mutableMapOf("tiff_compression" to "tiff_lzw", "dpi" to 300, "color_mode" to "CMYK"),
            "送印用", true),
    )

    // ------------------------------------------------------------------
    // 用户预设持久化（与桌面端 presets.json 同格式）
    // ------------------------------------------------------------------
    fun loadUserPresets(): MutableList<Preset> {
        if (!::file.isInitialized || !file.exists()) return mutableListOf()
        return try {
            parseList(file.readText(Charsets.UTF_8), keepBuiltinFlag = false)
        } catch (e: Exception) {
            mutableListOf()
        }
    }

    private fun parseList(json: String, keepBuiltinFlag: Boolean): MutableList<Preset> {
        val arr = JSONArray(json)
        val out = mutableListOf<Preset>()
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val name = o.optString("name", "")
            val kind = o.optString("kind", "")
            val ext = o.optString("ext", "")
            if (name.isEmpty() || kind.isEmpty() || ext.isEmpty()) continue
            val params = mutableMapOf<String, Any?>()
            val po = o.optJSONObject("params")
            if (po != null) for (key in po.keys()) params[key] = po.get(key)
            out += Preset(name, kind, ext, params, o.optString("description", ""),
                keepBuiltinFlag && o.optBoolean("builtin", false))
        }
        return out
    }

    fun saveUserPresets(presets: List<Preset>) {
        val arr = JSONArray()
        for (p in presets) {
            if (p.builtin) continue
            arr.put(JSONObject().apply {
                put("name", p.name); put("kind", p.kind); put("ext", p.ext)
                put("description", p.description)
                put("params", JSONObject(p.params))
            })
        }
        file.writeText(arr.toString(2), Charsets.UTF_8)
    }

    /** 新增用户预设；空名 / 与用户或内置同名抛 IllegalArgumentException。 */
    fun addUserPreset(preset: Preset) {
        require(preset.name.isNotBlank()) { "预设名称不能为空" }
        val list = loadUserPresets()
        require(list.none { it.name == preset.name }) { "已存在同名预设：${preset.name}" }
        require(BUILTIN.none { it.name == preset.name }) { "与内置预设同名：${preset.name}" }
        list += preset
        saveUserPresets(list)
    }

    fun renameUserPreset(oldName: String, newName: String): Boolean {
        require(newName.isNotBlank()) { "新名称不能为空" }
        val list = loadUserPresets()
        val target = list.firstOrNull { it.name == oldName } ?: return false
        if (oldName == newName) return true
        require(list.none { it.name == newName }) { "已存在同名预设：$newName" }
        require(BUILTIN.none { it.name == newName }) { "与内置预设同名：$newName" }
        target.name = newName
        saveUserPresets(list)
        return true
    }

    fun deleteUserPreset(name: String): Boolean {
        val list = loadUserPresets()
        val after = list.filterNot { it.name == name }
        if (after.size == list.size) return false
        saveUserPresets(after)
        return true
    }

    /** 用当前参数重建（覆盖）同名用户预设；不存在则新建。 */
    fun overwriteUserPreset(name: String, preset: Preset): Boolean {
        preset.name = name
        val list = loadUserPresets()
        val i = list.indexOfFirst { it.name == name }
        if (i >= 0) list[i] = preset else list += preset
        saveUserPresets(list)
        return true
    }

    fun exportPresets(presets: List<Preset>): String {
        val arr = JSONArray()
        for (p in presets) arr.put(JSONObject().apply {
            put("name", p.name); put("kind", p.kind); put("ext", p.ext)
            put("description", p.description); put("builtin", p.builtin)
            put("params", JSONObject(p.params))
        })
        return arr.toString(2)
    }

    /** 从 JSON 文本导入；返回 (新增数, 跳过名单)。 */
    fun importPresets(json: String): Pair<Int, List<String>> {
        val data = try {
            parseList(json, keepBuiltinFlag = false)
        } catch (e: Exception) {
            throw IllegalArgumentException("无法解析预设文件：${e.message}")
        }
        val existing = (BUILTIN.map { it.name } + loadUserPresets().map { it.name }).toMutableSet()
        val accepted = mutableListOf<Preset>()
        val skipped = mutableListOf<String>()
        for (p in data) {
            if (p.name in existing) { skipped += p.name; continue }
            accepted += p
            existing += p.name
        }
        if (accepted.isNotEmpty()) saveUserPresets(loadUserPresets() + accepted)
        return accepted.size to skipped
    }

    fun allPresets(kind: String? = null): List<Preset> {
        val all = BUILTIN + loadUserPresets()
        return if (kind == null) all else all.filter { it.kind == kind }
    }
}
