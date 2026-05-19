from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtGui import QColor

# Palette
ACCENT  = "#c41c1c"
BRIGHT  = "#ff5555"
DARK    = "#8a1010"
BORDER  = "rgba(200,25,25,80)"
BACT    = "rgba(255,70,70,200)"
SEL_BG  = "rgba(185,22,22,120)"
HDR_A   = "rgba(200,25,25,210)"
HDR_B   = "rgba(140,15,15,230)"

# Convex button — bright highlight on top, deep shadow on bottom
BTN = """
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0.00 rgba(255,255,255,55),
        stop:0.06 rgba(255,80,80,230),
        stop:0.50 rgba(185,22,22,220),
        stop:0.92 rgba(100,8,8,240),
        stop:1.00 rgba(30,0,0,255));
    border-top:    1px solid rgba(255,120,120,160);
    border-left:   1px solid rgba(255,80,80,100);
    border-right:  1px solid rgba(120,10,10,200);
    border-bottom: 2px solid rgba(20,0,0,255);
    border-radius: 10px;
    padding: 9px 22px;
    color: #ffffff;
    font-weight: bold;
    letter-spacing: 0.4px;
"""
BTN_HOVER = """
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0.00 rgba(255,255,255,80),
        stop:0.06 rgba(255,110,110,240),
        stop:0.50 rgba(210,30,30,230),
        stop:0.92 rgba(130,12,12,245),
        stop:1.00 rgba(40,0,0,255));
    border-top:    1px solid rgba(255,150,150,200);
    border-left:   1px solid rgba(255,100,100,120);
    border-right:  1px solid rgba(140,12,12,210);
    border-bottom: 2px solid rgba(20,0,0,255);
    border-radius: 10px;
    padding: 9px 22px;
    color: #ffffff;
    font-weight: bold;
"""
BTN_PRESSED = """
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(60,5,5,255),
        stop:1 rgba(120,10,10,255));
    border-top:    1px solid rgba(80,5,5,200);
    border-bottom: 1px solid rgba(220,30,30,150);
    border-left:   1px solid rgba(80,5,5,150);
    border-right:  1px solid rgba(80,5,5,150);
    border-radius: 10px;
    padding: 10px 22px 8px 22px;
    color: #cc9999;
    font-weight: bold;
"""

