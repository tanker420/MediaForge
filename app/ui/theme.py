"""MediaForge 液态玻璃主题（macOS Liquid Glass 风格，浅色 / 深色双主题）。

设计要点：
- 半透明材质层次：窗口背景（自绘光晕渐变）→ 毛玻璃工具栏/底栏 → 玻璃卡片 → 控件；
- 大圆角、发丝线（hairline）、苹果系统色（#007AFF / 深色 #0A84FF 强调色、systemFill 灰）；
- 分段选择器、胶囊按钮、细进度条等 macOS 控件语汇；
- 最小化/最大化/关闭沿用系统原生标题栏（Windows 位置），不做自绘；
- 运行时可切换浅色 / 深色（apply_theme(app, dark)），设置由主窗口持久化。

历史 Bug 根因修正（下拉菜单空白行）：
旧主题在 popup 视图上设置 selection-color: white，但 ::item 子控件被样式化后
选中背景不再取视图的 selection-background-color，导致「白字白底」——选中项
渲染为空白行。正确做法是在 ::item:selected / ::item:hover 上显式声明背景。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication, QWidget

# ---------------------------------------------------------------------------
# 设计令牌（浅色基准，供逻辑代码引用；QSS 使用 _tokens() 的双主题值）
# ---------------------------------------------------------------------------
ACCENT = "#007AFF"            # macOS 系统蓝
ACCENT_DEEP = "#0063E1"
PRIMARY = ACCENT              # 兼容旧引用
PRIMARY_HOVER = ACCENT_DEEP
PRIMARY_PRESSED = "#0050C8"

BG = "#EEF1F6"                # 降级（无系统模糊时）窗口背景
TEXT = "#1D1D1F"              # Apple label color
TEXT_SUB = "#6E6E73"          # Apple secondary label
SUCCESS = "#16A34A"
DANGER = "#DC2626"
WARNING = "#D97706"

_CHECK_SVG = (Path(__file__).resolve().parents[1] / "resources" / "check.svg").as_posix()

_DARK = False                 # 当前主题（运行时由 apply_theme 更新）


def is_dark() -> bool:
    """当前是否为深色主题。"""
    return _DARK


def _tokens(dark: bool) -> dict:
    """双主题颜色令牌表。"""
    if not dark:
        return dict(
            accent="#007AFF", accent_deep="#0063E1", accent_hover="#1E8CFF",
            primary_pressed="#0050C8",
            text="#1D1D1F", text_sub="#6E6E73", text_faint="rgba(60,60,67,120)",
            dis_fg="rgba(60,60,67,60)",
            hairline="rgba(0,0,0,22)",
            glass="rgba(255,255,255,130)", glass_hi="rgba(255,255,255,190)",
            glass_lo="rgba(255,255,255,70)", toolbar="rgba(255,255,255,110)",
            fill="rgba(120,120,128,32)", fill_hi="rgba(120,120,128,52)",
            card_border="rgba(255,255,255,170)",
            ctrl_bg="rgba(255,255,255,180)", ctrl_bg_ro="rgba(120,120,128,20)",
            ctrl_border="rgba(0,0,0,30)",
            popup_bg="rgba(250,251,253,246)", popup_border="rgba(0,0,0,35)",
            menu_bg="rgba(250,251,253,242)",
            item_hover="rgba(0,122,255,24)",
            btn_bg="rgba(255,255,255,170)", btn_hover="rgba(255,255,255,235)",
            btn_pressed="rgba(0,0,0,15)", btn_border="rgba(0,0,0,28)",
            btn_dis_bg="rgba(120,120,128,24)",
            seg_sel_bg="rgba(255,255,255,235)", seg_sel_border="rgba(0,0,0,20)",
            table_sel="rgba(0,122,255,45)", table_alt="rgba(120,120,128,12)",
            header_bg="rgba(255,255,255,90)",
            scroll_handle="rgba(0,0,0,70)", scroll_hover="rgba(0,0,0,110)",
            chk_bg="rgba(255,255,255,220)", chk_border="rgba(0,0,0,60)",
            chk_dis="rgba(120,120,128,40)",
            win_g1="#F6F8FC", win_g2="#EBEFF6", win_g3="#E3E9F2",
            dlg_g1="#F4F6FB", dlg_g2="#E9EDF4",
            msgbox="#F2F4F8", log_bg="rgba(255,255,255,120)",
            badge_ok_bg="rgba(22,163,74,26)", badge_ok_fg="#16A34A",
            badge_ok_border="rgba(22,163,74,70)",
            badge_warn_bg="rgba(217,119,6,26)", badge_warn_fg="#D97706",
            badge_warn_border="rgba(217,119,6,80)",
            drop_fg="rgba(60,60,67,120)", drop_border="rgba(0,0,0,50)",
            drop_bg="rgba(255,255,255,60)",
        )
    return dict(
        accent="#0A84FF", accent_deep="#0060DF", accent_hover="#3B9AFF",
        primary_pressed="#0046B8",
        text="#F5F5F7", text_sub="#98989F", text_faint="rgba(235,235,245,100)",
        dis_fg="rgba(235,235,245,55)",
        hairline="rgba(255,255,255,26)",
        glass="rgba(36,38,46,150)", glass_hi="rgba(66,70,82,190)",
        glass_lo="rgba(255,255,255,16)", toolbar="rgba(28,30,36,150)",
        fill="rgba(120,120,128,56)", fill_hi="rgba(120,120,128,80)",
        card_border="rgba(255,255,255,30)",
        ctrl_bg="rgba(22,24,30,140)", ctrl_bg_ro="rgba(255,255,255,14)",
        ctrl_border="rgba(255,255,255,42)",
        popup_bg="rgba(42,44,52,246)", popup_border="rgba(255,255,255,40)",
        menu_bg="rgba(42,44,52,242)",
        item_hover="rgba(10,132,255,60)",
        btn_bg="rgba(72,76,88,150)", btn_hover="rgba(94,98,112,170)",
        btn_pressed="rgba(0,0,0,60)", btn_border="rgba(255,255,255,36)",
        btn_dis_bg="rgba(120,120,128,32)",
        seg_sel_bg="rgba(84,88,100,235)", seg_sel_border="rgba(0,0,0,60)",
        table_sel="rgba(10,132,255,80)", table_alt="rgba(255,255,255,10)",
        header_bg="rgba(255,255,255,14)",
        scroll_handle="rgba(255,255,255,80)", scroll_hover="rgba(255,255,255,130)",
        chk_bg="rgba(0,0,0,90)", chk_border="rgba(255,255,255,80)",
        chk_dis="rgba(120,120,128,50)",
        win_g1="#26282F", win_g2="#202229", win_g3="#1A1C22",
        dlg_g1="#26282F", dlg_g2="#1E2026",
        msgbox="#23252B", log_bg="rgba(0,0,0,60)",
        badge_ok_bg="rgba(48,209,88,36)", badge_ok_fg="#30D158",
        badge_ok_border="rgba(48,209,88,90)",
        badge_warn_bg="rgba(255,159,10,36)", badge_warn_fg="#FF9F0A",
        badge_warn_border="rgba(255,159,10,90)",
        drop_fg="rgba(235,235,245,100)", drop_border="rgba(255,255,255,60)",
        drop_bg="rgba(255,255,255,12)",
    )


def _font_family() -> str:
    if sys.platform == "darwin":
        return '"PingFang SC", "Hiragino Sans GB", sans-serif'
    if sys.platform.startswith("win"):
        return '"Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif'
    return '"Noto Sans CJK SC", "WenQuanYi Micro Hei", sans-serif'


def apply_theme(app: QApplication, dark: bool = False) -> None:
    """应用全局主题与字体。dark=True 时切换为深色液态玻璃。"""
    global _DARK
    _DARK = bool(dark)
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI",
                      "PingFang SC", "Noto Sans CJK SC"])
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(build_qss(_DARK))


# ---------------------------------------------------------------------------
# 系统级材质（Windows DWM）+ 自绘液态玻璃背景
# ---------------------------------------------------------------------------
def enable_window_glass(window) -> bool:
    """为系统原生标题栏启用 Mica 材质（Win11），客户区玻璃由 GlassBackdrop 自绘。

    不在客户区开透明通道：Qt 原生标题栏 + WA_TranslucentBackground 在部分
    环境无法与 DWM 背景合成，会渲染出黑带。标题栏（最小化/最大化/关闭）
    保持系统原生，位置不变；任何异常都静默降级，不影响主题。
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        if sys.getwindowsversion().build < 22000:
            return False
        hwnd = int(window.winId())
        value = ctypes.c_int(2)  # DWMSBT_MAINWINDOW（Mica）
        return ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 38, ctypes.byref(value), 4) == 0
    except Exception:  # noqa: BLE001
        return False


