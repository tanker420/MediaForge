"""MediaForge 主窗口。"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar, QPushButton,
    QSpinBox, QSplitter, QStatusBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QToolBar, QVBoxLayout, QWidget,
)

from ..core import formats as F
from ..core import naming, presets
from ..core.converter import ConversionQueue, Job, Status
from ..core.ffmpeg_builder import preview_command
from ..core.ffprobe import available_encoders, ffmpeg_path, ffmpeg_version, probe
from ..core.naming import human_size, human_time
from .widgets import ParamForm, ScrollGroup

APP_NAME = "MediaForge"
VERSION = "1.0.0"

COL_NAME, COL_TYPE, COL_SIZE, COL_TARGET, COL_STATUS, COL_PROGRESS = range(6)


class Bridge(QObject):
    """把工作线程的回调安全地转发到 GUI 线程。"""

    progress = Signal(object)
    job_done = Signal(object)
    all_done = Signal(object)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {VERSION} — 全能媒体格式转换器")
        self.resize(1180, 760)
        self.setAcceptDrops(True)

        self.queue = ConversionQueue(workers=2)
        self.bridge = Bridge()
        self.bridge.progress.connect(self._on_progress)
        self.bridge.job_done.connect(self._on_job_done)
        self.bridge.all_done.connect(self._on_all_done)
        self.queue.on_progress = self.bridge.progress.emit
        self.queue.on_job_done = self.bridge.job_done.emit
        self.queue.on_all_done = self.bridge.all_done.emit

        self._rows: dict[str, int] = {}
        self._build_ui()
        self._refresh_formats()
        QTimer.singleShot(300, self._check_ffmpeg)

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._build_toolbar()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.total_bar = QProgressBar()
        self.total_bar.setMaximumWidth(220)
        self.total_bar.setValue(0)
        self.status.addPermanentWidget(self.total_bar)
        self.status.showMessage("就绪 — 把文件拖进来即可开始")

    def _build_toolbar(self) -> None:
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_add = QAction("添加文件", self)
        act_add.setShortcut(QKeySequence.StandardKey.Open)
        act_add.triggered.connect(self.add_files)
        tb.addAction(act_add)

        act_dir = QAction("添加文件夹", self)
        act_dir.triggered.connect(self.add_folder)
        tb.addAction(act_dir)

        act_rm = QAction("移除选中", self)
        act_rm.setShortcut(QKeySequence.StandardKey.Delete)
        act_rm.triggered.connect(self.remove_selected)
        tb.addAction(act_rm)

        act_clear = QAction("清空列表", self)
        act_clear.triggered.connect(self.clear_list)
        tb.addAction(act_clear)

        tb.addSeparator()
        self.act_start = QAction("开始转换", self)
        self.act_start.triggered.connect(self.start)
        tb.addAction(self.act_start)

        self.act_cancel = QAction("取消", self)
        self.act_cancel.triggered.connect(self.cancel)
        self.act_cancel.setEnabled(False)
        tb.addAction(self.act_cancel)

        tb.addSeparator()
        act_doctor = QAction("环境检查", self)
        act_doctor.triggered.connect(self.show_doctor)
        tb.addAction(act_doctor)

        act_about = QAction("关于", self)
        act_about.triggered.connect(self.show_about)
        tb.addAction(act_about)

    def _build_left(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["文件名", "类型", "大小", "输出为", "状态", "进度"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for c in (COL_TYPE, COL_SIZE, COL_TARGET, COL_STATUS, COL_PROGRESS):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(self.table, 3)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("转换日志与 ffmpeg 输出会显示在这里")
        self.log.setMaximumHeight(180)
        v.addWidget(self.log, 1)
        return w

    def _build_right(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)

        # ---- 输出设置 ----
        row = QHBoxLayout()
        row.addWidget(QLabel("媒体类型"))
        self.cb_kind = QComboBox()
        self.cb_kind.addItem("视频", F.VIDEO)
        self.cb_kind.addItem("音频", F.AUDIO)
        self.cb_kind.addItem("图片", F.IMAGE)
        self.cb_kind.currentIndexChanged.connect(self._refresh_formats)
        row.addWidget(self.cb_kind, 1)

        row.addWidget(QLabel("输出格式"))
        self.cb_format = QComboBox()
        self.cb_format.currentIndexChanged.connect(self._on_format_changed)
        row.addWidget(self.cb_format, 2)
        v.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("预设"))
        self.cb_preset = QComboBox()
        self.cb_preset.currentIndexChanged.connect(self._apply_preset)
        row2.addWidget(self.cb_preset, 3)
        btn_save = QPushButton("保存为预设")
        btn_save.clicked.connect(self.save_preset)
        row2.addWidget(btn_save)
        v.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("视频编码"))
        self.cb_vcodec = QComboBox()
        self.cb_vcodec.currentIndexChanged.connect(self._on_codec_changed)
        row3.addWidget(self.cb_vcodec, 1)
        row3.addWidget(QLabel("音频编码"))
        self.cb_acodec = QComboBox()
        self.cb_acodec.currentIndexChanged.connect(self._on_codec_changed)
        row3.addWidget(self.cb_acodec, 1)
        v.addLayout(row3)

        # ---- 参数页 ----
        self.tabs = QTabWidget()
        self.form_vcodec = ParamForm()
        self.form_acodec = ParamForm()
        self.form_vfilter = ParamForm(F.VIDEO_FILTER_PARAMS)
        self.form_afilter = ParamForm(F.AUDIO_FILTER_PARAMS)
        self.form_general = ParamForm(F.GENERAL_PARAMS)
        self.form_image = ParamForm(F.IMAGE_PARAMS)

        self.page_vcodec = ScrollGroup("视频编码")
        self.page_vcodec.add_form("视频编码器参数", self.form_vcodec)
        self.page_vcodec.add_stretch()

        self.page_acodec = ScrollGroup("音频编码")
        self.page_acodec.add_form("音频编码器参数", self.form_acodec)
        self.page_acodec.add_stretch()

        self.page_filters = ScrollGroup("处理")
        self.page_filters.add_form("画面处理", self.form_vfilter)
        self.page_filters.add_form("声音处理", self.form_afilter)
        self.page_filters.add_stretch()

        self.page_general = ScrollGroup("通用")
        self.page_general.add_form("通用与高级选项", self.form_general)
        self.page_general.add_stretch()

        self.page_image = ScrollGroup("图片")
        self.page_image.add_form("图片参数", self.form_image)
        self.page_image.add_stretch()

        self.tabs.addTab(self.page_vcodec, "视频编码")
        self.tabs.addTab(self.page_acodec, "音频编码")
        self.tabs.addTab(self.page_filters, "画面 / 声音")
        self.tabs.addTab(self.page_general, "通用")
        self.tabs.addTab(self.page_image, "图片")
        v.addWidget(self.tabs, 1)

        for form in (self.form_vcodec, self.form_acodec, self.form_vfilter,
                     self.form_afilter, self.form_general, self.form_image):
            form.changed.connect(self._update_preview)

        # ---- 输出位置 ----
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("输出目录"))
        self.ed_outdir = QLineEdit()
        self.ed_outdir.setPlaceholderText("留空 = 与源文件同目录")
        self.ed_outdir.textChanged.connect(self._refresh_targets)
        row4.addWidget(self.ed_outdir, 1)
        btn_browse = QPushButton("浏览…")
        btn_browse.clicked.connect(self.pick_outdir)
        row4.addWidget(btn_browse)
        v.addLayout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("命名模板"))
        self.ed_pattern = QLineEdit("{name}")
        self.ed_pattern.setToolTip("可用变量：{name} {ext} {date} {time} {index} {parent}")
        self.ed_pattern.textChanged.connect(self._refresh_targets)
        row5.addWidget(self.ed_pattern, 1)
        row5.addWidget(QLabel("并发"))
        self.sp_workers = QSpinBox()
        self.sp_workers.setRange(1, 16)
        self.sp_workers.setValue(2)
        row5.addWidget(self.sp_workers)
        v.addLayout(row5)

        self.ed_preview = QTextEdit()
        self.ed_preview.setReadOnly(True)
        self.ed_preview.setMaximumHeight(80)
        self.ed_preview.setPlaceholderText("此处显示将要执行的 ffmpeg 命令")
        v.addWidget(self.ed_preview)
        return w

    # ------------------------------------------------------------------
    # 格式 / 编码器联动
    # ------------------------------------------------------------------
    def _current_kind(self) -> str:
        return self.cb_kind.currentData()

    def _refresh_formats(self) -> None:
        kind = self._current_kind()
        self.cb_format.blockSignals(True)
        self.cb_format.clear()
        for f in F.formats_for(kind):
            self.cb_format.addItem(f".{f.ext} — {f.label}", f.ext)
        self.cb_format.blockSignals(False)

        self.cb_preset.blockSignals(True)
        self.cb_preset.clear()
        self.cb_preset.addItem("（不使用预设）", None)
        for p in presets.all_presets(kind):
            self.cb_preset.addItem(p.name, p.name)
        self.cb_preset.blockSignals(False)

        self.tabs.setTabVisible(0, kind == F.VIDEO)
        self.tabs.setTabVisible(1, kind in (F.VIDEO, F.AUDIO))
        self.tabs.setTabVisible(2, kind in (F.VIDEO, F.AUDIO))
        self.tabs.setTabVisible(3, kind in (F.VIDEO, F.AUDIO))
        self.tabs.setTabVisible(4, kind == F.IMAGE)
        if kind == F.IMAGE:
            self.tabs.setCurrentIndex(4)
        else:
            self.tabs.setCurrentIndex(0 if kind == F.VIDEO else 1)

        self._on_format_changed()

    def _on_format_changed(self) -> None:
        ext = self.cb_format.currentData()
        kind = self._current_kind()
        fmt = F.find_format(ext, kind) if ext else None
        avail = available_encoders()

        def fill(cb: QComboBox, codecs: tuple[str, ...], table: dict) -> None:
            cb.blockSignals(True)
            cb.clear()
            for c in codecs:
                info = table.get(c)
                label = info.label if info else c
                if c != "copy" and avail and c not in avail:
                    label += "（当前 FFmpeg 不支持）"
                cb.addItem(label, c)
            cb.setEnabled(cb.count() > 0)
            cb.blockSignals(False)

        if fmt:
            fill(self.cb_vcodec, fmt.video_codecs, F.VIDEO_CODECS)
            fill(self.cb_acodec, fmt.audio_codecs + (("none",) if fmt.audio_codecs else ()),
                 F.AUDIO_CODECS)
        self._on_codec_changed()
        self._refresh_targets()

    def _on_codec_changed(self) -> None:
        v = self.cb_vcodec.currentData()
        a = self.cb_acodec.currentData()
        self.form_vcodec.set_params(F.codec_params(v) if v else ())
        self.form_acodec.set_params(F.codec_params(a) if a else ())
        self._update_preview()

    def _apply_preset(self) -> None:
        name = self.cb_preset.currentData()
        if not name:
            return
        p = presets.find_preset(name)
        if not p:
            return
        idx = self.cb_format.findData(p.ext)
        if idx >= 0:
            self.cb_format.setCurrentIndex(idx)
        vc = p.params.get("video_codec")
        if vc:
            i = self.cb_vcodec.findData(vc)
            if i >= 0:
                self.cb_vcodec.setCurrentIndex(i)
        ac = p.params.get("audio_codec")
        if ac:
            i = self.cb_acodec.findData(ac)
            if i >= 0:
                self.cb_acodec.setCurrentIndex(i)
        for form in (self.form_vcodec, self.form_acodec, self.form_vfilter,
                     self.form_afilter, self.form_general, self.form_image):
            form.set_values(p.params)
        self.status.showMessage(f"已应用预设：{p.name}", 4000)

    # ------------------------------------------------------------------
    # 参数收集
    # ------------------------------------------------------------------
    def collect_params(self) -> dict[str, Any]:
        kind = self._current_kind()
        params: dict[str, Any] = {}
        if kind == F.IMAGE:
            params.update(self.form_image.values())
        else:
            params.update(self.form_general.values())
            params.update(self.form_vfilter.values())
            params.update(self.form_afilter.values())
            params.update(self.form_vcodec.values())
            params.update(self.form_acodec.values())
            params["video_codec"] = self.cb_vcodec.currentData() or ""
            params["audio_codec"] = self.cb_acodec.currentData() or ""
        return params

    def _update_preview(self) -> None:
        ext = self.cb_format.currentData()
        if not ext:
            return
        src = "输入文件." + ("mp4" if self._current_kind() != F.IMAGE else "png")
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if rows:
            item = self.table.item(rows[0].row(), COL_NAME)
            if item:
                src = item.data(Qt.ItemDataRole.UserRole) or src
        dst = naming.build_output_path(src, self.ed_outdir.text(), ext,
                                       self.ed_pattern.text() or "{name}")
        if self._current_kind() == F.IMAGE:
            self.ed_preview.setPlainText(
                "图片转换由内置 Pillow 引擎处理，参数：\n" +
                ", ".join(f"{k}={v}" for k, v in self.collect_params().items()
                          if v not in ("", 0, None, False)))
        else:
            self.ed_preview.setPlainText(preview_command(src, dst, self.collect_params()))

    # ------------------------------------------------------------------
    # 文件列表
    # ------------------------------------------------------------------
    def add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择要转换的文件", "",
                                                "所有媒体文件 (*.*)")
        if files:
            self._add_paths(files)

    def add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if d:
            self._add_paths([d])

    def _add_paths(self, paths: list[str]) -> None:
        allowed = tuple(sorted(set(F.INPUT_VIDEO_EXT + F.INPUT_AUDIO_EXT + F.INPUT_IMAGE_EXT)))
        files = naming.collect_files(paths, True, allowed)
        added = 0
        existing = {self.table.item(r, COL_NAME).data(Qt.ItemDataRole.UserRole)
                    for r in range(self.table.rowCount())}
        for f in files:
            if f in existing:
                continue
            self._add_row(f)
            added += 1
        if added:
            self.status.showMessage(f"已添加 {added} 个文件，共 {self.table.rowCount()} 个", 5000)
            self._refresh_targets()

    def _add_row(self, path: str) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        kind = F.detect_kind(path)
        name_item = QTableWidgetItem(os.path.basename(path))
        name_item.setData(Qt.ItemDataRole.UserRole, path)
        name_item.setToolTip(path)
        self.table.setItem(r, COL_NAME, name_item)
        self.table.setItem(r, COL_TYPE, QTableWidgetItem(
            {"video": "视频", "audio": "音频", "image": "图片"}.get(kind, kind)))
        try:
            size = human_size(os.path.getsize(path))
        except OSError:
            size = "?"
        self.table.setItem(r, COL_SIZE, QTableWidgetItem(size))
        self.table.setItem(r, COL_TARGET, QTableWidgetItem(""))
        self.table.setItem(r, COL_STATUS, QTableWidgetItem(Status.PENDING.value))
        bar = QProgressBar()
        bar.setValue(0)
        bar.setTextVisible(True)
        self.table.setCellWidget(r, COL_PROGRESS, bar)

    def _refresh_targets(self) -> None:
        ext = self.cb_format.currentData()
        if not ext:
            return
        for r in range(self.table.rowCount()):
            src = self.table.item(r, COL_NAME).data(Qt.ItemDataRole.UserRole)
            dst = naming.build_output_path(src, self.ed_outdir.text(), ext,
                                           self.ed_pattern.text() or "{name}",
                                           index=r + 1)
            item = self.table.item(r, COL_TARGET)
            item.setText(os.path.basename(dst))
            item.setToolTip(dst)
        self._update_preview()

    def remove_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self._refresh_targets()

    def clear_list(self) -> None:
        self.table.setRowCount(0)
        self._rows.clear()
        self.queue.jobs.clear()

    def _on_row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        path = self.table.item(rows[0].row(), COL_NAME).data(Qt.ItemDataRole.UserRole)
        kind = F.detect_kind(path)
        idx = self.cb_kind.findData(kind)
        self._update_preview()
        if kind != F.IMAGE:
            info = probe(path)
            bits = [f"{os.path.basename(path)}"]
            if info.duration:
                bits.append(f"时长 {human_time(info.duration)}")
            v = info.video
            if v:
                bits.append(f"{v.codec_name} {v.width}x{v.height} {v.fps:.2f}fps")
            a = info.audio
            if a:
                bits.append(f"{a.codec_name} {a.sample_rate}Hz {a.channels}ch")
            self.status.showMessage("   ".join(bits), 8000)

    def _table_menu(self, pos) -> None:
        menu = QMenu(self)
        act_open = menu.addAction("打开所在文件夹")
        act_info = menu.addAction("查看详细信息")
        act_rm = menu.addAction("从列表移除")
        act = menu.exec(self.table.viewport().mapToGlobal(pos))
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        path = self.table.item(rows[0].row(), COL_NAME).data(Qt.ItemDataRole.UserRole)
        if act == act_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
        elif act == act_info:
            self._show_info(path)
        elif act == act_rm:
            self.remove_selected()

    def _show_info(self, path: str) -> None:
        info = probe(path)
        lines = [f"文件：{path}", f"大小：{human_size(info.size)}",
                 f"容器：{info.format_name or '未知'}",
                 f"时长：{human_time(info.duration)}"]
        for s in info.streams:
            if s.codec_type == "video":
                lines.append(f"视频流 #{s.index}: {s.codec_name} {s.width}x{s.height} "
                             f"{s.fps:.3f}fps {s.pix_fmt}")
            elif s.codec_type == "audio":
                lines.append(f"音频流 #{s.index}: {s.codec_name} {s.sample_rate}Hz "
                             f"{s.channels}声道 {s.language}")
            else:
                lines.append(f"{s.codec_type} #{s.index}: {s.codec_name}")
        QMessageBox.information(self, "媒体信息", "\n".join(lines))

    # ---------------- 拖放 ----------------
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._add_paths(paths)
            event.acceptProposedAction()

    # ------------------------------------------------------------------
    # 转换流程
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "没有文件", "请先添加要转换的文件。")
            return
        ext = self.cb_format.currentData()
        kind = self._current_kind()
        if kind != F.IMAGE and not ffmpeg_path():
            QMessageBox.critical(self, "缺少 FFmpeg",
                                 "未找到 ffmpeg，无法转换音视频。\n"
                                 "请安装 ffmpeg 并加入 PATH，或放入程序 bin 目录。")
            return

        params = self.collect_params()
        self.queue = ConversionQueue(workers=self.sp_workers.value())
        self.queue.on_progress = self.bridge.progress.emit
        self.queue.on_job_done = self.bridge.job_done.emit
        self.queue.on_all_done = self.bridge.all_done.emit
        self._rows.clear()

        taken: set[str] = set()
        for r in range(self.table.rowCount()):
            src = self.table.item(r, COL_NAME).data(Qt.ItemDataRole.UserRole)
            dst = naming.build_output_path(src, self.ed_outdir.text(), ext,
                                           self.ed_pattern.text() or "{name}",
                                           params.get("overwrite", True), r + 1)
            # 不同来源可能生成同名输出（如不同目录的同名文件），去重避免互相覆盖
            dst = naming.dedupe(dst, taken)
            job = Job(src=src, dst=dst, params=dict(params), kind=kind)
            self.queue.add(job)
            self._rows[job.id] = r
            self.table.item(r, COL_STATUS).setText(Status.PENDING.value)
            bar = self.table.cellWidget(r, COL_PROGRESS)
            if bar:
                bar.setValue(0)

        self.log.append(f"=== 开始转换 {len(self.queue.jobs)} 个文件 → .{ext} ===")
        self.act_start.setEnabled(False)
        self.act_cancel.setEnabled(True)
        self.total_bar.setValue(0)
        self.queue.start()

    def cancel(self) -> None:
        self.queue.cancel()
        self.status.showMessage("正在取消…")

    def _on_progress(self, job: Job) -> None:
        r = self._rows.get(job.id)
        if r is None:
            return
        bar = self.table.cellWidget(r, COL_PROGRESS)
        if bar:
            bar.setValue(int(job.progress * 100))
        self.table.item(r, COL_STATUS).setText(
            f"{job.status.value} {job.speed}".strip())

    def _on_job_done(self, job: Job) -> None:
        r = self._rows.get(job.id)
        if r is not None:
            self.table.item(r, COL_STATUS).setText(job.status.value)
            bar = self.table.cellWidget(r, COL_PROGRESS)
            if bar:
                bar.setValue(100 if job.status is Status.DONE else bar.value())
        if job.status is Status.DONE:
            self.log.append(f"✔ {job.name} → {os.path.basename(job.dst)}  "
                            f"{human_size(job.out_size)}  用时 {human_time(job.elapsed)}")
        elif job.status is Status.FAILED:
            self.log.append(f"✘ {job.name} 失败：{job.message}")
        done = sum(1 for j in self.queue.jobs
                   if j.status in (Status.DONE, Status.FAILED, Status.SKIPPED, Status.CANCELED))
        total = len(self.queue.jobs) or 1
        self.total_bar.setValue(int(done / total * 100))

    def _on_all_done(self, jobs: list[Job]) -> None:
        self.act_start.setEnabled(True)
        self.act_cancel.setEnabled(False)
        ok = sum(1 for j in jobs if j.status is Status.DONE)
        failed = sum(1 for j in jobs if j.status is Status.FAILED)
        self.total_bar.setValue(100)
        self.log.append(f"=== 全部结束：成功 {ok}，失败 {failed} ===")
        self.status.showMessage(f"完成！成功 {ok}，失败 {failed}", 10000)

    # ------------------------------------------------------------------
    # 其它
    # ------------------------------------------------------------------
    def pick_outdir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.ed_outdir.setText(d)

    def save_preset(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "保存预设", "预设名称：")
        if not ok or not name.strip():
            return
        user = presets.load_user_presets()
        user = [p for p in user if p.name != name.strip()]
        user.append(presets.Preset(name.strip(), self._current_kind(),
                                   self.cb_format.currentData(),
                                   self.collect_params(), "用户自定义"))
        presets.save_user_presets(user)
        self._refresh_formats()
        self.status.showMessage(f"预设「{name}」已保存", 5000)

    def _check_ffmpeg(self) -> None:
        if not ffmpeg_path():
            QMessageBox.warning(
                self, "未检测到 FFmpeg",
                "没有找到 ffmpeg，音视频转换将无法使用（图片转换不受影响）。\n\n"
                "解决办法：安装 FFmpeg 并加入系统 PATH，"
                "或把 ffmpeg.exe 放到本程序目录下的 bin 文件夹。")

    def show_doctor(self) -> None:
        encs = available_encoders()
        lines = [f"{APP_NAME} {VERSION}",
                 f"Python: {sys.version.split()[0]}",
                 f"FFmpeg: {ffmpeg_version()}",
                 f"FFmpeg 路径: {ffmpeg_path() or '未找到'}",
                 f"可用编码器: {len(encs)} 个"]
        try:
            from PIL import Image
            lines.append(f"Pillow: {Image.__version__}")
        except ImportError:
            lines.append("Pillow: 未安装")
        from ..core.image_engine import HEIF_OK
        lines.append(f"HEIF/AVIF 支持: {'是' if HEIF_OK else '否'}")
        QMessageBox.information(self, "环境检查", "\n".join(lines))

    def show_about(self) -> None:
        QMessageBox.about(
            self, f"关于 {APP_NAME}",
            f"<h3>{APP_NAME} {VERSION}</h3>"
            "<p>全能的视频 / 音频 / 图片格式转换工具，"
            "支持批量转换与全部编码参数自定义。</p>"
            "<p>视频音频由 FFmpeg 驱动，图片由 Pillow 驱动。</p>")


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon = os.path.join(os.path.dirname(__file__), "..", "resources", "icon.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
