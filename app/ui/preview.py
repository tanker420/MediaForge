"""媒体预览组件。

放在文件列表下方，根据选中文件类型显示：
- 图片：缩略图（PIL）
- 视频：单帧缩略图（ffmpeg 抽取）
- 音频：归一化波形（ffmpeg 解码 + RMS）

全部在后台线程生成，通过 Signal 把像素数据送回主线程。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from ..core import formats as F
from ..core import media_preview as mp
from .theme import is_dark


@dataclass
class _PreviewResult:
    kind: str                     # "image" / "waveform" / "error" / "empty"
    image: QImage | None = None    # 直接绘制的 QImage（图片/视频/错误占位）
    waveform: list | None = None   # 波形点列表（音频）


class _Bridge(QObject):
    done = Signal(object)


class _PreviewTask(QRunnable):
    """后台：决定类型并生成预览数据，返回 _PreviewResult。"""

    def __init__(self, path: str, bridge: _Bridge) -> None:
        super().__init__()
        self.path = path
        self.bridge = bridge

    def run(self) -> None:
        try:
            kind = F.detect_kind(self.path)
            if kind == F.IMAGE:
                data = mp.make_image_thumbnail(self.path)
                img = QImage.fromData(data)
                self.bridge.done.emit(_PreviewResult(kind="image", image=img))
            elif kind == F.VIDEO:
                data = mp.extract_video_thumbnail(self.path)
                img = QImage.fromData(data)
                self.bridge.done.emit(_PreviewResult(kind="image", image=img))
            elif kind == F.AUDIO:
                wf = mp.decode_audio_waveform(self.path)
                self.bridge.done.emit(_PreviewResult(kind="waveform", waveform=wf))
            else:
                self.bridge.done.emit(_PreviewResult(kind="empty"))
        except Exception as exc:  # noqa: BLE001
            self.bridge.done.emit(_PreviewResult(
                kind="error", image=_error_pixmap(str(exc)).toImage()))


def _error_pixmap(text: str) -> QPixmap:
    pm = QPixmap(400, 200)
    pm.fill(QColor("#23252B" if is_dark() else "#F2F4F8"))
    p = QPainter(pm)
    p.setPen(QPen(QColor("#98989F" if is_dark() else "#6E6E73")))
    f = p.font(); f.setPointSize(11); p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, text[:200])
    p.end()
    return pm


class MediaPreview(QFrame):
    """媒体预览卡片，固定高度，承载缩略图或波形。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewCard")
        self.setMinimumHeight(180)
        self.setMaximumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        self.header = QLabel("预览（选中文件后自动生成）")
        self.header.setObjectName("PreviewHeader")
        lay.addWidget(self.header)

        self.canvas = _PreviewCanvas(self)
        self.canvas.setMinimumHeight(120)
        lay.addWidget(self.canvas, 1)

        self._bridge = _Bridge()
        self._bridge.done.connect(self._on_done)
        self._pool = QThreadPool(self)
        self._inflight_path: str | None = None

    def show_file(self, path: str) -> None:
        """切换预览文件；同一文件重复请求会被忽略。"""
        if not path:
            return
        if path == self._inflight_path:
            return
        self._inflight_path = path
        self.canvas.set_status("生成中…")
        self._pool.start(_PreviewTask(path, self._bridge))

    def clear(self) -> None:
        self._inflight_path = None
        self.canvas.set_empty()

    def _on_done(self, result: _PreviewResult) -> None:
        if result.kind == "image" and result.image is not None:
            self.canvas.set_image(result.image)
        elif result.kind == "waveform" and result.waveform:
            self.canvas.set_waveform(result.waveform)
        elif result.kind == "error" and result.image is not None:
            self.canvas.set_image(result.image)
        else:
            self.canvas.set_empty()


# --------------------------------------------------------------------------
# 绘制画布：image 缩略图 / 波形 / 占位文案
# --------------------------------------------------------------------------
class _PreviewCanvas(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewCanvas")
        self.setAlignment(Qt.AlignCenter)
        self._pixmap = None
        self._waveform: list | None = None
        self.set_text("拖入文件后在此查看缩略图 / 波形")

    def set_text(self, t: str) -> None:
        self._pixmap = None
        self._waveform = None
        super().setText(t)

    def set_status(self, t: str) -> None:
        super().setText(t)

    def set_empty(self) -> None:
        self.set_text("暂无预览")

    def set_image(self, img: QImage) -> None:
        self._waveform = None
        self._pixmap = QPixmap.fromImage(img)
        super().setText("")
        self.update()

    def set_waveform(self, samples: list) -> None:
        self._pixmap = None
        self._waveform = samples
        super().setText("")
        self.update()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        if self._pixmap is not None:
            p = QPainter(self)
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            scaled = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
            p.end()
            return
        if self._waveform is not None:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            w, h = self.width(), self.height()
            cy = h / 2
            n = len(self._waveform)
            if n == 0:
                p.end()
                return
            bar_w = max(1.0, (w - 16) / n)
            mid_color = QColor("#0A84FF" if is_dark() else "#007AFF")
            peak_color = QColor("#64D2FF" if is_dark() else "#5AC8FA")
            p.setPen(Qt.NoPen)
            for i, v in enumerate(self._waveform):
                amp = max(0.0, min(1.0, float(v)))
                bh = max(2.0, amp * (h * 0.85))
                x = 8 + i * bar_w
                p.fillRect(x, cy - bh / 2, max(1.0, bar_w * 0.7), bh, mid_color)
            p.end()