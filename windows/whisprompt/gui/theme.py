"""Claude-style QSS themes: warm ivory light mode, soft charcoal dark mode."""

LIGHT = {
    "bg": "#FAF9F5", "surface": "#FFFFFF", "alt": "#F0EEE6",
    "text": "#3D3D3A", "heading": "#1F1E1D", "muted": "#87867F",
    "border": "#E3E0D5", "accent": "#D97757", "accent_hover": "#C4633F",
    "accent_text": "#FFFFFF", "danger": "#B3261E", "select": "#F1E6DF",
}

DARK = {
    "bg": "#262624", "surface": "#30302E", "alt": "#3A3A37",
    "text": "#F0EEE6", "heading": "#FAF9F5", "muted": "#A8A69E",
    "border": "#4A4945", "accent": "#D97757", "accent_hover": "#E08B6D",
    "accent_text": "#FFFFFF", "danger": "#F2B8B5", "select": "#4A3A32",
}

SERIF = '"Georgia", "Times New Roman", "PMingLiU", serif'
SANS = '"Segoe UI", "Microsoft JhengHei UI", sans-serif'


def build_qss(theme: str) -> str:
    c = LIGHT if theme == "light" else DARK
    return f"""
QMainWindow, QDialog {{ background: {c['bg']}; }}
QWidget {{ color: {c['text']}; font-family: {SANS}; font-size: 10pt; }}

QGroupBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    margin-top: 14px;
    padding: 10px 6px 6px 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px; top: 0px;
    padding: 0 6px;
    color: {c['heading']};
    font-family: {SERIF};
    font-size: 11pt;
}}

QPushButton {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 6px 14px;
}}
QPushButton:hover {{ background: {c['alt']}; }}
QPushButton:pressed {{ background: {c['border']}; }}
QPushButton:disabled {{ color: {c['muted']}; background: {c['alt']}; }}

QPushButton#primary {{
    background: {c['accent']};
    border: 1px solid {c['accent']};
    color: {c['accent_text']};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
QPushButton#primary:disabled {{ background: {c['alt']}; border-color: {c['border']}; color: {c['muted']}; }}

QPushButton#chipBtn, QPushButton#chipDanger {{
    font-size: 8.5pt; padding: 1px 8px; border-radius: 6px;
}}
QPushButton#chipDanger {{ color: {c['danger']}; }}

QComboBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 4px 10px;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    selection-background-color: {c['select']};
    selection-color: {c['text']};
}}

QPlainTextEdit {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 8px;
    selection-background-color: {c['accent']};
    selection-color: {c['accent_text']};
    font-size: 10.5pt;
}}

QListWidget {{
    background: {c['bg']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    outline: none;
}}
QListWidget::item {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    margin: 4px 6px;
}}
QListWidget::item:selected {{
    background: {c['select']};
    border: 1px solid {c['accent']};
}}

QTabBar::tab {{
    background: transparent;
    border: none;
    padding: 7px 16px;
    color: {c['muted']};
    font-family: {SERIF};
    font-size: 10.5pt;
}}
QTabBar::tab:selected {{
    color: {c['heading']};
    border-bottom: 2px solid {c['accent']};
}}

QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c['border']};
    border-radius: 4px;
    background: {c['surface']};
}}
QCheckBox::indicator:checked {{
    background: {c['accent']};
    border-color: {c['accent']};
}}

QStatusBar {{ color: {c['muted']}; }}
QLabel#meta {{ color: {c['muted']}; font-size: 8.5pt; }}
QLabel#appTitle {{
    color: {c['heading']};
    font-family: {SERIF};
    font-size: 15pt;
}}
QSplitter::handle {{ background: {c['bg']}; width: 6px; }}
QMessageBox {{ background: {c['bg']}; }}
"""
