"""转换任务模型与执行引擎（含进度回调、并发队列）。"""
from __future__ import annotations

import os
import queue
import re
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from . import formats as F
from . import image_engine
from . import motion_photo
from .ffmpeg_builder import build_command, needs_two_pass
from .ffprobe import CREATE_NO_WINDOW, MediaInfo, probe, require_ffmpeg


class Status(str, Enum):
    PENDING = "等待中"
    RUNNING = "转换中"
    DONE = "已完成"
    FAILED = "失败"
    CANCELED = "已取消"
    SKIPPED = "已跳过"


@dataclass
class Job:
    src: str
    dst: str
    params: dict[str, Any] = field(default_factory=dict)
    kind: str = F.VIDEO
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: Status = Status.PENDING
    progress: float = 0.0
    message: str = ""
    speed: str = ""
    eta: float = 0.0
    started_at: float = 0.0
    ended_at: float = 0.0
    out_size: int = 0
    log: list[str] = field(default_factory=list)
    info: MediaInfo | None = None

    @property
    def name(self) -> str:
        return os.path.basename(self.src)

    @property
    def elapsed(self) -> float:
        if not self.started_at:
            return 0.0
        return (self.ended_at or time.time()) - self.started_at


ProgressCB = Callable[[Job], None]

_TIME_RE = re.compile(r"out_time_ms=(-?\d+)")
_SPEED_RE = re.compile(r"speed=\s*([0-9.]+)x")
_FRAME_RE = re.compile(r"frame=(\d+)")


class Canceled(Exception):
    pass


def _run_ffmpeg(cmd: list[str], job: Job, duration: float,
                on_progress: ProgressCB | None,
                cancel: threading.Event,
                base: float = 0.0, span: float = 1.0) -> None:
    """运行一次 ffmpeg 并解析 -progress 输出。"""
    full = cmd[:1] + ["-progress", "pipe:1", "-nostats"] + cmd[1:]
    job.log.append("$ " + " ".join(full))

    proc = subprocess.Popen(
        full, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )
    tail: list[str] = []
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise Canceled

            line = line.rstrip()
            if not line:
                continue
            if not line.startswith(("frame=", "fps=", "bitrate=", "total_size=",
                                    "out_time", "dup_frames=", "drop_frames=",
                                    "speed=", "progress=", "stream_")):
                tail.append(line)
                del tail[:-40]
                job.log.append(line)
                del job.log[:-400]

            m = _TIME_RE.search(line)
            if m and duration > 0:
                secs = max(0, int(m.group(1))) / 1_000_000
                job.progress = min(0.999, base + span * (secs / duration))
                if on_progress:
                    on_progress(job)
            elif m and duration <= 0:
                job.message = f"已处理 {int(m.group(1)) / 1_000_000:.1f}s"
                if on_progress:
                    on_progress(job)

            m = _SPEED_RE.search(line)
            if m:
                job.speed = f"{m.group(1)}x"
                try:
                    sp = float(m.group(1))
                    if duration > 0 and sp > 0:
                        done = job.progress
                        job.eta = max(0.0, duration * (1 - done) / sp)
                except ValueError:
                    pass
    finally:
        proc.stdout and proc.stdout.close()
        code = proc.wait()

    if cancel.is_set():
        raise Canceled
    if code != 0:
        detail = "\n".join(tail[-12:]) or f"退出码 {code}"
        raise RuntimeError(f"ffmpeg 失败：\n{detail}")


def run_job(job: Job, on_progress: ProgressCB | None = None,
            cancel: threading.Event | None = None) -> Job:
    """执行单个任务（同步阻塞）。"""
    cancel = cancel or threading.Event()
    job.status = Status.RUNNING
    job.started_at = time.time()
    job.progress = 0.0
    if on_progress:
        on_progress(job)

    try:
        if not os.path.isfile(job.src):
            raise FileNotFoundError(f"源文件不存在：{job.src}")

        os.makedirs(os.path.dirname(os.path.abspath(job.dst)) or ".", exist_ok=True)

        if os.path.exists(job.dst) and not job.params.get("overwrite", True):
            job.status = Status.SKIPPED
            job.message = "目标已存在，跳过"
            job.ended_at = time.time()
            if on_progress:
                on_progress(job)
            return job

        if os.path.abspath(job.src) == os.path.abspath(job.dst):
            raise ValueError("源文件与目标文件相同")

        if job.kind == F.IMAGE:
            try:
                image_engine.convert_image(job.src, job.dst, job.params, cancel)
            except image_engine.CanceledError:
                raise Canceled from None
            job.progress = 1.0
        else:
            require_ffmpeg()
            src = job.src
            tmp_video: str | None = None
            # Motion Photo 输入：先抽出内嵌 MP4，再走常规视频转换
            if job.kind == F.VIDEO and motion_photo.is_motion_photo_input(job.src):
                try:
                    tmp_video = motion_photo.extract_microvideo(job.src, cancel)
                    src = tmp_video
                    job.info = probe(src)
                except motion_photo.Canceled:
                    raise Canceled from None

            try:
                if job.info is None:
                    job.info = probe(src)

                # 视频 → Live Photo（Motion Photo）专用管线
                if job.kind == F.VIDEO and motion_photo.is_motion_photo_output(job.dst):
                    motion_photo.convert(src, job.dst, job.params, cancel,
                                         on_progress=_mp_progress(job, on_progress))
                    job.progress = 1.0
                else:
                    duration = job.info.duration if job.info else 0.0
                    # 有裁剪时按裁剪时长算进度
                    params = dict(job.params)
                    params["_duration"] = duration
                    a_stream = job.info.audio if job.info else None
                    if a_stream and a_stream.sample_rate:
                        params["_sample_rate"] = a_stream.sample_rate
                    trimmed = _effective_duration(params, duration)

                    if needs_two_pass(params):
                        with tempfile.TemporaryDirectory() as tmp:
                            log = os.path.join(tmp, "ffpass")
                            _run_ffmpeg(build_command(src, job.dst, params, job.info, 1, log),
                                        job, trimmed, on_progress, cancel, 0.0, 0.5)
                            _run_ffmpeg(build_command(src, job.dst, params, job.info, 2, log),
                                        job, trimmed, on_progress, cancel, 0.5, 0.5)
                    else:
                        _run_ffmpeg(build_command(src, job.dst, params, job.info),
                                    job, trimmed, on_progress, cancel)
                    job.progress = 1.0
            except motion_photo.Canceled:
                raise Canceled from None
            finally:
                if tmp_video:
                    try:
                        os.remove(tmp_video)
                    except OSError:
                        pass

        job.status = Status.DONE
        try:
            job.out_size = os.path.getsize(job.dst)
        except OSError:
            job.out_size = 0
        job.message = "完成"
    except Canceled:
        job.status = Status.CANCELED
        job.message = "已取消"
        _cleanup_partial(job)
    except Exception as exc:  # noqa: BLE001
        job.status = Status.FAILED
        job.message = str(exc)
        job.log.append(f"[错误] {exc}")
        _cleanup_partial(job)
    finally:
        job.ended_at = time.time()
        if on_progress:
            on_progress(job)
    return job


