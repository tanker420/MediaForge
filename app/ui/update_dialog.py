"""检查更新 / 下载更新对话框。

- UpdateAvailableDialog：展示新版本号、变更摘要，提供「立即更新」「仅下载」「取消」
- UpdateProgressDialog：下载进度 + 取消
- run_in_thread 中转站：用 QThreadPool 在后台跑 check_for_update，结果通过 Signal 回到主线程
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core import updater
from ..core.updater import UpdateInfo


# --------------------------------------------------------------------------
# 后台任务
# --------------------------------------------------------------------------
class _CheckBridge(QObject):
    done = Signal(object)     # UpdateInfo | None


class _CheckTask(QRunnable):
    def __init__(self, current_version: str, bridge: _CheckBridge) -> None:
        super().__init__()
        self.current_version = current_version
        self.bridge = bridge

    def run(self) -> None:
        try:
            info = updater.check_for_update(self.current_version)
        except Exception:  # noqa: BLE001
            info = None
        self.bridge.done.emit(info)


class _DownloadBridge(QObject):
    progress = Signal(int, int)
    done = Signal(object)     # str (path) | Exception


class _DownloadTask(QRunnable):
    def __init__(self, info: UpdateInfo, bridge: _DownloadBridge,
                 cancel_evt) -> None:
        super().__init__()
        self.info = info
        self.bridge = bridge
        self.cancel = cancel_evt

    def run(self) -> None:
        try:
            path = updater.download_update(
                self.info,
                on_progress=lambda d, t: self.bridge.progress.emit(d, t),
                cancel=lambda: self.cancel.is_set(),
            )
            self.bridge.done.emit(path)
        except Exception as exc:  # noqa: BLE001
            self.bridge.done.emit(exc)


# --------------------------------------------------------------------------
# 「有可用更新」对话框
# --------------------------------------------------------------------------
class UpdateAvailableDialog(QDialog):
    """展示新版本信息，让用户选择立即更新 / 仅下载 / 取消。"""

    def __init__(self, parent: QWidget | None, info: UpdateInfo,
                 current: str) -> None:
        super().__init__(parent)
        self.info = info
        self.setWindowTitle("发现新版本")
        self.setMinimumWidth(520)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        title = QLabel(f"发现新版本：v{info.version}")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(13)
        title.setFont(title_font)
        lay.addWidget(title)

        cur_label = QLabel(f"当前版本：v{current}    ·    "
                           f"发布时间：{info.published_at[:10] if info.published_at else '-'}"
                           f"    ·    大小：{_human(info.asset_size)}")
        cur_label.setStyleSheet("color:#6B7280;font-size:11px;")
        lay.addWidget(cur_label)

        body = QTextBrowser()
        body.setOpenExternalLinks(True)
        body.setStyleSheet("QTextBrowser{background:#F8FAFD;border:1px solid #E5E7EB;"
                           "border-radius:8px;padding:10px;font-size:12px;color:#1F2937;}")
        body.setPlainText(info.summary())
        body.append(f"\n\n<a href='{info.html_url}'>在 GitHub 上查看完整说明 →</a>")
        lay.addWidget(body, 1)

        self.btn_box = QDialogButtonBox()
        self.btn_install = self.btn_box.addButton("立即更新", QDialogButtonBox.AcceptRole)
        self.btn_download = self.btn_box.addButton("仅下载", QDialogButtonBox.ActionRole)
        self.btn_box.addButton("稍后再说", QDialogButtonBox.RejectRole)
        self.btn_install.setDefault(True)
        self.btn_box.accepted.connect(self.accept)
        self.btn_box.rejected.connect(self.reject)
        self.btn_download.clicked.connect(self._on_download_only)
        lay.addWidget(self.btn_box)

    def _on_download_only(self) -> None:
        # 「仅下载」= 走下载流程但不立即安装
        self.done(2)

    @property
    def choice(self) -> str:
        """'install' / 'download' / 'later'."""
        rc = self.result()
        if rc == 1:           # QDialog.Accepted
            return "install"
        if rc == 2:           # done(2)
            return "download"
        return "later"


# --------------------------------------------------------------------------
# 下载进度对话框
# --------------------------------------------------------------------------
class UpdateProgressDialog(QDialog):
    """下载安装包的进度展示，可取消。"""

    def __init__(self, parent: QWidget | None, info: UpdateInfo) -> None:
        super().__init__(parent)
        self.info = info
        self._cancel = _ThreadEvent()
        self.setWindowTitle(f"下载 v{info.version}")
        self.setMinimumWidth(440)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(10)

        title = QLabel(f"正在下载 MediaForge v{info.version} 安装包…")
        lay.addWidget(title)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        lay.addWidget(self.bar)

        self.lbl = QLabel(f"0 / {_human(info.asset_size)}")
        self.lbl.setStyleSheet("color:#6B7280;font-size:11px;")
        self.lbl.setAlignment(Qt.AlignRight)
        lay.addWidget(self.lbl)

        btn_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        btn_box.rejected.connect(self._on_cancel)
        lay.addWidget(btn_box)

        self._pool = QThreadPool(self)
        self._bridge = _DownloadBridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.done.connect(self._on_done)

    def start(self) -> None:
        self._pool.start(_DownloadTask(self.info, self._bridge, self._cancel))

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            pct = int(done * 100 / total)
            self.bar.setValue(min(100, pct))
        self.lbl.setText(f"{_human(done)} / {_human(total) if total else '?'}")

    def _on_done(self, result) -> None:
        if isinstance(result, Exception):
            QMessageBox.warning(self, "下载失败", str(result))
            self.reject()
            return
        self._downloaded_path = result
        self.accept()

    def _on_cancel(self) -> None:
        self._cancel.set()
        self.reject()

    @property
    def downloaded_path(self) -> str:
        return getattr(self, "_downloaded_path", "")


# --------------------------------------------------------------------------
# 简单线程取消标志
# --------------------------------------------------------------------------
class _ThreadEvent:
    """不依赖 Qt / threading，给下载任务用的轻量级事件标志。"""
    def __init__(self) -> None:
        self._flag = False
    def set(self) -> None:
        self._flag = True
    def is_set(self) -> bool:
        return self._flag


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def _human(n: int) -> str:
    units = ("B", "KB", "MB", "GB")
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.0f} {u}" if u == "B" else f"{f:.1f} {u}"
        f /= 1024
    return f"{n} B"