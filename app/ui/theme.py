"""MediaForge 现代化界面主题（浅色主流风格）。

基于 QSS 实现：圆角卡片、主题色按钮、清爽表格、胶囊进度条。
字体优先使用微软雅黑（Windows）/ 苹方（macOS）。
"""
from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

PRIMARY = "#2D6CDF"          # 主色（蓝）
PRIMARY_HOVER = "#1E56C8"
PRIMARY_PRESSED = "#1746A8"
BG = "#F3F5F9"               # 窗口背景
CARD = "#FFFFFF"             # 卡片背景
BORDER = "#E5E7EB"           # 边框
TEXT = "#1F2937"             # 主文字
TEXT_SUB = "#6B7280"         # 次要文字
SUCCESS = "#16A34A"
DANGER = "#DC2626"
WARNING = "#D97706"


def _font_family() -> str:
    if sys.platform == "darwin":
        return '"PingFang SC", "Hiragino Sans GB", sans-serif'
    if sys.platform.startswith("win"):
        return '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif'
    return '"Noto Sans CJK SC", "WenQuanYi Micro Hei", sans-serif'


def apply_theme(app: QApplication) -> None:
    """应用全局主题与字体。"""
    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC",
                      "Segoe UI", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(QSS)


QSS = f"""
* {{
    font-family: {_font_family()};
    outline: none;
}}

QMainWindow, QDialog {{
    background: {BG};
}}

/* ---------- 顶部标题栏 ---------- */
#AppHeader {{
    background: {CARD};
    border-bottom: 1px solid {BORDER};
}}
#AppTitle {{
    font-size: 18px;
    font-weight: 700;
    color: {TEXT};
}}
#AppSubtitle {{
    font-size: 11px;
    color: {TEXT_SUB};
}}
#EnvBadge {{
    background: #ECFDF3;
    color: {SUCCESS};
    border: 1px solid #A7F3D0;
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 11px;
}}
#EnvBadge[warn="true"] {{
    background: #FFFBEB;
    color: {WARNING};
    border-color: #FDE68A;
}}

/* ---------- 工具栏按钮 ---------- */
QToolBar {{
    background: {CARD};
    border: none;
    border-bottom: 1px solid {BORDER};
    spacing: 8px;
    padding: 8px 14px;
}}
QToolBar QToolButton {{
    background: transparent;
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
}}
QToolBar QToolButton:hover {{
    background: #EEF2F9;
    border-color: {BORDER};
}}
QToolBar QToolButton:pressed {{
    background: #E2E8F3;
}}
QToolBar QToolButton:disabled {{
    color: #B0B7C3;
}}

/* 主操作按钮（开始转换） */
QToolBar QToolButton#ActStart {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {PRIMARY}, stop:1 {PRIMARY_HOVER});
    color: white;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    padding: 8px 24px;
}}
QToolBar QToolButton#ActStart:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {PRIMARY}, stop:1 {PRIMARY_PRESSED});
}}
QToolBar QToolButton#ActStart:disabled {{
    background: #A9C3F0;
    color: #F0F5FF;
}}
QToolBar QToolButton#ActCancel {{
    color: {DANGER};
    border-color: #F3C1C1;
}}
QToolBar QToolButton#ActCancel:hover {{
    background: #FEF2F2;
}}

/* ---------- 卡片区 ---------- */
QFrame#Card, QGroupBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QGroupBox {{
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 600;
    color: {TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    background: {CARD};
}}

/* ---------- 标签页 ---------- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {CARD};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_SUB};
    border: none;
    padding: 8px 18px;
    margin-right: 2px;
    font-size: 13px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{
    color: {PRIMARY};
    font-weight: 700;
    background: {CARD};
    border: 1px solid {BORDER};
    border-bottom: 2px solid {PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    color: {PRIMARY};
    background: #EEF2F9;
}}

/* ---------- 表格 ---------- */
QTableWidget {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: #E8F0FE;
    selection-color: {TEXT};
    alternate-background-color: #FAFBFC;
}}
QTableWidget::item {{
    padding: 6px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background: #E8F0FE;
    color: {PRIMARY};
    font-weight: 600;
}}
QHeaderView::section {{
    background: #F8FAFD;
    color: {TEXT_SUB};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 8px;
    font-weight: 600;
    font-size: 12px;
}}

/* ---------- 输入控件 ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px 10px;
    color: {TEXT};
    selection-background-color: {PRIMARY};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SUB};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {PRIMARY};
    selection-color: white;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 6px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    border: none;
    background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none;
    background: transparent;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 13px;
}}
QPushButton:hover {{
    background: #F0F4FB;
    border-color: #C9D4E8;
}}
QPushButton:pressed {{
    background: #E2E8F3;
}}
QPushButton:disabled {{
    color: #B0B7C3;
    background: #F5F6F8;
}}
QPushButton#PrimaryBtn {{
    background: {PRIMARY};
    color: white;
    border: none;
    font-weight: 600;
}}
QPushButton#PrimaryBtn:hover {{
    background: {PRIMARY_HOVER};
}}
QPushButton#PrimaryBtn:pressed {{
    background: {PRIMARY_PRESSED};
}}
QPushButton#PrimaryBtn:disabled {{
    background: #A9C3F0;
    color: #F0F5FF;
}}

/* ---------- 进度条 ---------- */
QProgressBar {{
    background: #EDF0F5;
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: {TEXT_SUB};
    font-size: 10px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {PRIMARY}, stop:1 #5B8DEF);
    border-radius: 6px;
}}

/* ---------- 状态栏 ---------- */
QStatusBar {{
    background: {CARD};
    border-top: 1px solid {BORDER};
    color: {TEXT_SUB};
    font-size: 12px;
}}
QStatusBar::item {{
    border: none;
}}

/* ---------- 日志 ---------- */
QTextEdit#LogView {{
    background: #F8FAFD;
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_SUB};
    font-size: 12px;
    padding: 6px;
}}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #C9D2E0;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #A9B6C8;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #C9D2E0;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
}}

/* ---------- 提示 ---------- */
QToolTip {{
    background: #1F2937;
    color: #F9FAFB;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ---------- 菜单 ---------- */
QMenu {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 24px;
    border-radius: 6px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background: #E8F0FE;
    color: {PRIMARY};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ---------- 分段选择器 ---------- */
QFrame#Segmented {{
    background: #E9EDF3;
    border: none;
    border-radius: 10px;
}}
QPushButton#SegBtn {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px 26px;
    font-size: 13px;
    font-weight: 600;
    color: {TEXT_SUB};
}}
QPushButton#SegBtn:hover {{
    color: {PRIMARY};
}}
QPushButton#SegBtn:checked {{
    background: {CARD};
    color: {PRIMARY};
}}

/* ---------- 文本与区块标题 ---------- */
QLabel#SectionTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#ParamLabel {{
    font-size: 12px;
    color: {TEXT_SUB};
}}
QLabel#DropHint {{
    color: #9AA3B2;
    font-size: 13px;
    border: 2px dashed {BORDER};
    border-radius: 10px;
    padding: 20px;
    background: #FAFBFC;
}}
QLabel#StatusLabel {{
    color: {TEXT_SUB};
    font-size: 12px;
}}

/* ---------- 底部操作栏 ---------- */
QFrame#FooterBar {{
    background: {CARD};
    border-top: 1px solid {BORDER};
}}
QFrame#FooterBar QPushButton#PrimaryBtn {{
    padding: 10px 32px;
    font-size: 14px;
    border-radius: 10px;
}}

QMessageBox {{
    background: {CARD};
}}
"""
