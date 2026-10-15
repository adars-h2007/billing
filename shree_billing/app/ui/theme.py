"""Fixed light theme so the app looks the same whatever the OS theme is
(Windows dark mode would otherwise turn labels white on our light background)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

BG = QColor("#fbf7f5")
BASE = QColor("#ffffff")
TEXT = QColor("#231a1a")
MUTED = QColor("#8a7c79")
RED = QColor("#8b1a1a")
BUTTON = QColor("#f1ebe8")


def apply_light_theme(app: QApplication) -> None:
    try:  # Qt 6.8+: stop following the OS dark/light setting
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except Exception:  # noqa: BLE001 - older Qt, the palette below still applies
        pass
    app.setStyle("Fusion")  # native Windows style ignores some palette roles
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: BG,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: BASE,
        QPalette.ColorRole.AlternateBase: BG,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: BUTTON,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.ToolTipBase: BASE,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Highlight: RED,
        QPalette.ColorRole.HighlightedText: QColor("#ffffff"),
        QPalette.ColorRole.Link: RED,
    }
    for role, color in roles.items():
        p.setColor(role, color)
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, MUTED)
    app.setPalette(p)
