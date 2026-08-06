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
        val duration = probeDuration(job.src)
        val passlog = if (Builder.needsTwoPass(job.params))
            job.dst + ".passlog" else null

        val passes = if (passlog != null) listOf(1, 2) else listOf(0)
        for (passNo in passes) {
            if (cancelled) {
                listener?.onJobDone(job, false, "已取消")
                return
            }
            val args = Builder.buildCommand(job.src, job.dst, job.params, duration, passNo, passlog)
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
            latch.await()
            if (!ok) {
                listener?.onJobDone(job, false, msg.ifEmpty { "转换失败" })
                return
            }
        }
        listener?.onProgress(job, 1f, "")
        listener?.onJobDone(job, true, "")
    }
}