def _cleanup_partial(job: Job) -> None:
    """删除中断产生的残缺输出。"""
    try:
        if os.path.exists(job.dst) and os.path.getsize(job.dst) == 0:
            os.remove(job.dst)
    except OSError:
        pass


def _mp_progress(job: Job, on_progress: ProgressCB | None) -> Callable[[float], None]:
    """把 Motion Photo 管线的 0~1 进度写回 job 并通知 UI。"""
    def cb(p: float) -> None:
        job.progress = min(1.0, max(0.0, p))
        if on_progress:
            on_progress(job)
    return cb


def _effective_duration(params: dict[str, Any], total: float) -> float:
    """考虑起止时间后的实际处理时长。"""
    def parse(t: str) -> float:
        t = (t or "").strip()
        if not t:
            return 0.0
        if ":" in t:
            bits = [float(x) for x in t.split(":")]
            secs = 0.0
            for b in bits:
                secs = secs * 60 + b
            return secs
        try:
            return float(t)
        except ValueError:
            return 0.0

    start = parse(str(params.get("start_time", "")))
    dur = parse(str(params.get("duration", "")))
    end = parse(str(params.get("end_time", "")))
    if dur > 0:
        return dur
    if end > 0:
        return max(0.1, end - start)
    if total > 0:
        return max(0.1, total - start)
    return 0.0


class ConversionQueue:
    """带并发控制的批量转换队列。"""

    def __init__(self, workers: int = 2) -> None:
        self.workers = max(1, workers)
        self.jobs: list[Job] = []
        self._q: queue.Queue[Job] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self.on_progress: ProgressCB | None = None
        self.on_job_done: ProgressCB | None = None
        self.on_all_done: Callable[[list[Job]], None] | None = None
        self._active = 0

    # ---------------- 队列管理 ----------------
    def add(self, job: Job) -> Job:
        with self._lock:
            self.jobs.append(job)
        return job

    def clear(self) -> None:
        with self._lock:
            self.jobs = [j for j in self.jobs if j.status is Status.RUNNING]

    def remove(self, job_id: str) -> None:
        with self._lock:
            self.jobs = [j for j in self.jobs if j.id != job_id]

    @property
    def running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    # ---------------- 执行 ----------------
    def start(self) -> None:
        if self.running:
            return
        self._cancel.clear()
        pending = [j for j in self.jobs if j.status in (Status.PENDING, Status.FAILED, Status.CANCELED)]
        for j in pending:
            j.status = Status.PENDING
            j.progress = 0.0
            j.message = ""
            self._q.put(j)

        self._threads = []
        for _ in range(min(self.workers, max(1, len(pending)))):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self._threads.append(t)

        threading.Thread(target=self._await_all, daemon=True).start()

    def _worker(self) -> None:
        while not self._cancel.is_set():
            try:
                job = self._q.get_nowait()
            except queue.Empty:
                return
            try:
                run_job(job, self.on_progress, self._cancel)
            finally:
                if self.on_job_done:
                    self.on_job_done(job)
                self._q.task_done()

    def _await_all(self) -> None:
        for t in self._threads:
            t.join()
        if self.on_all_done:
            self.on_all_done(self.jobs)

    def wait(self) -> None:
        """阻塞直到所有工作线程结束（公开 API，替代直接访问 _threads）。"""
        for t in list(self._threads):
            t.join()

    def cancel(self) -> None:
        self._cancel.set()
        while True:
            try:
                j = self._q.get_nowait()
                j.status = Status.CANCELED
                j.message = "已取消"
                self._q.task_done()
            except queue.Empty:
                break
