"""用户预设管理对话框。

布局：左侧列表（用户预设，按类别分组），
     右侧按钮：保存当前参数为预设、重命名、删除、导出、导入。
内置预设不可编辑，仅在「保存当前参数」时作为同名冲突提示。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import presets as P
from ..core.presets import Preset


class PresetManagerDialog(QDialog):
    """预设管理对话框。修改后通过 all_presets() 重新读取即可生效。"""

    def __init__(self, parent: QWidget | None,
                 current_kind: str,
                 make_from_current: callable) -> None:
        """current_kind: 当前媒体类别，用于过滤显示。

        make_from_current: 回调，签名 () -> dict | None，
          返回当前 UI 参数（包含 video_codec/audio_codec 等），
          用于「保存当前参数为预设」按钮预填表单。
        """
        super().__init__(parent)
        self.setWindowTitle("预设管理")
        self.resize(620, 460)
        self._kind = current_kind
        self._make_from_current = make_from_current
        self._user_presets: list[Preset] = P.load_user_presets()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("用户预设（内置预设不可编辑）")
        title.setStyleSheet("font-weight:600;font-size:13px;color:#1F2937;")
        root.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(12)

        # 左：预设列表
        self.list = QListWidget()
        self.list.setStyleSheet(
            "QListWidget{background:#FFFFFF;border:1px solid #E5E7EB;border-radius:8px;"
            "padding:6px;}QListWidget::item{padding:6px 10px;border-radius:6px;}"
            "QListWidget::item:selected{background:#E8F0FE;color:#2D6CDF;}")
        self.list.itemSelectionChanged.connect(self._on_select)
        body.addWidget(self.list, 2)

        # 右：操作区
        right = QVBoxLayout()
        right.setSpacing(8)

        self.btn_new = QPushButton("保存当前参数为预设…")
        self.btn_rename = QPushButton("重命名…")
        self.btn_delete = QPushButton("删除")
        self.btn_overwrite = QPushButton("用当前参数覆盖")
        self.btn_export = QPushButton("导出…")
        self.btn_import = QPushButton("从文件导入…")
        for b in (self.btn_new, self.btn_rename, self.btn_delete,
                  self.btn_overwrite, self.btn_export, self.btn_import):
            b.setCursor(Qt.PointingHandCursor)
        right.addWidget(self.btn_new)
        right.addWidget(self.btn_overwrite)
        right.addSpacing(4)
        right.addWidget(self.btn_rename)
        right.addWidget(self.btn_delete)
        right.addSpacing(4)
        right.addWidget(self.btn_export)
        right.addWidget(self.btn_import)
        right.addStretch(1)

        body.addLayout(right, 1)
        root.addLayout(body, 1)

        # 详情区
        self.detail = QLabel("")
        self.detail.setStyleSheet("color:#6B7280;font-size:11px;")
        self.detail.setWordWrap(True)
        root.addWidget(self.detail)

        # 关闭按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        btn_box.accepted.connect(self.accept)
        root.addWidget(btn_box)

        # 信号
        self.btn_new.clicked.connect(self._on_new)
        self.btn_rename.clicked.connect(self._on_rename)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_overwrite.clicked.connect(self._on_overwrite)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_import.clicked.connect(self._on_import)

        self._refresh_list()

    # ---------------- 列表 ----------------
    def _refresh_list(self) -> None:
        self.list.clear()
        self._user_presets = P.load_user_presets()
        # 按 kind 分组展示
        shown = [p for p in self._user_presets if p.kind == self._kind]
        other = [p for p in self._user_presets if p.kind != self._kind]
        if not shown and not other:
            placeholder = QListWidgetItem("（暂无用户预设）")
            placeholder.setFlags(Qt.NoItemFlags)
            self.list.addItem(placeholder)
            self._update_buttons(None)
            return
        for p in shown:
            item = QListWidgetItem(f"{p.name}    （{p.ext}）")
            item.setData(Qt.UserRole, p)
            self.list.addItem(item)
        if other:
            sep = QListWidgetItem(f"── 其它类别 ──")
            sep.setFlags(Qt.NoItemFlags)
            sep.setForeground(Qt.gray)
            self.list.addItem(sep)
            for p in other:
                item = QListWidgetItem(f"{p.name}    [其它类别]")
                item.setData(Qt.UserRole, p)
                self.list.addItem(item)
        self._update_buttons(None)

    def _on_select(self) -> None:
        items = self.list.selectedItems()
        preset: Preset | None = items[0].data(Qt.UserRole) if items else None
        self._update_buttons(preset)
        if preset:
            self.detail.setText(
                f"类别：{preset.kind}    输出格式：.{preset.ext}    "
                f"编码：{preset.params.get('video_codec', preset.params.get('audio_codec', '默认'))}"
                + (f"\n说明：{preset.description}" if preset.description else ""))
        else:
            self.detail.setText("")

    def _update_buttons(self, preset: Preset | None) -> None:
        has = preset is not None
        self.btn_rename.setEnabled(has)
        self.btn_delete.setEnabled(has)
        self.btn_overwrite.setEnabled(has)

    def _selected(self) -> Preset | None:
        items = self.list.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    # ---------------- 操作 ----------------
    def _on_new(self) -> None:
        params = self._make_from_current()
        if not params:
            QMessageBox.warning(self, "无法保存",
                                "当前没有可保存的参数。")
            return
        ext = params.get("ext") or "mp4"
        # 弹出名称/说明输入
        dlg = _PresetFormDialog(self, kind=self._kind, ext=ext,
                                params=params, mode="new")
        if dlg.exec() != QInputDialog.Accepted:
            return
        name, desc, chosen_params = dlg.value()
        if not name:
            return
        try:
            P.add_user_preset(Preset(name=name, kind=self._kind, ext=ext,
                                     params=chosen_params, description=desc))
        except ValueError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self._refresh_list()

    def _on_overwrite(self) -> None:
        p = self._selected()
        if not p:
            return
        params = self._make_from_current()
        if not params:
            QMessageBox.warning(self, "无法覆盖", "当前没有可用的参数。")
            return
        ret = QMessageBox.question(
            self, "确认覆盖",
            f"将用当前参数覆盖预设「{p.name}」？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        P.overwrite_user_preset(p.name, Preset(
            name=p.name, kind=p.kind, ext=p.ext,
            params=params, description=p.description))
        self._refresh_list()

    def _on_rename(self) -> None:
        p = self._selected()
        if not p:
            return
        new_name, ok = QInputDialog.getText(self, "重命名预设",
                                            "新名称：", text=p.name)
        if not ok:
            return
        try:
            P.rename_user_preset(p.name, new_name.strip())
        except ValueError as exc:
            QMessageBox.warning(self, "重命名失败", str(exc))
            return
        self._refresh_list()

    def _on_delete(self) -> None:
        p = self._selected()
        if not p:
            return
        ret = QMessageBox.question(
            self, "确认删除",
            f"删除用户预设「{p.name}」？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        P.delete_user_preset(p.name)
        self._refresh_list()

    def _on_export(self) -> None:
        presets = [p for p in self._user_presets if p.kind == self._kind]
        if not presets:
            QMessageBox.information(self, "无可导出项",
                                    "当前类别没有用户预设。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出预设",
            "mediaforge_presets.json",
            "JSON 文件 (*.json)")
        if not path:
            return
        try:
            P.export_presets(presets, path)
        except OSError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "导出成功", f"已导出 {len(presets)} 个预设到\n{path}")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入预设",
            "", "JSON 文件 (*.json)")
        if not path:
            return
        try:
            added, skipped = P.import_presets(path)
        except ValueError as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        msg = f"成功导入 {added} 个预设。"
        if skipped:
            msg += f"\n跳过 {len(skipped)} 个（已存在或格式错误）：{', '.join(skipped[:5])}"
            if len(skipped) > 5:
                msg += "…"
        QMessageBox.information(self, "导入完成", msg)
        self._refresh_list()


class _PresetFormDialog(QDialog):
    """保存新预设时输入名称 + 说明的小对话框。"""

    def __init__(self, parent, *, kind: str, ext: str,
                 params: dict, mode: str = "new") -> None:
        super().__init__(parent)
        self.setWindowTitle("保存预设")
        self.setMinimumWidth(420)
        self._params = params

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        lay.addWidget(QLabel(f"类别：{kind}    输出格式：.{ext}"))

        lay.addWidget(QLabel("预设名称（必填）"))
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("例如：MP4 高压缩")
        lay.addWidget(self.ed_name)

        lay.addWidget(QLabel("说明（可选）"))
        self.ed_desc = QLineEdit()
        self.ed_desc.setPlaceholderText("例如：日常视频转码，画质优先")
        lay.addWidget(self.ed_desc)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        lay.addWidget(btn_box)

    def value(self) -> tuple[str, str, dict]:
        return (self.ed_name.text().strip(),
                self.ed_desc.text().strip(),
                dict(self._params))