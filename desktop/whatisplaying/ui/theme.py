"""Material-inspired light/dark styling for the Qt desktop UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtCore import Qt, QUrl

ASSETS = Path(__file__).resolve().parent.parent / "assets"


@dataclass(frozen=True)
class Palette:
    dark: bool
    background: str
    surface: str
    surface_high: str
    primary: str
    primary_hover: str
    on_primary: str
    primary_container: str
    on_primary_container: str
    text: str
    muted: str
    border: str
    field: str
    error: str
    ok: str
    ok_bg: str
    warn: str
    warn_bg: str
    switch_off: str
    hover: str
    disabled: str


DARK = Palette(
    dark=True,
    background="#141218",
    surface="#211F26",
    surface_high="#2B2930",
    primary="#D0BCFF",
    primary_hover="#EADDFF",
    on_primary="#21005D",
    primary_container="#4F378B",
    on_primary_container="#EADDFF",
    text="#E6E1E5",
    muted="#CAC4D0",
    border="#49454F",
    field="#2B2930",
    error="#F2B8B5",
    ok="#A6D8B0",
    ok_bg="#203A28",
    warn="#F5D48A",
    warn_bg="#3D2F12",
    switch_off="#49454F",
    hover="#302D37",
    disabled="#7A757F",
)

LIGHT = Palette(
    dark=False,
    background="#F7F2FA",
    surface="#FFFFFF",
    surface_high="#F3EDF7",
    primary="#6650A4",
    primary_hover="#57428F",
    on_primary="#FFFFFF",
    primary_container="#EADDFF",
    on_primary_container="#21005D",
    text="#1C1B1F",
    muted="#625B71",
    border="#DED7E7",
    field="#F3EDF7",
    error="#B3261E",
    ok="#1B5E20",
    ok_bg="#D7F0DC",
    warn="#7A5900",
    warn_bg="#FFE9B0",
    switch_off="#CAC4D0",
    hover="#F0EAF5",
    disabled="#9C96A4",
)


def is_dark(app: QGuiApplication) -> bool:
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except AttributeError:
        pass
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def current_palette(app: QGuiApplication) -> Palette:
    return DARK if is_dark(app) else LIGHT


def stylesheet(p: Palette) -> str:
    check = QUrl.fromLocalFile(
        str(ASSETS / ("check-dark.svg" if p.dark else "check-light.svg"))
    ).toString()
    return f"""
    QWidget {{
        color: {p.text};
        font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif;
        font-size: 13px;
    }}
    QWidget#Root {{
        background: {p.background};
    }}
    QScrollArea#Scroll {{
        border: none;
        background: transparent;
    }}
    QScrollArea#Scroll > QWidget > QWidget {{
        background: transparent;
    }}
    QFrame#Card {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 18px;
    }}
    QFrame#IntroCard {{
        background: {p.primary_container};
        border: 1px solid {p.primary_container};
        border-radius: 20px;
    }}
    QFrame#PlayerRow {{
        background: {p.field};
        border: 1px solid transparent;
        border-radius: 12px;
    }}
    QFrame#PlayerRow:hover {{
        border: 1px solid {p.border};
    }}
    QFrame#Divider {{
        background: {p.border};
        border: none;
        min-height: 1px;
        max-height: 1px;
    }}
    QLabel {{
        background: transparent;
    }}
    QLabel#AppTitle {{
        font-size: 24px;
        font-weight: 800;
    }}
    QLabel#IntroTitle {{
        color: {p.on_primary_container};
        font-size: 22px;
        font-weight: 800;
    }}
    QLabel#IntroBody {{
        color: {p.on_primary_container};
        font-size: 13px;
    }}
    QLabel#CardTitle {{
        font-size: 16px;
        font-weight: 700;
    }}
    QLabel#Muted {{
        color: {p.muted};
    }}
    QLabel#Hint {{
        color: {p.muted};
        font-size: 12px;
    }}
    QLabel#Error {{
        color: {p.error};
        font-size: 12px;
    }}
    QLabel#TrackTitle {{
        font-size: 21px;
        font-weight: 800;
    }}
    QLabel#TrackArtist {{
        color: {p.muted};
        font-size: 14px;
    }}
    QLabel#TrackSource {{
        color: {p.muted};
        font-size: 12px;
    }}
    QLabel#PillOk {{
        background: {p.ok_bg};
        color: {p.ok};
        border-radius: 9px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#PillWarn {{
        background: {p.warn_bg};
        color: {p.warn};
        border-radius: 9px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#PillError {{
        background: transparent;
        color: {p.error};
        border: 1px solid {p.error};
        border-radius: 9px;
        padding: 1px 7px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#PillMuted {{
        background: {p.field};
        color: {p.muted};
        border-radius: 9px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#Badge {{
        background: {p.surface};
        color: {p.primary};
        border-radius: 9px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: 700;
    }}
    QLabel#Note {{
        color: {p.primary};
        font-size: 29px;
        font-weight: 700;
        background: transparent;
    }}
    QPushButton {{
        background: transparent;
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 7px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {p.hover};
    }}
    QPushButton:pressed {{
        background: {p.field};
    }}
    QPushButton#Primary {{
        background: {p.primary};
        color: {p.on_primary};
        border: 1px solid {p.primary};
    }}
    QPushButton#Primary:hover {{
        background: {p.primary_hover};
        border-color: {p.primary_hover};
    }}
    QPushButton#Flat {{
        border: none;
        color: {p.primary};
        padding: 5px 8px;
    }}
    QPushButton#Flat:hover {{
        background: {p.hover};
    }}
    QPushButton:disabled {{
        color: {p.disabled};
        border-color: {p.border};
        background: transparent;
    }}
    QToolButton {{
        background: transparent;
        border: none;
        color: {p.primary};
        padding: 4px 8px;
        font-weight: 600;
    }}
    QToolButton:hover {{
        background: {p.hover};
        border-radius: 8px;
    }}
    QLineEdit {{
        background: {p.field};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: {p.primary};
        selection-color: {p.on_primary};
    }}
    QLineEdit:focus {{
        border: 1px solid {p.primary};
    }}
    QTextEdit#Log, QPlainTextEdit#Log {{
        background: {p.field};
        color: {p.muted};
        border: 1px solid {p.border};
        border-radius: 12px;
        padding: 7px;
        font-family: "JetBrains Mono", "Noto Sans Mono", "DejaVu Sans Mono", monospace;
        font-size: 11px;
        selection-background-color: {p.primary};
    }}
    QCheckBox {{
        spacing: 10px;
    }}
    QCheckBox::indicator {{
        width: 19px;
        height: 19px;
        border: 1.5px solid {p.muted};
        border-radius: 5px;
        background: transparent;
    }}
    QCheckBox::indicator:hover {{
        border-color: {p.primary};
    }}
    QCheckBox::indicator:checked {{
        background: {p.primary};
        border-color: {p.primary};
        image: url("{check}");
    }}
    QCheckBox:disabled {{
        color: {p.disabled};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border};
        min-height: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p.muted};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QMenu {{
        background: {p.surface};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 5px;
    }}
    QMenu::item {{
        padding: 6px 24px 6px 10px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background: {p.hover};
    }}
    QMenu::indicator {{
        width: 14px;
        height: 14px;
    }}
    QToolTip {{
        background: {p.surface_high};
        color: {p.text};
        border: 1px solid {p.border};
        padding: 5px;
    }}
    """
