"""可复用的界面控件：参数表单、文件列表。"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from ..core.formats import Param


class ParamForm(QWidget):
    """根据 Param 列表自动生成的表单。"""

    changed = Signal()

    def __init__(self, params: tuple[Param, ...] = (), parent: QWidget | None = None):
        super().__init__(parent)
        self._widgets: dict[str, QWidget] = {}
        self._params: dict[str, Param] = {}
        self._layout = QFormLayout(self)
        self._layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.set_params(params)

    # ---------------- 构建 ----------------
    def set_params(self, params: tuple[Param, ...]) -> None:
        values = self.values() if self._widgets else {}
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._widgets.clear()
        self._params.clear()

        for p in params:
            w = self._make_widget(p)
            if w is None:
                continue
            self._widgets[p.key] = w
            self._params[p.key] = p
            label = QLabel(p.label)
            if p.help:
                label.setToolTip(p.help)
                w.setToolTip(p.help)
            self._layout.addRow(label, w)

        # 尽量保留用户之前填过的同名参数
        keep = {k: v for k, v in values.items() if k in self._widgets}
        if keep:
            self.set_values(keep)

    def _make_widget(self, p: Param) -> QWidget | None:
        if p.type == "bool":
            w = QCheckBox()
            w.setChecked(bool(p.default))
            w.toggled.connect(self.changed)
            return w
        if p.type == "int":
            w = QSpinBox()
            w.setRange(int(p.minimum if p.minimum is not None else -10**9),
                       int(p.maximum if p.maximum is not None else 10**9))
            w.setValue(int(p.default or 0))
            w.valueChanged.connect(self.changed)
            return w
        if p.type == "float":
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setSingleStep(p.step or 0.1)
            w.setRange(float(p.minimum if p.minimum is not None else -10**9),
                       float(p.maximum if p.maximum is not None else 10**9))
            w.setValue(float(p.default or 0))
            w.valueChanged.connect(self.changed)
            return w
        if p.type == "choice":
            w = QComboBox()
            w.setEditable(True)
            for c in p.choices:
                w.addItem(c if c else "（默认）", c)
            idx = w.findData(p.default)
            w.setCurrentIndex(idx if idx >= 0 else 0)
            w.currentIndexChanged.connect(self.changed)
            w.editTextChanged.connect(self.changed)
            return w
        w = QLineEdit(str(p.default or ""))
        if p.help:
            w.setPlaceholderText(p.help)
        w.textChanged.connect(self.changed)
        return w

    # ---------------- 读写 ----------------
    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, w in self._widgets.items():
            if isinstance(w, QCheckBox):
                out[key] = w.isChecked()
            elif isinstance(w, QSpinBox):
                out[key] = w.value()
            elif isinstance(w, QDoubleSpinBox):
                out[key] = w.value()
            elif isinstance(w, QComboBox):
                data = w.currentData()
                text = w.currentText()
                out[key] = data if (data is not None and text ==
                                    (data if data else "（默认）")) else text
                if out[key] == "（默认）":
                    out[key] = ""
            elif isinstance(w, QLineEdit):
                out[key] = w.text()
        return out

    def set_values(self, values: dict[str, Any]) -> None:
        for key, val in values.items():
            w = self._widgets.get(key)
            if w is None:
                continue
            w.blockSignals(True)
            try:
                if isinstance(w, QCheckBox):
                    w.setChecked(bool(val))
                elif isinstance(w, QSpinBox):
                    w.setValue(int(float(val or 0)))
                elif isinstance(w, QDoubleSpinBox):
                    w.setValue(float(val or 0))
                elif isinstance(w, QComboBox):
                    idx = w.findData(str(val))
                    if idx >= 0:
                        w.setCurrentIndex(idx)
                    else:
                        w.setCurrentText(str(val))
                elif isinstance(w, QLineEdit):
                    w.setText("" if val is None else str(val))
            except (TypeError, ValueError):
                pass
            finally:
                w.blockSignals(False)
        self.changed.emit()

    def reset_defaults(self) -> None:
        self.set_values({k: p.default for k, p in self._params.items()})


class ScrollGroup(QScrollArea):
    """带标题的可滚动参数区。"""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        self._v = QVBoxLayout(inner)
        self._v.setContentsMargins(4, 4, 4, 4)
        self.setWidget(inner)
        self._title = title

    def add_form(self, title: str, form: ParamForm) -> None:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(form)
        self._v.addWidget(box)

    def add_stretch(self) -> None:
        self._v.addStretch(1)
