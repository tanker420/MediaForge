package cn.mediaforge.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * 安卓端「检查更新」：移植桌面版 app/core/updater.py 的 GitHub Releases 检查 /
 * 下载逻辑。检查与下载失败一律降级（返回 null / false），不抛给 UI。
 */
data class UpdateInfo(
    val version: String,
    val name: String,
    val body: String,
    val assetUrl: String,
    val assetSize: Long,
    val htmlUrl: String
)

object Updater {

    private const val REPO = "tanker420/MediaForge"
    private const val API = "https://api.github.com/repos/$REPO/releases/latest"

    /** 把 'v1.2.3' / '1.2.3-rc1' 解析成 [1, 2, 3]；失败返回 [-1]。 */
    fun parseVersion(tag: String): List<Int> {
        val s = (tag.trim().removePrefix("v").substringBefore('-'))
        return try {
            s.split('.').map { it.toInt() }
        } catch (e: Exception) {
            listOf(-1)
        }
    }

    private fun compareVersions(a: List<Int>, b: List<Int>): Int {
        val n = maxOf(a.size, b.size)
        for (i in 0 until n) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x - y
        }
        return 0
    }

    /** 联网检查 GitHub Releases 最新稳定版，有新版则返回 UpdateInfo，否则 null。 */
    fun checkForUpdate(current: String): UpdateInfo? {
        return try {
            val conn = URL(API).openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "MediaForge-Updater/1.0")
            conn.setRequestProperty("Accept", "application/vnd.github+json")
            conn.connectTimeout = 10000
            conn.readTimeout = 10000
            if (conn.responseCode != HttpURLConnection.HTTP_OK) return null
            val text = conn.inputStream.bufferedReader().use { it.readText() }
            val json = JSONObject(text)

            val tag = json.optString("tag_name", "")
            val newV = parseVersion(tag)
            val curV = parseVersion(current)
            if (newV.contains(-1) || curV.contains(-1)) return null
            if (compareVersions(newV, curV) <= 0) return null

            val assets = json.optJSONArray("assets") ?: return null
            var assetUrl = ""
            var assetSize = 0L
            for (i in 0 until assets.length()) {
                val a = assets.optJSONObject(i) ?: continue
                val nm = a.optString("name", "")
                if (nm.lowercase().endsWith(".apk")) {
                    assetUrl = a.optString("browser_download_url", "")
                    assetSize = a.optLong("size", 0L)
                    break
                }
            }
            if (assetUrl.isEmpty()) return null

            UpdateInfo(
                version = newV.joinToString("."),
                name = json.optString("name", tag),
                body = json.optString("body", ""),
                assetUrl = assetUrl,
                assetSize = assetSize,
                htmlUrl = json.optString("html_url", "")
            )
        } catch (e: Exception) {
            null
        }
    }

    /** 下载 APK 到应用私有目录，带进度回调 (done, total)。失败返回 null。 */
    fun download(context: Context, info: UpdateInfo,
                 onProgress: (Long, Long) -> Unit): File? {
        return try {
            val conn = URL(info.assetUrl).openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "MediaForge-Updater/1.0")
            conn.connectTimeout = 30000
            conn.readTimeout = 120000
            if (conn.responseCode != HttpURLConnection.HTTP_OK) return null

            val dir = context.getExternalFilesDir(null) ?: context.cacheDir
            val file = File(dir, "MediaForge-update.apk")
            conn.inputStream.use { ins ->
                FileOutputStream(file).use { out ->
                    val buf = ByteArray(65536)
                    var done = 0L
                    while (true) {
                        val r = ins.read(buf)
                        if (r <= 0) break
                        out.write(buf, 0, r)
                        done += r
                        onProgress(done, info.assetSize)
                    }
                }
            }
            file
        } catch (e: Exception) {
            null
        }
    }

    /** 通过系统包安装器打开已下载的 APK。 */
    fun installApk(context: Context, file: File) {
        val uri = FileProvider.getUriForFile(
            context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