STYLESHEET = f"""
QMainWindow, QDialog {{
    background: #07070d;
}}
QWidget {{
    background: transparent;
    color: #eeeef5;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}}

/* ── Labels ───────────────────────────────────────────── */
QLabel {{ color: #7878a0; background: transparent; }}

/* ── Inputs ───────────────────────────────────────────── */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: rgba(6,4,4,230);
    border: 1px solid {BORDER};
    border-top: 1px solid rgba(255,40,40,60);
    border-radius: 10px;
    padding: 8px 12px;
    color: #eeeef5;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {BACT};
    background: rgba(10,4,4,240);
}}

/* ── Convex Buttons ───────────────────────────────────── */
QPushButton {{ {BTN} }}
QPushButton:hover {{ {BTN_HOVER} }}
QPushButton:pressed {{ {BTN_PRESSED} }}
QPushButton:disabled {{
    background: rgba(25,20,20,180);
    border: 1px solid rgba(70,60,60,80);
    color: rgba(100,90,90,150);
    border-radius: 10px;
    padding: 9px 22px;
}}

/* Secondary (тёмная, ненавязчивая) */
QPushButton[class="secondary"] {{
    background: rgba(28,7,7,200);
    border: 1px solid rgba(180,25,25,70);
    border-bottom: 2px solid rgba(8,0,0,200);
    border-radius: 10px;
    padding: 8px 18px;
    color: #aa6060;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QPushButton[class="secondary"]:hover {{
    background: rgba(48,10,10,220);
    border-color: rgba(220,40,40,110);
    color: #ee9090;
}}
QPushButton[class="secondary"]:pressed {{
    background: rgba(18,4,4,230);
    color: #884040;
}}

/* Flat / danger variants */
QPushButton[class="flat"] {{
    background: transparent;
    border: none;
    color: {BRIGHT};
    font-weight: bold;
    padding: 6px 14px;
}}
QPushButton[class="flat"]:hover {{ color: #ff8888; background: rgba(255,50,50,15); border-radius: 6px; }}
QPushButton[class="flat"]:pressed {{
    color: #aa4444;
    background: rgba(120,10,10,30);
    border-radius: 6px;
    padding: 8px 14px 4px 14px;
}}
QPushButton[class="danger"] {{
    background: transparent;
    border: 1px solid rgba(200,25,25,120);
    border-radius: 8px;
    color: {BRIGHT};
    padding: 6px 14px;
    font-weight: bold;
}}
QPushButton[class="danger"]:hover {{
    background: rgba(200,25,25,40);
    border-color: {BACT};
}}
QPushButton[class="danger"]:pressed {{
    background: rgba(100,8,8,80);
    border-color: rgba(140,15,15,150);
    color: #884444;
    padding: 8px 14px 4px 14px;
}}
QPushButton[class="launch"] {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0.00 rgba(255,255,255,70),
        stop:0.06 rgba(255,90,90,240),
        stop:0.50 rgba(185,22,22,230),
        stop:0.92 rgba(90,6,6,250),
        stop:1.00 rgba(20,0,0,255));
    border-top:    1px solid rgba(255,140,140,180);
    border-bottom: 3px solid rgba(10,0,0,255);
    border-left:   1px solid rgba(200,60,60,120);
    border-right:  1px solid rgba(100,8,8,200);
    border-radius: 10px;
    padding: 12px 28px;
    font-size: 14px;
    font-weight: bold;
    color: #ffffff;
}}
QPushButton[class="launch"]:hover {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0.00 rgba(255,255,255,90),
        stop:0.06 rgba(255,120,120,250),
        stop:0.50 rgba(220,32,32,240),
        stop:0.92 rgba(120,10,10,255),
        stop:1.00 rgba(30,0,0,255));
}}
QPushButton[class="launch"]:pressed {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(40,3,3,255),
        stop:1 rgba(100,8,8,255));
    border-top:    1px solid rgba(60,4,4,200);
    border-bottom: 1px solid rgba(200,30,30,150);
    border-left:   1px solid rgba(60,4,4,150);
    border-right:  1px solid rgba(60,4,4,150);
    border-radius: 10px;
    padding: 14px 28px 10px 28px;
    color: #aa6666;
    font-weight: bold;
}}

/* ── Checkable plan buttons ───────────────────────────── */
QPushButton:checkable:checked {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(60,5,5,255), stop:1 rgba(140,15,15,255));
    border-top: 1px solid rgba(120,10,10,200);
    border-bottom: 2px solid rgba(255,80,80,200);
    color: #ff9090;
    font-weight: bold;
}}

/* ── Progress bar ─────────────────────────────────────── */
QProgressBar {{
    background: rgba(10,4,4,220);
    border: 1px solid {BORDER};
    border-top: 1px solid rgba(60,5,5,200);
    border-radius: 8px;
    text-align: center;
    color: #eeeef5; font-size: 11px;
    min-height: 18px; max-height: 18px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(130,10,10,255),
        stop:0.5 rgba(196,28,28,255),
        stop:0.9 rgba(255,80,80,255),
        stop:1 rgba(255,160,160,200));
    border-radius: 7px;
}}

/* ── Tabs ─────────────────────────────────────────────── */
QTabWidget::pane {{
    background: rgba(10,4,4,240);
    border: 1px solid {BORDER};
    border-radius: 12px; top: -1px;
}}
QTabBar::tab {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(40,10,10,200), stop:1 rgba(15,4,4,220));
    border: 1px solid rgba(120,15,15,80);
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    padding: 8px 22px;
    color: #666;
    margin-right: 3px;
    font-size: 12px;
}}
QTabBar::tab:hover {{ color: #cc6060; border-color: rgba(200,25,25,120); }}
QTabBar::tab:selected {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(255,255,255,30),
        stop:0.1 rgba(200,25,25,210),
        stop:1 rgba(120,10,10,240));
    border: 1px solid {BACT};
    border-bottom: none;
    color: #ffffff;
    font-weight: bold;
}}

/* ── Table ────────────────────────────────────────────── */
QTableWidget {{
    background: rgba(8,3,3,220);
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: rgba(120,10,10,60);
    color: #eeeef5;
    alternate-background-color: rgba(16,5,5,180);
    outline: none;
}}
QTableWidget::item {{ padding: 7px 10px; border: none; }}
QTableWidget::item:selected {{ background: {SEL_BG}; color: #fff; }}
QHeaderView::section {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {HDR_A}, stop:1 {HDR_B});
    color: #fff; padding: 7px 10px;
    border: none; border-right: 1px solid rgba(120,10,10,100);
    font-weight: bold; font-size: 11px;
}}
QHeaderView::section:first {{ border-top-left-radius: 9px; }}
QHeaderView::section:last  {{ border-top-right-radius: 9px; border-right: none; }}
QHeaderView {{ background: transparent; }}

/* ── Scrollbar ────────────────────────────────────────── */
QScrollBar:vertical {{
    background: rgba(8,3,3,120); width: 6px; border-radius: 3px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(180,22,22,160); border-radius: 3px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {BRIGHT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: rgba(8,3,3,120); height: 6px; border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(180,22,22,160); border-radius: 3px; min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: {BRIGHT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Cards & Panels ───────────────────────────────────── */
QScrollArea {{ background: transparent; border: none; }}
QFrame[class="card"] {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(255,255,255,8),
        stop:0.03 rgba(22,6,6,235),
        stop:1 rgba(10,2,2,245));
    border-top: 1px solid rgba(255,60,60,60);
    border-left: 1px solid rgba(200,25,25,50);
    border-right: 1px solid rgba(60,5,5,120);
    border-bottom: 2px solid rgba(10,0,0,200);
    border-radius: 12px;
}}
QFrame[class="header"] {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(14,4,4,250),
        stop:0.5 rgba(24,6,6,245),
        stop:1 rgba(14,4,4,250));
    border-bottom: 1px solid rgba(200,25,25,80);
}}
QFrame[class="sidebar"] {{
    background: rgba(10,3,3,230);
    border-left: 1px solid rgba(200,25,25,60);
}}
QFrame[class="footer"] {{
    background: rgba(10,3,3,230);
    border-top: 1px solid rgba(200,25,25,60);
}}

/* ── Misc ─────────────────────────────────────────────── */
QToolTip {{
    background: rgba(16,4,4,245); color: #eeeef5;
    border: 1px solid {BACT}; border-radius: 8px;
    padding: 6px 10px; font-size: 11px;
}}
QMessageBox {{ background: #0a0303; }}
QMessageBox QLabel {{ color: #eeeef5; }}
QCheckBox {{ color: #7878a0; spacing: 8px; }}
QCheckBox:hover {{ color: #eeeef5; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1px solid {BORDER}; border-radius: 5px;
    background: rgba(6,2,2,220);
}}
QCheckBox::indicator:hover {{ border: 1px solid {BACT}; }}
QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(255,80,80,200), stop:1 rgba(160,15,15,255));
    border: 1px solid {BACT};
}}
"""


def glow(widget, radius: int = 22, alpha: float = 0.5):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(radius)
    fx.setOffset(0, 2)
    fx.setColor(QColor(220, 28, 28, int(alpha * 255)))
    widget.setGraphicsEffect(fx)


def apply(app):
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
