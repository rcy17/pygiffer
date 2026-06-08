from __future__ import annotations

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QFont, QGuiApplication, QScreen

# Default layout tuned for 4K displays.
WINDOW_ASPECT_W = 1650
WINDOW_ASPECT_H = 1140
SCREEN_FILL_RATIO = 0.8

APP_FONT_FAMILY = "Segoe UI"
APP_FONT_POINT_SIZE = 15

THUMB_SIZE = 128
FOLDER_LIST_MAX_HEIGHT = 140

FONT_HINT_PX = 20
FONT_LIST_PX = 22
FONT_MUTED_PX = 18


def default_window_size(screen: QScreen | None = None) -> QSize:
    screen = screen or QGuiApplication.primaryScreen()
    if screen is None:
        return QSize(WINDOW_ASPECT_W, WINDOW_ASPECT_H)

    avail = screen.availableGeometry()
    max_w = int(avail.width() * SCREEN_FILL_RATIO)
    max_h = int(avail.height() * SCREEN_FILL_RATIO)
    aspect = WINDOW_ASPECT_W / WINDOW_ASPECT_H

    width = max_w
    height = int(round(width / aspect))
    if height > max_h:
        height = max_h
        width = int(round(height * aspect))
    return QSize(max(640, width), max(480, height))


def app_font() -> QFont:
    font = QFont(APP_FONT_FAMILY, APP_FONT_POINT_SIZE)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    return font


def global_stylesheet() -> str:
    return f"""
        QGroupBox {{
            font-size: {APP_FONT_POINT_SIZE + 1}px;
            font-weight: 600;
            margin-top: 10px;
            padding-top: 8px;
        }}
        QPushButton {{
            font-size: {APP_FONT_POINT_SIZE}px;
            padding: 6px 14px;
        }}
        QCheckBox {{
            font-size: {APP_FONT_POINT_SIZE}px;
        }}
        QListWidget {{
            font-size: {FONT_LIST_PX}px;
        }}
        QLabel#StatusLabel {{
            color: #71717a;
            font-size: {FONT_MUTED_PX}px;
            padding: 6px;
        }}
        QLabel#MutedLabel {{
            color: #a1a1aa;
            font-size: {FONT_MUTED_PX}px;
        }}
        QLabel#HintLabel {{
            color: #71717a;
            font-size: {FONT_HINT_PX}px;
        }}
    """