class GlassBackdrop(QWidget):
    """窗口客户区自绘背景：基底渐变 + 多团柔光，模拟 macOS 液态玻璃的壁纸光晕。

    上层的毛玻璃工具栏 / 玻璃卡片以半透明材质叠加其上，形成层次；
    跟随当前主题（浅 / 深）取色。
    """

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QLinearGradient, QPainter, QRadialGradient
        p = QPainter(self)
        w, h = self.width(), self.height()
        base = QLinearGradient(0, 0, 0, h)
        if is_dark():
            base.setColorAt(0.0, "#26282F")
            base.setColorAt(1.0, "#191B21")
            glows = (((0.16, 0.08, 0.85), (10, 132, 255, 42)),
                     ((0.88, 0.92, 0.80), (90, 200, 250, 34)),
                     ((0.75, 0.10, 0.60), (191, 90, 250, 30)))
        else:
            base.setColorAt(0.0, "#F6F8FC")
            base.setColorAt(1.0, "#E6EBF4")
            glows = (((0.16, 0.08, 0.85), (0, 122, 255, 46)),
                     ((0.88, 0.92, 0.80), (90, 200, 250, 56)),
                     ((0.75, 0.10, 0.60), (191, 90, 250, 26)))
        p.fillRect(self.rect(), base)
        for (cx, cy, r), (rr, gg, bb, aa) in glows:
            g = QRadialGradient(w * cx, h * cy, max(w, h) * r)
            g.setColorAt(0, QColor(rr, gg, bb, aa))
            g.setColorAt(1, QColor(rr, gg, bb, 0))
            p.fillRect(self.rect(), g)
        p.end()


