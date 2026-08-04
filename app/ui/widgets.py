"""现代风格可复用控件：分段选择器、自动参数表单、文件表格。

参数表单完全由 formats.Param 目录驱动（单一事实来源），
新增/调整参数时 UI 自动跟随，无需改动界面代码。
"""
from __future__ import annotations

import os
from typing import Any, Sequence

from PySide6.QtCore import QFileInfo, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import formats as F


# --------------------------------------------------------------------------
# 分段选择器（视频 / 音频 / 图片）
# --------------------------------------------------------------------------
class SegmentedControl(QFrame):
    """胶囊风格的分段单选控件，类似主流应用顶部的类别切换。"""

    changed = Signal(str)

    def __init__(self, options: Sequence[tuple[str, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        for value, label in options:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("SegBtn")
            btn.setProperty("segValue", value)
            self._group.addButton(btn)
            lay.addWidget(btn)
        self._group.buttonClicked.connect(lambda b: self.changed.emit(b.property("segValue")))

    def value(self) -> str | None:
        btn = self._group.checkedButton()
        return btn.property("segValue") if btn else None

    def set_value(self, value: str) -> None:
        for btn in self._group.buttons():
            if btn.property("segValue") == value:
                btn.setChecked(True)
                return


# --------------------------------------------------------------------------
# 自动参数表单
# --------------------------------------------------------------------------
class ParamForm(QWidget):
    """依据 formats.Param 目录自动生成参数编辑控件。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._controls: dict[str, QWidget] = {}
        self._rows: list[QWidget] = []
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(10)

    def clear(self) -> None:
        for row in self._rows:
            self._root.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._controls.clear()

    def set_params(self, params: Sequence[F.Param]) -> None:
        """重建表单。extra_args / overwrite 有专属入口，不再在表单中重复暴露。"""
        self.clear()
        shown = [p for p in params if p.key not in ("extra_args", "overwrite")]
        for p in shown:
            row = self._build_row(p)
            self._root.addWidget(row)
            self._rows.append(row)

    # ---------------- 控件构建 ----------------
    def _build_row(self, p: F.Param) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        label = QLabel(p.label)
        label.setObjectName("ParamLabel")
        label.setMinimumWidth(150)
        label.setMaximumWidth(190)
        label.setToolTip(p.help or "")
        lay.addWidget(label, 0)

        ctrl = self._build_control(p)
        ctrl.setToolTip(p.help or "")
        lay.addWidget(ctrl, 1)
        self._controls[p.key] = ctrl
        return row

    def _build_control(self, p: F.Param) -> QWidget:
        t = p.type
        if t == "bool":
            c = QCheckBox()
            c.setChecked(bool(p.default))
            return c
        if t == "int":
            c = QSpinBox()
            lo = int(p.minimum) if p.minimum is not None else -2_147_483_648
            hi = int(p.maximum) if p.maximum is not None else 2_147_483_647
            c.setRange(lo, hi)
            c.setSingleStep(int(p.step) or 1)
            c.setValue(int(p.default) if p.default is not None else lo)
            return c
        if t == "float":
            c = QDoubleSpinBox()
            lo = p.minimum if p.minimum is not None else -1_000_000.0
            hi = p.maximum if p.maximum is not None else 1_000_000.0
            c.setRange(lo, hi)
            c.setSingleStep(float(p.step or 0.1))
            c.setDecimals(2)
            c.setValue(float(p.default) if p.default is not None else 0.0)
            return c
        if t == "choice":
            c = QComboBox()
            for item in p.choices:
                c.addItem(item if item else "（默认）", item)
            idx = c.findData(str(p.default)) if p.default is not None else -1
            c.setCurrentIndex(max(0, idx))
            return c
        # str
        c = QLineEdit()
        if p.default:
            c.setText(str(p.default))
        return c

    # ---------------- 取值 ----------------
    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, ctrl in self._controls.items():
            if isinstance(ctrl, QCheckBox):
                out[key] = ctrl.isChecked()
            elif isinstance(ctrl, QSpinBox):
                out[key] = ctrl.value()
            elif isinstance(ctrl, QDoubleSpinBox):
                out[key] = ctrl.value()
            elif isinstance(ctrl, QComboBox):
                out[key] = ctrl.currentData() or ""
            else:
                out[key] = ctrl.text().strip()
        return out

    def set_values(self, values: dict[str, Any]) -> None:
        for key, val in values.items():
            ctrl = self._controls.get(key)
            if ctrl is None:
                continue
            if isinstance(ctrl, QCheckBox):
                ctrl.setChecked(bool(val))
            elif isinstance(ctrl, QSpinBox):
                try:
                    ctrl.setValue(int(val))
                except (TypeError, ValueError):
                    pass
            elif isinstance(ctrl, QDoubleSpinBox):
                try:
                    ctrl.setValue(float(val))
                except (TypeError, ValueError):
                    pass
            elif isinstance(ctrl, QComboBox):
                idx = ctrl.findData(str(val))
                if idx >= 0:
                    ctrl.setCurrentIndex(idx)
            elif isinstance(ctrl, QLineEdit):
                ctrl.setText(str(val))

    def set_enabled_all(self, enabled: bool) -> None:
        for ctrl in self._controls.values():
            ctrl.setEnabled(enabled)


# --------------------------------------------------------------------------
# 文件列表表格（支持拖拽）
# --------------------------------------------------------------------------
class FileTable(QTableWidget):
    """转换文件列表：文件名 / 大小 / 输出 / 状态 / 进度。"""

    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(0, 5, parent)
        self.setHorizontalHeaderLabels(["文件", "大小", "输出", "状态", "进度"])
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(40)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.setColumnWidth(4, 150)
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        self._icons = QFileIconProvider()

    # ---------------- 拖拽 ----------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local:
                paths.append(local)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    # ---------------- 行数据 ----------------
    def add_row(self, path: str, size: int, out_ext: str) -> int:
        row = self.rowCount()
        self.insertRow(row)

        item = QTableWidgetItem(self._icons.icon(QFileInfo(path)),
                                os.path.basename(path))
        item.setData(Qt.UserRole, path)
        self.setItem(row, 0, item)

        self.setItem(row, 1, QTableWidgetItem(_human(size)))
        ext_item = QTableWidgetItem(f".{out_ext}")
        ext_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 2, ext_item)

        status_item = QTableWidgetItem("等待中")
        status_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 3, status_item)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        self.setCellWidget(row, 4, bar)
        return row

    def set_status(self, row: int, text: str, color: str | None = None) -> None:
        item = self.item(row, 3)
        if item is None:
            return
        item.setText(text)
        if color:
            item.setForeground(_QColor(color))

    def set_progress(self, row: int, value: int) -> None:
        bar = self.cellWidget(row, 4)
        if isinstance(bar, QProgressBar):
            bar.setValue(max(0, min(100, int(value))))

    def clear_rows(self) -> None:
        self.setRowCount(0)


def _QColor(hex_color: str):
    from PySide6.QtGui import QColor
    return QColor(hex_color)


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"
