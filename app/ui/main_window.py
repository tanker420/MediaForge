"""主窗口：现代化单窗口媒体转换器界面。

本次重构要点：
- 去掉命令行预览框与「自定义 ffmpeg 参数」等专家入口，全程图形化操作；
- 媒体类别（视频/音频/图片）随拖入文件自动切换，无需手动选择；
- 参数表单完全由 formats.Param 目录驱动，UI 与 CLI 保持单一事实来源；
- 转换期间锁定所有会改变任务集合/参数的控件，防止误操作；
- 完成后一键打开输出文件夹，并汇总成功/失败数量。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__ as APP_VERSION
from ..core import formats as F
from ..core import presets as P
from ..core import updater
from ..core.converter import ConversionQueue, Job, Status
from ..core.ffprobe import ffmpeg_path, ffmpeg_version, invalidate_caches, probe
from ..core.naming import build_output_path, collect_files, dedupe, human_size, human_time
from .theme import (DANGER, SUCCESS, TEXT_SUB, WARNING, GlassBackdrop,
                    apply_theme, is_dark, set_titlebar_mode)
from .preset_dialog import PresetManagerDialog
from .preview import MediaPreview
from .update_dialog import (
    UpdateAvailableDialog,
    UpdateProgressDialog,
    _CheckBridge,
    _CheckTask,
)
from .widgets import FileTable, ParamForm, SegmentedControl, SliderParam

KIND_LABEL = {F.VIDEO: "视频", F.AUDIO: "音频", F.IMAGE: "图片"}
_KIND_EXTS = {
    F.VIDEO: F.INPUT_VIDEO_EXT,
    F.AUDIO: F.INPUT_AUDIO_EXT,
    F.IMAGE: F.INPUT_IMAGE_EXT,
}
NAMED_PATTERNS = (
    ("{name}", "原文件名"),
    ("{name}_converted", "原文件名_converted"),
    ("{name}_{date}", "原文件名_日期"),
    ("{parent}_{name}", "上级目录_文件名"),
)

STATUS_COLORS = {
    Status.DONE: SUCCESS,
    Status.FAILED: DANGER,
    Status.CANCELED: TEXT_SUB,
    Status.SKIPPED: WARNING,
}


# --------------------------------------------------------------------------
# 线程桥接：工作线程 → 主线程信号
# --------------------------------------------------------------------------
class _Bridge(QObject):
    progress = Signal(object)
    job_done = Signal(object)
    all_done = Signal(object)


class _ProbeBridge(QObject):
    done = Signal(object)


class _ProbeTask(QRunnable):
    """后台探测单个文件的媒体信息，避免阻塞界面。"""

    def __init__(self, path: str, bridge: _ProbeBridge) -> None:
        super().__init__()
        self.path = path
        self.bridge = bridge

    def run(self) -> None:
        try:
            info = probe(self.path)
        except Exception:  # noqa: BLE001
            info = None
        self.bridge.done.emit(info)


# --------------------------------------------------------------------------
# 主窗口
# --------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MediaForge 全能媒体格式转换器")
        self.resize(1180, 780)
        self.setMinimumSize(980, 640)
        self.setAcceptDrops(True)

        self.settings = QSettings("MediaForge", "MediaForge")
        self.kind = F.VIDEO
        self.files: list[str] = []                 # 全部已添加文件（跨类别保留）
        self._extra: dict = {}                     # 表单未覆盖的预设参数
        self._out_dir: str = self.settings.value("out_dir", "") or ""
        self._busy = False
        self._jobs: list[Job] = []
        self._job_rows: dict[str, int] = {}        # 源路径 -> 表格行号
        self._last_out_dir = ""
        self._probe_target = ""
        self._has_vcodec = False
        self._has_acodec = False

        self.bridge = _Bridge()
        self.bridge.progress.connect(self._on_progress)
        self.bridge.job_done.connect(self._on_job_done)
        self.bridge.all_done.connect(self._on_all_done)
        self.probe_bridge = _ProbeBridge()
        self.probe_bridge.done.connect(self._on_probe_done)
        self.update_bridge = _CheckBridge()
        self.update_bridge.done.connect(self._on_update_check_done)
        self._pool = QThreadPool(self)
        self._update_check_inflight = False

        self._build_ui()
        self._connect()
        self._apply_kind(F.VIDEO)
        self._rebuild_table()
        self._refresh_env()
        if self.settings.value("ui_dark", False, type=bool):
            self._set_dark(True, persist=False)
        self._maybe_check_update_on_startup()

    # ================= 界面构建 =================
    def _build_ui(self) -> None:
        central = GlassBackdrop()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_body(), 1)
        root.addWidget(self._build_footer())
        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪", 3000)

    def _build_header(self) -> QFrame:
        """macOS 工具栏式头部：左品牌、中分段选择器、右状态与菜单。

        最小化/最大化/关闭保持系统原生标题栏（Windows 位置），此处不自绘。
        """
        header = QFrame()
        header.setObjectName("AppHeader")
        header.setFixedHeight(52)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(16, 6, 12, 6)
        lay.setSpacing(10)

        icon = QLabel()
        icon.setPixmap(QIcon(self._icon_path("icon.png")).pixmap(28, 28))
        icon.setFixedSize(28, 28)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("MediaForge")
        title.setObjectName("AppTitle")
        subtitle = QLabel("全能媒体格式转换器 · 视频 / 音频 / 图片")
        subtitle.setObjectName("AppSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        # 类别分段选择器：工具栏居中（macOS Finder 式）
        self.seg = SegmentedControl([(F.VIDEO, "视频"), (F.AUDIO, "音频"), (F.IMAGE, "图片")])

        self.env_badge = QPushButton("FFmpeg …")
        self.env_badge.setObjectName("EnvBadge")
        self.env_badge.setFlat(True)
        self.env_badge.setCursor(Qt.PointingHandCursor)

        self.menu_btn = QToolButton()
        self.menu_btn.setText("⋯")
        self.menu_btn.setObjectName("MenuBtn")
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.menu = QMenu(self.menu_btn)
        self.act_check_update = QAction("检查更新…", self.menu)
        self.act_about = QAction("关于 MediaForge", self.menu)
        self.act_config_dir = QAction("打开配置目录", self.menu)
        self.act_log_dir = QAction("查看日志", self.menu)
        self.menu.addAction(self.act_check_update)
        self.menu.addSeparator()
        self.menu.addAction(self.act_about)
        self.menu.addAction(self.act_config_dir)
        self.menu.addAction(self.act_log_dir)
        self.menu_btn.setMenu(self.menu)

        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("ThemeBtn")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setText("深色")
        self.theme_btn.setToolTip("切换深色 / 浅色主题")

        lay.addWidget(icon)
        lay.addLayout(title_box)
        lay.addStretch(1)
        lay.addWidget(self.seg, 0, Qt.AlignVCenter)
        lay.addStretch(1)
        lay.addWidget(self.theme_btn, 0, Qt.AlignVCenter)
        lay.addWidget(self.env_badge, 0, Qt.AlignVCenter)
        lay.addWidget(self.menu_btn, 0, Qt.AlignVCenter)
        return header

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setObjectName("Body")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)

        # 左：文件列表；右：输出设置（inspector 风格）
        split = QHBoxLayout()
        split.setSpacing(12)
        split.addWidget(self._build_files_card(), 3)
        split.addWidget(self._build_settings_card(), 2)
        lay.addLayout(split, 1)
        return body

    def _kind_note(self) -> QLabel:
        note = QLabel("添加文件后自动识别类别")
        note.setObjectName("AppSubtitle")
        return note

    def _build_files_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("文件列表")
        title.setObjectName("SectionTitle")
        self.lbl_count = QLabel("0 个文件")
        self.lbl_count.setObjectName("AppSubtitle")
        title_row.addWidget(title)
        title_row.addSpacing(8)
        title_row.addWidget(self.lbl_count)
        title_row.addSpacing(12)
        title_row.addWidget(self._kind_note())
        title_row.addStretch(1)

        self.btn_add = QPushButton("＋ 添加文件")
        self.btn_add.setObjectName("PrimaryBtn")
        self.btn_adddir = QPushButton("添加文件夹")
        self.btn_remove = QPushButton("移除选中")
        self.btn_clear = QPushButton("清空")
        for b in (self.btn_adddir, self.btn_remove, self.btn_clear):
            b.setCursor(Qt.PointingHandCursor)
        title_row.addWidget(self.btn_add)
        title_row.addWidget(self.btn_adddir)
        title_row.addWidget(self.btn_remove)
        title_row.addWidget(self.btn_clear)

        self.table = FileTable()
        self.hint = QLabel("将文件或文件夹拖拽到此处\n也可以点击「＋ 添加文件」选择")
        self.hint.setObjectName("DropHint")
        self.hint.setAlignment(Qt.AlignCenter)

        self.preview = MediaPreview()
        self.preview.hide()

        lay.addLayout(title_row)
        lay.addWidget(self.table, 3)
        lay.addWidget(self.preview, 1)
        lay.addWidget(self.hint)
        return card

    def _build_settings_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(16, 14, 16, 16)
        pv.setSpacing(10)

        title = QLabel("输出设置")
        title.setObjectName("SectionTitle")
        pv.addWidget(title)

        # 预设
        pv.addWidget(self._field_label("预设（一键套用常用参数）"))
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        self.cb_preset = QComboBox()
        self.btn_presets = QPushButton("管理…")
        self.btn_presets.setCursor(Qt.PointingHandCursor)
        self.btn_presets.setToolTip("新建、重命名、删除、导入/导出用户预设")
        preset_row.addWidget(self.cb_preset, 1)
        preset_row.addWidget(self.btn_presets)
        pv.addLayout(preset_row)

        # 输出格式
        pv.addWidget(self._field_label("输出格式"))
        self.cb_fmt = QComboBox()
        pv.addWidget(self.cb_fmt)

        # 编码器（视频/音频）
        self.vcodec_label = self._field_label("视频编码器")
        self.cb_vcodec = QComboBox()
        pv.addWidget(self.vcodec_label)
        pv.addWidget(self.cb_vcodec)

        self.acodec_label = self._field_label("音频编码器")
        self.cb_acodec = QComboBox()
        pv.addWidget(self.acodec_label)
        pv.addWidget(self.cb_acodec)

        # 参数表单
        self.form = ParamForm()
        pv.addWidget(self.form)

        # 输出位置
        loc_title = QLabel("输出位置")
        loc_title.setObjectName("SectionTitle")
        pv.addSpacing(6)
        pv.addWidget(loc_title)
        dir_row = QHBoxLayout()
        self.ed_outdir = QLineEdit()
        self.ed_outdir.setReadOnly(True)
        self.ed_outdir.setPlaceholderText("与源文件相同目录")
        self.btn_browse = QPushButton("浏览…")
        self.btn_resetdir = QPushButton("重置")
        dir_row.addWidget(self.ed_outdir, 1)
        dir_row.addWidget(self.btn_browse)
        dir_row.addWidget(self.btn_resetdir)
        pv.addLayout(dir_row)

        # 命名规则：内置默认选项 + 自定义规则
        pv.addWidget(self._field_label("命名规则"))
        self.cb_pattern = QComboBox()
        for pattern, label in NAMED_PATTERNS:
            self.cb_pattern.addItem(label, pattern)
        self.cb_pattern.addItem("自定义…", None)
        pv.addWidget(self.cb_pattern)
        self.ed_pattern = QLineEdit()
        self.ed_pattern.setPlaceholderText(
            "自定义规则，可用变量：{name} {ext} {date} {time} {index} {parent}")
        self.ed_pattern.setToolTip(
            "{name}=原文件名 {ext}=原扩展名 {date}=日期 {time}=时间 "
            "{index}=序号 {parent}=上级目录名；留空回退为原文件名")
        self.ed_pattern.setVisible(False)
        pv.addWidget(self.ed_pattern)
        saved = self.settings.value("pattern", "{name}")
        idx = self.cb_pattern.findData(saved)
        if idx >= 0:
            self.cb_pattern.setCurrentIndex(idx)
        else:
            self.cb_pattern.setCurrentIndex(self.cb_pattern.count() - 1)
            self.ed_pattern.setText(saved)
        self.ed_pattern.setVisible(self.cb_pattern.currentData() is None)

        # 覆盖 + 并行
        opt_row = QHBoxLayout()
        self.chk_overwrite = QCheckBox("覆盖同名文件")
        self.chk_overwrite.setChecked(True)
        opt_row.addWidget(self.chk_overwrite)
        opt_row.addStretch(1)
        opt_row.addWidget(QLabel("并行任务"))
        self.sp_workers = SliderParam(
            F.Param("workers", "并行任务", "int", 2, minimum=1, maximum=8,
                    help="同时转换的任务数，过高可能拖慢单个任务"))
        self.sp_workers.set_value(int(self.settings.value("workers", 2)))
        opt_row.addWidget(self.sp_workers, 1)
        pv.addLayout(opt_row)

        pv.addStretch(1)
        scroll.setWidget(panel)
        outer.addWidget(scroll)
        return card

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("ParamLabel")
        return label

    def _build_footer(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("FooterBar")
        bar.setFixedHeight(56)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        lay.addWidget(self.progress, 1)

        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("StatusLabel")
        self.lbl_status.setMinimumWidth(160)
        lay.addWidget(self.lbl_status)

        self.btn_open = QPushButton("打开输出文件夹")
        self.btn_open.setEnabled(False)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        self.btn_start = QPushButton("开始转换")
        self.btn_start.setObjectName("PrimaryBtn")
        for b in (self.btn_open, self.btn_cancel, self.btn_start):
            b.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.btn_open)
        lay.addWidget(self.btn_cancel)
        lay.addWidget(self.btn_start)
        return bar

    # ================= 信号连接 =================
    def _connect(self) -> None:
        self.seg.changed.connect(self._on_kind_changed)
        self.table.files_dropped.connect(self.add_files)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.btn_add.clicked.connect(self._pick_files)
        self.btn_adddir.clicked.connect(self._pick_folder)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_files)
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_open.clicked.connect(self.open_output_folder)
        self.env_badge.clicked.connect(self._rescan_ffmpeg)
        self.btn_browse.clicked.connect(self._browse_outdir)
        self.btn_resetdir.clicked.connect(self._reset_outdir)

        self.cb_fmt.currentIndexChanged.connect(self._on_fmt_changed)
        self.cb_vcodec.currentIndexChanged.connect(self._on_codec_changed)
        self.cb_acodec.currentIndexChanged.connect(self._on_codec_changed)
        self.cb_preset.currentIndexChanged.connect(self._on_preset)
        self.btn_presets.clicked.connect(self._open_preset_manager)

        self.chk_overwrite.toggled.connect(
            lambda v: self.settings.setValue("overwrite", v))
        self.chk_overwrite.setChecked(
            self.settings.value("overwrite", True, type=bool))
        self.sp_workers.valueChanged.connect(
            lambda v: self.settings.setValue("workers", int(v)))
        self.cb_pattern.currentIndexChanged.connect(self._on_pattern_changed)
        self.ed_pattern.textChanged.connect(lambda _t: self._save_pattern())

        self.act_check_update.triggered.connect(self._on_manual_check_update)
        self.act_about.triggered.connect(self._on_about)
        self.act_config_dir.triggered.connect(self._open_config_dir)
        self.act_log_dir.triggered.connect(self._show_log)
        self.theme_btn.clicked.connect(self._toggle_theme)

        # 快捷键：Delete 移除选中
        act = QAction(self)
        act.setShortcut(Qt.Key_Delete)
        act.triggered.connect(self._remove_selected)
        self.addAction(act)

    # ================= 类别与格式 =================
    @property
    def out_ext(self) -> str:
        return self.cb_fmt.currentData() or ""

    def _on_kind_changed(self, kind: str) -> None:
        if kind == self.kind:
            return
        self._apply_kind(kind)
        self._rebuild_table()

    def _apply_kind(self, kind: str) -> None:
        self.kind = kind
        self._extra = {}

        # 预设
        self.cb_preset.blockSignals(True)
        self.cb_preset.clear()
        self.cb_preset.addItem("自定义…", None)
        for p in P.all_presets(kind):
            self.cb_preset.addItem(p.name, p)
        self.cb_preset.blockSignals(False)

        # 输出格式
        self.cb_fmt.blockSignals(True)
        self.cb_fmt.clear()
        for f in F.formats_for(kind):
            text = f.label if f.ext == f.label.split(" ")[0] else f.label
            self.cb_fmt.addItem(f"{text}  (.{f.ext})", f.ext)
        self.cb_fmt.blockSignals(False)

        self._sync_codec_combos()
        self._rebuild_form()

    def _sync_codec_combos(self) -> None:
        kind, ext = self.kind, self.out_ext
        fmt = F.find_format(ext, kind) if ext else None

        if kind == F.VIDEO and fmt:
            self._has_vcodec = True
            self._has_acodec = bool(fmt.audio_codecs)
        elif kind == F.AUDIO and fmt:
            self._has_vcodec = False
            self._has_acodec = bool(fmt.audio_codecs)
        else:
            self._has_vcodec = False
            self._has_acodec = False

        self.vcodec_label.setVisible(self._has_vcodec)
        self.cb_vcodec.setVisible(self._has_vcodec)
        self.acodec_label.setVisible(self._has_acodec)
        self.cb_acodec.setVisible(self._has_acodec)

        for combo, pool, codec_map, has in (
            (self.cb_vcodec, fmt.video_codecs if fmt else (), F.VIDEO_CODECS, self._has_vcodec),
            (self.cb_acodec, fmt.audio_codecs if fmt else (), F.AUDIO_CODECS, self._has_acodec),
        ):
            combo.blockSignals(True)
            combo.clear()
            if has:
                for enc in pool:
                    codec = codec_map.get(enc)
                    text = codec.label if codec else enc
                    if ffmpeg_path() and enc != "copy" and enc not in _available_encs():
                        text += "（未安装）"
                    combo.addItem(text, enc)
            combo.blockSignals(False)

    def _rebuild_form(self) -> None:
        self.form.set_params(self._form_params())
        self.form.set_values(self._extra)

    def _form_params(self) -> list[F.Param]:
        if self.kind == F.IMAGE:
            return list(F.IMAGE_PARAMS)
        params: list[F.Param] = (list(F.GENERAL_PARAMS)
                                 + list(F.VIDEO_FILTER_PARAMS)
                                 + list(F.AUDIO_FILTER_PARAMS))
        if self._has_vcodec:
            params += list(F.codec_params(self.cb_vcodec.currentData() or ""))
        if self._has_acodec:
            params += list(F.codec_params(self.cb_acodec.currentData() or ""))
        seen: dict[str, F.Param] = {}
        for p in params:
            seen[p.key] = p
        return list(seen.values())

    def _on_fmt_changed(self) -> None:
        self._sync_codec_combos()
        self._extra = {}
        self._rebuild_form()
        self._update_rows_ext()

    def _on_codec_changed(self) -> None:
        self._extra = {}
        self._rebuild_form()

    def _on_preset(self, index: int) -> None:
        preset = self.cb_preset.itemData(index)
        if preset is None:
            return
        if preset.kind != self.kind:
            self._flash("该预设不适用于当前类别，已忽略")
            self.cb_preset.setCurrentIndex(0)
            return
        idx = self.cb_fmt.findData(preset.ext)
        if idx >= 0:
            self.cb_fmt.setCurrentIndex(idx)
        if self._has_vcodec:
            i = self.cb_vcodec.findData(preset.params.get("video_codec", ""))
            if i >= 0:
                self.cb_vcodec.setCurrentIndex(i)
        if self._has_acodec:
            i = self.cb_acodec.findData(preset.params.get("audio_codec", ""))
            if i >= 0:
                self.cb_acodec.setCurrentIndex(i)
        self._extra = {k: v for k, v in preset.params.items()
                       if k not in ("video_codec", "audio_codec")}
        self._rebuild_form()
        self._flash(f"已应用预设「{preset.name}」，可继续微调参数")

    # ================= 文件管理 =================
    # ---------------- 预设管理 ----------------
    def _make_current_params(self) -> dict:
        """把当前 UI 上的所有参数汇总成 dict（用于「保存为预设」）。"""
        params = self._collect_params()
        params["ext"] = self.out_ext or "mp4"
        params.pop("overwrite", None)
        return params

    def _open_preset_manager(self) -> None:
        dlg = PresetManagerDialog(self, current_kind=self.kind,
                                  make_from_current=self._make_current_params)
        dlg.exec()
        # 用户增删预设后刷新下拉
        self._apply_kind(self.kind)
    def _visible_files(self) -> list[str]:
        pool = _KIND_EXTS[self.kind]
        return [f for f in self.files if F.input_ext(f) in pool]

    def add_files(self, paths: list[str]) -> None:
        files: list[str] = []
        dirs: list[str] = []
        for p in paths:
            if os.path.isfile(p):
                files.append(os.path.abspath(p))
            elif os.path.isdir(p):
                dirs.append(p)
        if dirs:
            files += collect_files(dirs, recursive=True)

        # 先按真实类别过滤，确定首个文件所属类别
        valid = [f for f in files if any(
            F.input_ext(f) in pool for pool in _KIND_EXTS.values())]
        if not valid:
            self._flash("没有找到可转换的媒体文件")
            return

        # 类别自动切换：以第一个文件为准
        first_kind = F.detect_kind(valid[0])
        if first_kind != self.kind:
            self._apply_kind(first_kind)
            self.seg.set_value(first_kind)
            self._rebuild_table()

        pool = _KIND_EXTS[self.kind]
        matched = [f for f in valid if F.input_ext(f) in pool]
        existing = set(self.files)
        new = [f for f in matched if f not in existing]
        skipped = len(matched) - len(new)
        self.files.extend(new)
        self._rebuild_table()

        if new:
            self._flash(f"已添加 {len(new)} 个文件" +
                        (f"，忽略 {skipped} 个不匹配的文件" if skipped else ""))
        else:
            self._flash("所选文件已在列表中或与当前类别不匹配")

    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择要转换的媒体文件",
            self.settings.value("last_open_dir", os.path.expanduser("~")),
            "媒体文件 (*.*)")
        if paths:
            self.settings.setValue("last_open_dir", os.path.dirname(paths[0]))
            self.add_files(paths)

    def _pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "选择要批量转换的文件夹",
            self.settings.value("last_open_dir", os.path.expanduser("~")))
        if d:
            self.add_files([d])

    def _remove_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectionModel().selectedRows()},
                      reverse=True)
        for row in rows:
            item = self.table.item(row, 0)
            if item is None:
                continue
            path = item.data(Qt.UserRole)
            if path in self.files:
                self.files.remove(path)
        self._rebuild_table()

    def _clear_files(self) -> None:
        self.files.clear()
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self.table.clear_rows()
        self._job_rows.clear()
        visible = self._visible_files()
        for path in visible:
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            row = self.table.add_row(path, size, self.out_ext)
            self._job_rows[path] = row
        self.hint.setVisible(not visible)
        self.lbl_count.setText(f"{len(visible)} 个文件")

    def _update_rows_ext(self) -> None:
        for path, row in self._job_rows.items():
            item = self.table.item(row, 2)
            if item is not None:
                item.setText(f".{self.out_ext}")

    # ================= 输出设置 =================
    def _browse_outdir(self) -> None:
        start = self._out_dir or self.settings.value("last_open_dir", os.path.expanduser("~"))
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", start)
        if d:
            self._set_out_dir(os.path.abspath(d))

    def _set_out_dir(self, d: str) -> None:
        self._out_dir = d
        self.ed_outdir.setText(d)
        self.settings.setValue("out_dir", d)

    def _reset_outdir(self) -> None:
        self._out_dir = ""
        self.ed_outdir.clear()
        self.settings.setValue("out_dir", "")

    # ---------------- 命名规则 ----------------
    def _on_pattern_changed(self) -> None:
        self.ed_pattern.setVisible(self.cb_pattern.currentData() is None)
        self._save_pattern()

    def _save_pattern(self) -> None:
        self.settings.setValue("pattern", self._current_pattern())

    def _current_pattern(self) -> str:
        data = self.cb_pattern.currentData()
        if data is not None:
            return str(data)
        return self.ed_pattern.text().strip() or "{name}"

    # ================= 转换执行 =================
    def _collect_params(self) -> dict:
        d = F.default_params_for(self.kind)
        d.update(self.form.values())
        d.update(self._extra)
        if self._has_vcodec:
            d["video_codec"] = self.cb_vcodec.currentData() or ""
        if self._has_acodec:
            d["audio_codec"] = self.cb_acodec.currentData() or ""
        d["overwrite"] = self.chk_overwrite.isChecked()
        return d

    def _start(self) -> None:
        files = self._visible_files()
        if not files:
            QMessageBox.information(self, "提示", "请先添加要转换的文件。")
            return
        if self.kind != F.IMAGE and not ffmpeg_path():
            ret = QMessageBox.warning(
                self, "缺少 FFmpeg",
                "未检测到 FFmpeg。\n\n视频 / 音频转换需要 FFmpeg，"
                "请安装后点击右上角的 FFmpeg 状态标签重新检测。\n\n是否仍要继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                return

        ext = self.out_ext
        if not ext:
            QMessageBox.warning(self, "提示", "请先选择输出格式。")
            return

        params = self._collect_params()
        overwrite = self.chk_overwrite.isChecked()
        taken: set[str] = set()
        jobs: list[Job] = []
        for i, src in enumerate(files, 1):
            out_dir = self._out_dir or os.path.dirname(src)
            dst = build_output_path(src, out_dir, ext, self._current_pattern(),
                                    overwrite=overwrite, index=i)
            dst = dedupe(dst, taken)
            jobs.append(Job(src=src, dst=dst, params=dict(params), kind=self.kind))

        self._jobs = jobs
        self.queue = ConversionQueue(workers=max(1, self.sp_workers.value()))
        self.queue.on_progress = lambda j: self.bridge.progress.emit(j)
        self.queue.on_job_done = lambda j: self.bridge.job_done.emit(j)
        self.queue.on_all_done = lambda js: self.bridge.all_done.emit(js)
        for j in jobs:
            self.queue.add(j)

        self._set_busy(True)
        self.progress.setValue(0)
        self.lbl_status.setText(f"开始转换 {len(jobs)} 个文件…")
        self.queue.start()

    def _cancel(self) -> None:
        self.queue.cancel()
        self.btn_cancel.setEnabled(False)
        self.lbl_status.setText("正在取消…")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for w in (self.seg, self.btn_add, self.btn_adddir, self.btn_remove,
                  self.btn_clear, self.cb_preset, self.btn_presets, self.cb_fmt,
                  self.cb_vcodec, self.cb_acodec, self.ed_outdir, self.btn_browse,
                  self.btn_resetdir, self.cb_pattern, self.ed_pattern,
                  self.chk_overwrite, self.sp_workers):
            w.setEnabled(not busy)
        self.form.set_enabled_all(not busy)
        self.btn_start.setEnabled(not busy)
        self.btn_start.setText("转换中…" if busy else "开始转换")
        self.btn_cancel.setEnabled(busy)

    # ---------------- 回调（主线程） ----------------
    def _on_progress(self, job: Job) -> None:
        row = self._job_rows.get(job.src)
        if row is not None:
            self.table.set_progress(row, job.progress * 100)
        pct = int(job.progress * 100)
        extra = f"  {job.speed}" if job.speed else ""
        self.lbl_status.setText(f"转换中：{job.name}  {pct}%{extra}")

    def _on_job_done(self, job: Job) -> None:
        row = self._job_rows.get(job.src)
        if row is None:
            return
        self.table.set_status(row, job.status.value, STATUS_COLORS.get(job.status))
        if job.status is Status.DONE:
            self.table.set_progress(row, 100)
        if job.status is Status.FAILED:
            item = self.table.item(row, 3)
            if item is not None:
                item.setToolTip(job.message)

    def _on_all_done(self, jobs: list[Job]) -> None:
        self._set_busy(False)
        done = [j for j in jobs if j.status is Status.DONE]
        failed = [j for j in jobs if j.status is Status.FAILED]
        canceled = [j for j in jobs if j.status is Status.CANCELED]
        skipped = [j for j in jobs if j.status is Status.SKIPPED]

        if jobs:
            self._last_out_dir = self._out_dir or os.path.dirname(jobs[0].dst)
        self.btn_open.setEnabled(bool(self._last_out_dir))

        if canceled:
            self.lbl_status.setText(f"已取消：完成 {len(done)} 个")
            self.progress.setValue(0)
            self._flash("转换已取消")
            return
        self.progress.setValue(100)
        self.lbl_status.setText(f"全部完成：成功 {len(done)} · 失败 {len(failed)} · 跳过 {len(skipped)}")

        if not failed:
            QMessageBox.information(
                self, "转换完成",
                f"全部处理完成！\n\n成功 {len(done)} 个，跳过 {len(skipped)} 个。")
        else:
            QMessageBox.warning(
                self, "转换完成",
                f"处理结束，有 {len(failed)} 个文件失败：\n\n"
                + "\n".join(f"· {j.name}：{j.message}" for j in failed[:8])
                + ("\n…" if len(failed) > 8 else ""))

    def _on_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.preview.hide()
            return
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return
        path = item.data(Qt.UserRole)
        if not path:
            return
        if path == self._probe_target:
            return
        self._probe_target = path
        self._pool.start(_ProbeTask(path, self.probe_bridge))
        # 显示预览面板并触发后台生成
        self.preview.show()
        self.preview.show_file(path)

    def _on_probe_done(self, info) -> None:
        if info is None or getattr(info, "path", None) != self._probe_target:
            return
        parts: list[str] = []
        if info.has_video:
            v = info.video
            parts.append(f"{v.width}×{v.height}" if v.width and v.height else v.codec_name)
            if v.fps:
                parts.append(f"{v.fps:g} fps")
        if info.has_audio:
            a = info.audio
            parts.append(a.codec_name)
            if a.sample_rate:
                parts.append(f"{a.sample_rate / 1000:g} kHz")
        if info.duration:
            parts.append(human_time(info.duration))
        if info.size:
            parts.append(human_size(info.size))
        self.statusBar().showMessage("  ".join(parts) if parts else "已读取媒体信息", 8000)

    # ================= 其它 =================
    def _toggle_theme(self) -> None:
        self._set_dark(not is_dark())

    def _set_dark(self, dark: bool, persist: bool = True) -> None:
        """应用深 / 浅色液态玻璃主题；persist=True 时记住偏好。"""
        apply_theme(QApplication.instance(), dark)
        set_titlebar_mode(self, dark)
        if persist:
            self.settings.setValue("ui_dark", dark)
        self.theme_btn.setText("浅色" if dark else "深色")
        self.theme_btn.setToolTip("切换到浅色主题" if dark else "切换到深色主题")
        cw = self.centralWidget()
        if cw is not None:
            cw.update()
        self._flash("已切换为深色主题" if dark else "已切换为浅色主题", 2000)

    def open_output_folder(self) -> None:
        d = self._last_out_dir or self._out_dir
        if not d and self._jobs:
            d = os.path.dirname(self._jobs[0].dst)
        if not d or not os.path.isdir(d):
            self._flash("还没有可打开的输出目录")
            return
        try:
            if sys.platform == "win32":
                os.startfile(d)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
        except OSError as exc:
            QMessageBox.warning(self, "无法打开文件夹", str(exc))

    def _rescan_ffmpeg(self) -> None:
        global _enc_cache
        invalidate_caches()
        _enc_cache = None
        self._refresh_env()
        self._sync_codec_combos()
        self._flash("已重新检测 FFmpeg")

    def _refresh_env(self) -> None:
        ver = ffmpeg_version()
        if ver and ver != "未安装":
            self.env_badge.setText("FFmpeg 已就绪")
            self.env_badge.setProperty("warn", False)
            self.env_badge.setToolTip(ver)
        else:
            self.env_badge.setText("未检测到 FFmpeg")
            self.env_badge.setProperty("warn", True)
            self.env_badge.setToolTip("视频/音频转换需要 FFmpeg，点击重新检测")
        self.env_badge.style().unpolish(self.env_badge)
        self.env_badge.style().polish(self.env_badge)

    def _flash(self, text: str, msecs: int = 5000) -> None:
        self.statusBar().showMessage(text, msecs)

    @staticmethod
    def _icon_path(name: str) -> str:
        return str(Path(__file__).resolve().parents[1] / "resources" / name)

    # ---------------- 拖拽（窗口级） ----------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
        if paths:
            self.add_files(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def closeEvent(self, event) -> None:
        if self._busy:
            ret = QMessageBox.question(
                self, "确认退出",
                "有任务正在转换，退出将中断它们。确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()


# ---------------- 更新检查 ----------------
    def _maybe_check_update_on_startup(self) -> None:
        """启动后静默检查更新，受 auto_check_updates 与节流控制。"""
        if not self.settings.value("auto_check_updates", True, type=bool):
            return
        # 节流：24 小时内最多检查一次（last_check 存 QDateTime 字符串）
        from datetime import datetime, timedelta
        last = self.settings.value("last_update_check", "")
        try:
            last_dt = datetime.fromisoformat(last) if last else datetime.min
        except ValueError:
            last_dt = datetime.min
        if datetime.now() - last_dt < timedelta(hours=24):
            return
        # 延迟 3s 启动检查，避免阻塞 UI 初始化
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, self._kick_update_check)

    def _kick_update_check(self, *, manual: bool = False) -> None:
        """实际发起一次后台检查。manual=True 强制刷新节流。"""
        if self._update_check_inflight:
            if manual:
                self._flash("上一次检查还未完成")
            return
        self._update_check_inflight = True
        if manual:
            self._flash("正在检查更新…")
        self._pool.start(_CheckTask(APP_VERSION, self.update_bridge))

    def _on_manual_check_update(self) -> None:
        self._kick_update_check(manual=True)

    def _on_update_check_done(self, info) -> None:
        self._update_check_inflight = False
        from datetime import datetime
        self.settings.setValue("last_update_check", datetime.now().isoformat(timespec="seconds"))
        if info is None:
            self._flash("已是最新版本" if not self.settings.value(
                "_last_update_was_manual", False) else "已是最新版本")
            return
        self._prompt_update(info)

    def _prompt_update(self, info: updater.UpdateInfo) -> None:
        """弹出更新对话框，根据用户选择下载并（可选）安装。"""
        dlg = UpdateAvailableDialog(self, info, APP_VERSION)
        dlg.exec()
        if dlg.choice == "later":
            return
        # 下载
        dlg_dl = UpdateProgressDialog(self, info)
        dlg_dl.start()
        if dlg_dl.exec() != UpdateProgressDialog.Accepted:
            return
        path = dlg_dl.downloaded_path
        if dlg.choice == "download":
            self._flash(f"安装包已下载到 {path}")
            self._reveal_in_explorer(path)
            return
        # install：退出应用，让安装器接管
        self._flash("即将退出并启动安装程序…")
        QTimer = __import__("PySide6.QtCore", fromlist=["QTimer"]).QTimer
        QTimer.singleShot(800, lambda: updater.launch_installer_and_exit(path))

    def _on_about(self) -> None:
        QMessageBox.about(self, "关于 MediaForge",
            f"<h3>MediaForge 全能媒体格式转换器</h3>"
            f"<p>版本 <b>v{APP_VERSION}</b></p>"
            f"<p>开源协议：GPL-3.0</p>"
            f"<p>仓库：<a href='https://github.com/{updater.GITHUB_REPO}'>"
            f"github.com/{updater.GITHUB_REPO}</a></p>"
            f"<p>基于 Python + PySide6 + FFmpeg + Pillow</p>")

    def _open_config_dir(self) -> None:
        from ..core.presets import config_dir
        path = str(config_dir())
        try:
            if sys.platform == "win32":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as exc:
            QMessageBox.warning(self, "无法打开", str(exc))

    def _show_log(self) -> None:
        """提示用户在配置目录中查看日志（当前实现：打开配置目录）。"""
        self._open_config_dir()

    def _reveal_in_explorer(self, path: str) -> None:
        """在系统文件管理器中定位文件。"""
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except OSError:
            pass


_enc_cache: frozenset[str] | None = None


def _available_encs() -> frozenset[str]:
    """当前 ffmpeg 可用编码器（带缓存，切换 ffmpeg 后由 _rescan_ffmpeg 清除）。"""
    global _enc_cache
    if _enc_cache is None:
        from ..core.ffprobe import available_encoders
        _enc_cache = available_encoders()
    return _enc_cache


def run() -> int:
    """启动图形界面。"""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            try:
                import ctypes
                ctypes.windll.shell32.SetProcessDPIAware()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
    from PySide6.QtWidgets import QApplication

    from .theme import apply_theme, enable_window_glass

    app = QApplication(sys.argv)
    app.setApplicationName("MediaForge")
    app.setOrganizationName("MediaForge")
    app.setWindowIcon(QIcon(MainWindow._icon_path("icon.png")))
    apply_theme(app)
    window = MainWindow()
    enable_window_glass(window)
    window.show()
    return app.exec()
