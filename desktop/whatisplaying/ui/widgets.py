"""Reusable widgets for the WhatIsPlaying desktop window."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import Palette


class ToggleSwitch(QAbstractButton):
    """A small Material-style switch painted with QPainter."""

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(52, 30)
        self._offset = 0.0
        self._palette = palette
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, get_offset, set_offset)

    def apply_theme(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(52, 30)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt name
        del event
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        track = QRectF(1, 5, self.width() - 2, self.height() - 10)
        radius = track.height() / 2

        if not self.isEnabled():
            track_color = QColor(p.border)
            knob_color = QColor(p.surface_high)
        elif self.isChecked():
            track_color = QColor(p.primary)
            knob_color = QColor(p.on_primary)
        else:
            track_color = QColor(p.switch_off)
            knob_color = QColor(p.text if p.dark else p.surface)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, radius, radius)

        knob_size = track.height() - 4
        start_x = track.left() + 2
        end_x = track.right() - knob_size - 2
        knob_x = start_x + (end_x - start_x) * self._offset
        knob = QRectF(knob_x, track.top() + 2, knob_size, knob_size)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob)

        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(p.primary), 1.5))
            focus = track.adjusted(-2, -2, 2, 2)
            painter.drawRoundedRect(focus, radius + 2, radius + 2)

        painter.end()


class StatusDot(QWidget):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(12, 12)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt name
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(1, 1, 10, 10)
        painter.end()


class PlayerRow(QFrame):
    def __init__(
        self,
        *,
        identity: str,
        bus_name: str,
        status: str,
        checked: bool,
        palette: Palette,
        on_toggle: Callable[[bool], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PlayerRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._on_toggle = on_toggle

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(10)

        self.checkbox = QCheckBox(self)
        self.checkbox.setChecked(checked)
        self.checkbox.setAccessibleName(f"Watch {identity}")
        self.checkbox.toggled.connect(self._on_toggle)
        layout.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        name = QLabel(identity)
        name.setStyleSheet("font-weight: 600; background: transparent;")
        detail = QLabel(bus_name)
        detail.setObjectName("Hint")
        detail.setStyleSheet("background: transparent;")
        text_col.addWidget(name)
        text_col.addWidget(detail)
        layout.addLayout(text_col, 1)

        self.pill = QLabel()
        if status == "Playing":
            self.pill.setObjectName("PillOk")
            self.pill.setText("Playing")
        elif status == "Paused":
            self.pill.setObjectName("PillWarn")
            self.pill.setText("Paused")
        else:
            self.pill.setObjectName("PillMuted")
            self.pill.setText(status or "Idle")
        self.pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt name
        if event.button() == Qt.MouseButton.LeftButton:
            self.checkbox.toggle()
        super().mouseReleaseEvent(event)
