from __future__ import annotations

import ctypes

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .models import CrosshairState, Settings


def select_overlay_screen(screens, primary_screen, configured_name: str):
    """Resolve the configured display, with a safe primary-display fallback."""
    if not screens:
        return None
    if configured_name:
        selected = next((screen for screen in screens if screen.name() == configured_name), None)
        if selected is not None:
            return selected
    return primary_screen or screens[0]


class CrosshairOverlay(QWidget):
    def __init__(self, get_state, settings: Settings) -> None:
        super().__init__(None)
        self._get_state = get_state
        self.settings = settings
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self._screen = None
        application = QGuiApplication.instance()
        if application is not None:
            application.screenAdded.connect(lambda _screen: self.sync_screen())
            application.screenRemoved.connect(lambda _screen: self.sync_screen())
        self.sync_screen()
        self._make_click_through()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)

    def _target_screen(self):
        screens = QGuiApplication.screens()
        return select_overlay_screen(screens, QGuiApplication.primaryScreen(), self.settings.overlay_screen)

    def sync_screen(self) -> None:
        """Resize the click-through window to the selected display.

        A missing saved display is expected after unplugging a monitor, so it
        intentionally falls back to the current primary display.
        """
        screen = self._target_screen()
        if screen is None:
            return
        if screen is not self._screen:
            if self._screen is not None:
                try:
                    self._screen.geometryChanged.disconnect(self._on_screen_geometry_changed)
                except (RuntimeError, TypeError):
                    pass
            self._screen = screen
            screen.geometryChanged.connect(self._on_screen_geometry_changed)
        self.setGeometry(screen.geometry())

    def _on_screen_geometry_changed(self, geometry) -> None:
        self.setGeometry(geometry)

    def _make_click_through(self) -> None:
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x20 | 0x80000)

    @staticmethod
    def _centred_dot_size(size: int, minimum: int = 1) -> int:
        """Keep the filled pixel grid symmetric around the crosshair centre."""
        return max(minimum, round(size) | 1)

    def paintEvent(self, event) -> None:
        state: CrosshairState = self._get_state()
        max_radius = self.settings.moving_size / 2
        min_radius = self.settings.standing_size / 2
        radius = min_radius + (max_radius - min_radius) * state.progress
        if state.crouching:
            # Crouching while still has a small visual spread, but both are
            # deliberately tighter than the normal standing ring.
            crouch_idle_radius = min_radius * 0.65
            crouch_moving_radius = min_radius * 1.15
            radius = crouch_idle_radius + (crouch_moving_radius - crouch_idle_radius) * state.speed_ratio
        if state.marker_active:
            radius = min_radius * (0.65 if state.direction_change_marker else 1.0)
        alpha = round(255 * self.settings.opacity / 100)
        colour = QColor(self.settings.marker_color) if state.marker_active else QColor(self.settings.crosshair_color)
        colour.setAlpha(alpha)
        outline_colour = QColor(self.settings.crosshair_outline_color)
        outline_colour.setAlpha(alpha)
        painter = QPainter(self)
        # Both the outline and dot use this exact logical centre. QPoint-based
        # overloads round independently on even-sized fullscreen surfaces.
        center = QPointF(self.width() / 2, self.height() / 2)
        if state.marker_active:
            # The compressed, rotated cross at the low-movement marker could collapse
            # into an unreadable X. Use a fixed bullseye instead: it is clear at
            # any profile size, shape, line thickness, and rotation.
            marker_radius = max(4, self.settings.crosshair_thickness * 2)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(colour, max(1, self.settings.crosshair_thickness)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(
                center.x() - marker_radius, center.y() - marker_radius,
                marker_radius * 2, marker_radius * 2,
            ))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            dot_size = self._centred_dot_size(self.settings.center_dot_size, minimum=3)
            dot_radius = dot_size / 2
            painter.drawEllipse(QRectF(center.x() - dot_radius, center.y() - dot_radius, dot_size, dot_size))
            return
        if self.settings.crosshair_shape == "cross":
            # Cross arms stay fixed; movement is represented by widening the
            # gap between them. Standing size controls arm length, while
            # Moving size controls the maximum extra spread.
            arm_length = max(round(self.settings.standing_size / 2), self.settings.crosshair_thickness + 2)
            movement_spread = max(0, (self.settings.moving_size - self.settings.standing_size) / 2)
            gap = self.settings.crosshair_gap + movement_spread * state.speed_ratio
            outer = gap + arm_length
            pen = QPen(colour, self.settings.crosshair_thickness)
            pen.setCapStyle(Qt.PenCapStyle.SquareCap)
            painter.save()
            painter.translate(center)
            painter.rotate(self.settings.crosshair_rotation)
            if self.settings.crosshair_rotation % 90:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            lines = ((-outer, 0, -gap, 0), (gap, 0, outer, 0), (0, -outer, 0, -gap), (0, gap, 0, outer))
            if self.settings.crosshair_outline:
                outline_pen = QPen(outline_colour, self.settings.crosshair_thickness + self.settings.crosshair_outline_thickness * 2)
                outline_pen.setCapStyle(Qt.PenCapStyle.SquareCap)
                painter.setPen(outline_pen)
                for line in lines:
                    painter.drawLine(*line)
            painter.setPen(pen)
            for line in lines:
                painter.drawLine(*line)
            painter.restore()
        elif self.settings.crosshair_shape == "dot":
            # The dot is a compact alternative: movement expands the dot
            # itself instead of introducing a ring or a line gap.
            dot_size = max(3, round(self.settings.standing_size + (self.settings.moving_size - self.settings.standing_size) * state.speed_ratio))
            dot_size = self._centred_dot_size(dot_size, minimum=3)
            dot_radius = dot_size / 2
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            if self.settings.crosshair_outline:
                outline_size = dot_size + self.settings.crosshair_outline_thickness * 2
                outline_radius = outline_size / 2
                painter.setBrush(outline_colour)
                painter.drawEllipse(QRectF(center.x() - outline_radius, center.y() - outline_radius, outline_size, outline_size))
            painter.setBrush(colour)
            painter.drawEllipse(QRectF(center.x() - dot_radius, center.y() - dot_radius, dot_size, dot_size))
        else:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.settings.crosshair_outline:
                painter.setPen(QPen(outline_colour, self.settings.crosshair_thickness + self.settings.crosshair_outline_thickness * 2))
                painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2))
            painter.setPen(QPen(colour, self.settings.crosshair_thickness))
            painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2))
        if self.settings.center_dot and self.settings.crosshair_shape != "dot":
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            dot_size = self._centred_dot_size(self.settings.center_dot_size)
            dot_radius = dot_size / 2
            if self.settings.crosshair_outline:
                outline_size = dot_size + self.settings.crosshair_outline_thickness * 2
                outline_radius = outline_size / 2
                painter.setBrush(outline_colour)
                painter.drawEllipse(QRectF(center.x() - outline_radius, center.y() - outline_radius, outline_size, outline_size))
            painter.drawEllipse(QRectF(center.x() - dot_radius, center.y() - dot_radius, dot_size, dot_size))
