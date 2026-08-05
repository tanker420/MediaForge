"""下拉弹层无空白行/一致性的回归测试。

保证修复后的 QSS 不会让 popup 渲染出多余空白行 / 首项空白。
如果将来有人重新引入 padding 或破坏主题，这里会失败。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.theme import apply_theme  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    yield app


@pytest.fixture
def window(qapp):
    w = MainWindow()
    w.show()
    QTimer.singleShot(50, lambda: None)  # 让事件循环跑一拍，触发初始布局
    qapp.processEvents()
    yield w
    w.close()


def _all_combos(window: MainWindow) -> list[tuple[str, QComboBox]]:
    out: list[tuple[str, QComboBox]] = [
        ("preset", window.cb_preset), ("fmt", window.cb_fmt),
        ("vcodec", window.cb_vcodec), ("acodec", window.cb_acodec),
        ("pattern", window.cb_pattern),
    ]
    for key, ctrl in window.form._controls.items():
        if isinstance(ctrl, QComboBox):
            out.append((f"form.{key}", ctrl))
    return out


def test_no_blank_item_text(window: MainWindow) -> None:
    """模型层：每个 combo 项的文本都非空（不应有「空白项」）。"""
    for label, combo in _all_combos(window):
        for i in range(combo.count()):
            text = combo.itemText(i)
            assert text.strip(), (
                f"{label} 第{i}项文本为空 (data={combo.itemData(i)!r})"
            )


def test_popup_first_item_touches_top(window: MainWindow) -> None:
    """渲染层：popup 中第一项必须紧贴 viewport 顶部，不应有 phantom top row。

    QSS padding/margin 残留会让 Qt 6 popup 在首项上方多出一段空行——
    一旦回归，这里会失败。
    """
    window._apply_kind("image")
    window._apply_kind("video")
    if window.cb_preset.count() > 1:
        window.cb_preset.setCurrentIndex(1)

    for label, combo in _all_combos(window):
        if combo.count() == 0:
            continue
        view = combo.view()
        first_idx = view.model().index(0, 0)
        rect = view.visualRect(first_idx)
        if rect.height() <= 0:
            continue
        assert rect.top() <= 1, (
            f"{label} 首项 y={rect.top()}, 距 viewport 顶部有空隙 "
            f"（典型原因：QComboBox QAbstractItemView 残留 padding）"
        )


def test_popup_selected_item_has_explicit_background() -> None:
    """根因回归：QSS 必须在 ::item:selected 上显式声明背景与前景。

    历史「下拉空白」Bug 的真正根因：popup 视图设了 selection-color: white，
    但 ::item 子控件被样式化后选中背景不再取视图的 selection-background-color，
    选中项渲染为白字白底的不可见空白行。若有人删掉 ::item:selected 规则，
    这里会失败。
    """
    from app.ui.theme import QSS

    assert "QComboBox QAbstractItemView::item:selected" in QSS
    seg = QSS.split("QComboBox QAbstractItemView::item:selected", 1)[1]
    seg = seg.split("}", 1)[0]
    assert "background" in seg, "选中项必须显式声明背景，否则会白字白底"
    assert "color" in seg, "选中项必须显式声明前景色"