# ---------------------------------------------------------------------------
# QSS
# ---------------------------------------------------------------------------
def build_qss(dark: bool = False) -> str:
    """生成液态玻璃 QSS。dark=True 时输出深色变体。"""
    t = _tokens(dark)
    return f"""
* {{
    font-family: {_font_family()};
    outline: none;
}}
QWidget {{
    background: transparent;
    color: {t['text']};
}}

/* ---------- 窗口基底：渐变（客户区光晕由 GlassBackdrop 自绘） ---------- */
QMainWindow {{
    background: qlineargradient(x1:0, y1:0, x2:0.6, y2:1,
                                stop:0 {t['win_g1']}, stop:0.5 {t['win_g2']}, stop:1 {t['win_g3']});
}}
QDialog {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {t['dlg_g1']}, stop:1 {t['dlg_g2']});
}}

/* ---------- 顶部工具栏（毛玻璃） ---------- */
#AppHeader {{
    background: {t['toolbar']};
    border-bottom: 1px solid {t['hairline']};
}}
#AppTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {t['text']};
}}
#AppSubtitle {{
    font-size: 11px;
    color: {t['text_sub']};
}}
#EnvBadge {{
    background: {t['badge_ok_bg']};
    color: {t['badge_ok_fg']};
    border: 1px solid {t['badge_ok_border']};
    border-radius: 12px;
    padding: 3px 12px;
    font-size: 11px;
    font-weight: 600;
}}
#EnvBadge[warn="true"] {{
    background: {t['badge_warn_bg']};
    color: {t['badge_warn_fg']};
    border-color: {t['badge_warn_border']};
}}
#MenuBtn, #ThemeBtn {{
    background: transparent;
    color: {t['text_sub']};
    border: 1px solid transparent;
    border-radius: 14px;
    font-size: 12px;
    font-weight: 600;
    padding: 0 10px;
    min-height: 28px;
    max-height: 28px;
}}
#MenuBtn {{
    font-size: 16px;
    font-weight: 700;
    padding: 0 8px;
    min-width: 28px;
    max-width: 28px;
}}
#MenuBtn:hover, #ThemeBtn:hover {{
    background: {t['fill']};
    color: {t['text']};
}}
#MenuBtn::menu-indicator {{
    image: none;
}}

/* ---------- 分段选择器（macOS segmented control） ---------- */
QFrame#Segmented {{
    background: {t['fill']};
    border: none;
    border-radius: 9px;
}}
QPushButton#SegBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 5px 20px;
    font-size: 12px;
    font-weight: 600;
    color: {t['text_sub']};
}}
QPushButton#SegBtn:hover {{
    color: {t['text']};
}}
QPushButton#SegBtn:checked {{
    background: {t['seg_sel_bg']};
    border: 1px solid {t['seg_sel_border']};
    color: {t['text']};
}}

/* ---------- 玻璃卡片 ---------- */
QFrame#Card, QGroupBox {{
    background: {t['glass']};
    border: 1px solid {t['card_border']};
    border-radius: 14px;
}}
QGroupBox {{
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}}
QFrame#PreviewCard {{
    background: {t['glass_lo']};
    border: 1px solid {t['hairline']};
    border-radius: 10px;
}}
#PreviewHeader {{
    color: {t['text_sub']};
    font-size: 11px;
    font-weight: 600;
}}
#PreviewCanvas {{
    background: {t['glass_lo']};
    border: 1px solid {t['hairline']};
    border-radius: 10px;
    color: {t['text_faint']};
    font-size: 12px;
}}

/* ---------- 表格 ---------- */
QTableWidget {{
    background: {t['glass_lo']};
    border: 1px solid {t['hairline']};
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: {t['table_sel']};
    selection-color: {t['text']};
    alternate-background-color: {t['table_alt']};
}}
QTableWidget::item {{
    padding: 4px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background: {t['table_sel']};
    color: {t['text']};
}}
QHeaderView::section {{
    background: {t['header_bg']};
    color: {t['text_sub']};
    border: none;
    border-bottom: 1px solid {t['hairline']};
    padding: 7px 8px;
    font-weight: 600;
    font-size: 12px;
}}

/* ---------- 输入控件（玻璃） ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
    background: {t['ctrl_bg']};
    border: 1px solid {t['ctrl_border']};
    border-radius: 9px;
    padding: 5px 10px;
    color: {t['text']};
    selection-background-color: {t['accent']};
}}
QLineEdit:read-only {{
    background: {t['ctrl_bg_ro']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {t['accent']};
}}
QComboBox {{
    /* 覆盖共享输入控件的垂直 padding，popup 留白完全交给 ::item */
    padding-top: 0;
    padding-bottom: 0;
    min-height: 26px;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t['text_sub']};
    margin-right: 8px;
}}
QComboBox:on::down-arrow {{
    border-top-color: {t['accent']};
}}
/* popup：关键修复——选中/悬停态必须在 ::item 上显式声明背景，
   否则选中项白字白底渲染为空白行（历史「下拉空白」Bug 的真正根因）。
   视图本身保持 margin/padding 为 0，避免首项 phantom row。 */
QComboBox QAbstractItemView {{
    background: {t['popup_bg']};
    border: 1px solid {t['popup_border']};
    border-radius: 8px;
    margin: 0;
    padding: 0;
    outline: 0;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    min-height: 20px;
    border: none;
    color: {t['text']};
}}
QComboBox QAbstractItemView::item:hover {{
    background: {t['item_hover']};
}}
QComboBox QAbstractItemView::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {t['accent']}, stop:1 {t['accent_deep']});
    color: white;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border: none;
    border-left: 1px solid {t['hairline']};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border: none;
    border-left: 1px solid {t['hairline']};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid {t['text_sub']};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid {t['text_sub']};
}}

/* ---------- 复选框（macOS 圆角方块） ---------- */
QCheckBox {{
    spacing: 8px;
    color: {t['text']};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid {t['chk_border']};
    background: {t['chk_bg']};
}}
QCheckBox::indicator:hover {{
    border-color: {t['accent']};
}}
QCheckBox::indicator:checked {{
    border: 1px solid {t['accent_deep']};
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {t['accent']}, stop:1 {t['accent_deep']});
    image: url({_CHECK_SVG});
}}
QCheckBox::indicator:disabled {{
    background: {t['chk_dis']};
    border-color: {t['hairline']};
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {t['btn_bg']};
    color: {t['text']};
    border: 1px solid {t['btn_border']};
    border-radius: 9px;
    padding: 6px 14px;
    font-size: 12px;
}}
QPushButton:hover {{
    background: {t['btn_hover']};
}}
QPushButton:pressed {{
    background: {t['btn_pressed']};
}}
QPushButton:disabled {{
    color: {t['dis_fg']};
    background: {t['btn_dis_bg']};
    border-color: {t['hairline']};
}}
QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {t['accent']}, stop:1 {t['accent_deep']});
    color: white;
    border: 1px solid rgba(0,0,0,20);
    border-radius: 10px;
    font-weight: 600;
    padding: 6px 18px;
}}
QPushButton#PrimaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {t['accent_hover']}, stop:1 {t['accent']});
}}
QPushButton#PrimaryBtn:pressed {{
    background: {t['primary_pressed']};
}}
QPushButton#PrimaryBtn:disabled {{
    background: rgba(0,122,255,90);
    color: rgba(255,255,255,200);
    border-color: transparent;
}}

/* ---------- 进度条（细胶囊） ---------- */
QProgressBar {{
    background: {t['fill']};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: {t['text_sub']};
    font-size: 10px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {t['accent']}, stop:1 #5AC8FA);
    border-radius: 5px;
}}

/* ---------- 状态栏 / 底栏 ---------- */
QStatusBar {{
    background: {t['toolbar']};
    border-top: 1px solid {t['hairline']};
    color: {t['text_sub']};
    font-size: 12px;
}}
QStatusBar::item {{
    border: none;
}}
QFrame#FooterBar {{
    background: {t['toolbar']};
    border-top: 1px solid {t['hairline']};
}}
QFrame#FooterBar QPushButton#PrimaryBtn {{
    padding: 9px 28px;
    font-size: 13px;
    border-radius: 10px;
}}

/* ---------- 日志 ---------- */
QTextEdit#LogView {{
    background: {t['log_bg']};
    border: 1px solid {t['hairline']};
    border-radius: 8px;
    color: {t['text_sub']};
    font-size: 12px;
    padding: 6px;
}}

/* ---------- 滚动条（macOS 细条） ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t['scroll_handle']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['scroll_hover']};
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
    background: {t['scroll_handle']};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {t['scroll_hover']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ---------- 提示 ---------- */
QToolTip {{
    background: rgba(29,29,31,225);
    color: #F9FAFB;
    border: none;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ---------- 菜单 ---------- */
QMenu {{
    background: {t['menu_bg']};
    border: 1px solid {t['popup_border']};
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 24px;
    border-radius: 7px;
    color: {t['text']};
}}
QMenu::item:selected {{
    background: {t['accent']};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {t['hairline']};
    margin: 4px 10px;
}}
QMenu::indicator {{
    width: 14px;
    height: 14px;
    margin-left: 8px;
}}

/* ---------- 文本与区块标题 ---------- */
QLabel#SectionTitle {{
    font-size: 13px;
    font-weight: 700;
    color: {t['text']};
}}
QLabel#ParamLabel {{
    font-size: 12px;
    color: {t['text_sub']};
}}
QLabel#DropHint {{
    color: {t['drop_fg']};
    font-size: 13px;
    border: 1px dashed {t['drop_border']};
    border-radius: 12px;
    padding: 20px;
    background: {t['drop_bg']};
}}
QLabel#StatusLabel {{
    color: {t['text_sub']};
    font-size: 12px;
}}

QMessageBox {{
    background: {t['msgbox']};
}}
"""


QSS = build_qss(False)