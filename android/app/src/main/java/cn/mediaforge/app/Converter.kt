package cn.mediaforge.app

import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.FFmpegSession
import com.arthenica.ffmpegkit.FFprobeKit
import com.arthenica.ffmpegkit.ReturnCode
import java.util.concurrent.Executors
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ExecutorService
import java.util.concurrent.ConcurrentHashMap

data class Job(val src: String, val dst: String, val params: Map<String, Any?>, val kind: String)

/** 转换执行器：FFmpegKit 并发队列，支持取消与进度回调。 */
object Converter {

    interface Listener {
        fun onProgress(job: Job, progress: Float, speed: String)
        fun onJobDone(job: Job, ok: Boolean, message: String)
        fun onAllDone()
    }

    var listener: Listener? = null

    private var executor: ExecutorService? = null
    private val sessions = ConcurrentHashMap<Job, FFmpegSession>()

    @Volatile
    var cancelled = false
        private set

    /** 把单个参数按 shell 规则加引号，供 ffmpeg-kit 命令解析器正确拆分。 */
    private fun quote(a: String): String =
        if (a.matches(Regex("^[A-Za-z0-9_\\-./:=,@%+]+$"))) a
        else "\"" + a.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

    /** 当前 ffmpeg-kit 内置的编码器集合（用于「（不支持）」标记）。 */
    fun availableEncoders(): Set<String> {
        return try {
            val session = FFmpegKit.execute("-hide_banner -encoders")
            if (!ReturnCode.isSuccess(session.returnCode)) return emptySet()
            val names = mutableSetOf<String>()
            for (line in session.allLogsAsString.lines()) {
                val t = line.trim().split(Regex("\\s+"))
                if (t.size >= 2 && t[0].length == 6 && (t[0].startsWith("V") || t[0].startsWith("A")))
                    names += t[1]
            }
            names
        } catch (e: Exception) {
            emptySet()
        }
    }

    /** 探测媒体时长（秒），失败返回 null。 */
    fun probeDuration(path: String): Double? = try {
        FFprobeKit.getMediaInformation(path).mediaInformation?.duration?.toDoubleOrNull()
    } catch (e: Exception) { null }

    /** 探测首个音频流的采样率（Hz），失败返回 null。用于响度归一化/变调的
     *  重采样基准，避免无信息时回退到固定 48kHz 造成失真。 */
    fun probeAudioSampleRate(path: String): Int? {
        return try {
            val info = FFprobeKit.getMediaInformation(path).mediaInformation
            info?.streams?.firstOrNull { it.type == "audio" }?.sampleRate?.toIntOrNull()
        } catch (e: Exception) { null }
    }

    fun start(jobs: List<Job>, workers: Int) {
        cancelled = false
        val ex = Executors.newFixedThreadPool(maxOf(1, workers))
        executor = ex
        val remaining = java.util.concurrent.atomic.AtomicInteger(jobs.size)
        for (job in jobs) {
            ex.submit {
                try {
                    runJob(job)
                } finally {
                    if (remaining.decrementAndGet() == 0) {
                        listener?.onAllDone()
                    }
                }
            }
        }
    }

    fun cancel() {
        cancelled = true
        sessions.values.forEach { runCatching { it.cancel() } }
    }

    private fun runJob(job: Job) {
        if (cancelled) {
            listener?.onJobDone(job, false, "已取消")
            return
        }
        // Motion Photo 输入：抽出内嵌 MP4 作为视频源
        var src = job.src
        var tmpVideo: String? = null
        if (job.kind == Formats.VIDEO && Formats.isMotionPhoto(job.src)) {
            tmpVideo = MotionPhoto.extractMicrovideo(job.src)
            if (tmpVideo == null) {
                listener?.onJobDone(job, false, "无法从 Live Photo 提取视频")
                return
            }
            src = tmpVideo
        }
        try {
            // Motion Photo 输出：视频 → 实况照片（专用管线）
            if (job.kind == Formats.VIDEO && Formats.isMotionPhoto(job.dst)) {
                val ok = MotionPhoto.convert(src, job.dst, job.params) { cancelled }
                if (cancelled) {
                    listener?.onJobDone(job, false, "已取消")
                    return
                }
                if (!ok) {
                    listener?.onJobDone(job, false, "转换失败")
                    return
                }
                listener?.onProgress(job, 1f, "")
                listener?.onJobDone(job, true, "")
                return
            }

            val duration = probeDuration(src)
            val sampleRate = probeAudioSampleRate(src)
            // 注入采样率供音频滤镜使用（变调/响度归一化）
            val params = if (sampleRate != null)
                job.params + ("_sample_rate" to sampleRate) else job.params

            val passlog = if (Builder.needsTwoPass(job.params))
                job.dst + ".passlog" else null

            val passes = if (passlog != null) listOf(1, 2) else listOf(0)
            for (passNo in passes) {
                if (cancelled) {
                    cleanupPasslog(passlog)
                    listener?.onJobDone(job, false, "已取消")
                    return
                }
                val args = Builder.buildCommand(src, job.dst, params, duration, passNo, passlog)
                val latch = CountDownLatch(1)
                var ok = false
                var msg = ""
                FFmpegKit.executeAsync(
                    args.joinToString(" ") { quote(it) },
                    { session ->
                        ok = ReturnCode.isSuccess(session.returnCode)
                        msg = if (ok) "" else
                            session.allLogsAsString.lines().takeLast(6).joinToString("\n")
                        sessions.remove(job)
                        latch.countDown()
                    },
                    null,
                    { stats ->
                        val d = duration ?: 0.0
                        if (d > 0 && passNo != 1) {
                            val p = (stats.time / 1000.0 / d).toFloat().coerceIn(0f, 1f)
                            listener?.onProgress(job, p, "")
                        }
                    })
                    .let { sessions[job] = it }
                // 兜底超时：即使 ffmpeg 挂死也不永久占用线程（24h 上限）
                val finished = latch.await(24, java.util.concurrent.TimeUnit.HOURS)
                if (!finished) {
                    runCatching { sessions.remove(job)?.cancel() }
                    cleanupPasslog(passlog)
                    listener?.onJobDone(job, false, "任务超时")
                    return
                }
                if (!ok) {
                    cleanupPasslog(passlog)
                    listener?.onJobDone(job, false, msg.ifEmpty { "转换失败" })
                    return
                }
            }
            cleanupPasslog(passlog)
            listener?.onProgress(job, 1f, "")
            listener?.onJobDone(job, true, "")
        } finally {
            if (tmpVideo != null) runCatching { java.io.File(tmpVideo).delete() }
        }
    }

    /** 清理两遍编码产生的 passlog 临时文件。 */
    private fun cleanupPasslog(passlog: String?) {
        if (passlog == null) return
        runCatching { java.io.File(passlog).delete() }
        runCatching { java.io.File("$passlog-0.log").delete() }
        runCatching { java.io.File("$passlog-0.log.mbtree").delete() }
    }
}
