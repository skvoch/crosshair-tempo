from __future__ import annotations

import signal
import sys
import random
import ctypes
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from crosshair_tempo.input_tracker import InputTracker, cs2_is_foreground
    from crosshair_tempo.icons import icon as app_icon
    from crosshair_tempo.models import CrosshairState, MovementState, Settings
    from crosshair_tempo.overlay import CrosshairOverlay
    from crosshair_tempo.crosshair_profiles import CrosshairProfile, CrosshairProfileStore, apply_profile, export_share_code, import_share_code, update_profile_from_settings
    from crosshair_tempo.settings_store import load_settings, save_settings
    from crosshair_tempo.timing import MovementFeedbackEngine
    from crosshair_tempo.windows_startup import set_start_with_windows
else:
    from .input_tracker import InputTracker, cs2_is_foreground
    from .icons import icon as app_icon
    from .models import CrosshairState, MovementState, Settings
    from .overlay import CrosshairOverlay
    from .crosshair_profiles import CrosshairProfile, CrosshairProfileStore, apply_profile, export_share_code, import_share_code, update_profile_from_settings
    from .settings_store import load_settings, save_settings
    from .timing import MovementFeedbackEngine
    from .windows_startup import set_start_with_windows

from PySide6.QtCore import QObject, Qt, QPointF, QProcess, QRect, QRectF, QSize, QTimer, Signal, Slot

from PySide6.QtGui import QAction, QColor, QDesktopServices, QGuiApplication, QIcon, QPainter, QPen
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QPushButton, QScrollArea, QStackedWidget, QStyle, QSystemTrayIcon, QToolButton, QVBoxLayout, QWidget,
)
from qfluentwidgets import ComboBox, FluentWindow, NavigationItemPosition, PushButton, Slider, SwitchButton, setTheme, Theme


class Panel(QFrame):
    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        self.setObjectName("panel")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(22, 20, 22, 20)
        self.layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        self.layout.addWidget(heading)
        if description:
            body = QLabel(description)
            body.setObjectName("panelDescription")
            body.setWordWrap(True)
            self.layout.addWidget(body)


class CrosshairPreview(QWidget):
    def __init__(self, settings: Settings, get_state) -> None:
        super().__init__()
        self.settings = settings
        self.get_state = get_state
        self._context_state = CrosshairState(MovementState.STANDING)
        self.setMinimumHeight(210)
        self.setObjectName("preview")
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.update)
        self.refresh_timer.start(16)

    def show_context(self, context: str) -> None:
        states = {
            "standing": CrosshairState(MovementState.STANDING),
            "moving": CrosshairState(MovementState.MOVING_RIGHT, progress=1.0, speed_ratio=1.0),
            "marker": CrosshairState(MovementState.STANDING, marker_active=True, direction_change_marker=True),
        }
        self._context_state = states[context]
        self.update()

    def displayed_state(self) -> CrosshairState:
        return self._context_state

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        center = QPointF(self.width() / 2, self.height() / 2)
        state = self.displayed_state()
        max_radius = self.settings.moving_size / 2
        min_radius = self.settings.standing_size / 2
        radius = min_radius + (max_radius - min_radius) * state.progress
        if state.crouching:
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
        if state.marker_active:
            marker_radius = max(4, self.settings.crosshair_thickness * 2)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(colour, max(1, self.settings.crosshair_thickness)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(center.x() - marker_radius, center.y() - marker_radius, marker_radius * 2, marker_radius * 2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            dot_size = self._centred_dot_size(self.settings.center_dot_size, minimum=3)
            dot_radius = dot_size / 2
            painter.drawEllipse(QRectF(center.x() - dot_radius, center.y() - dot_radius, dot_size, dot_size))
            return
        if self.settings.crosshair_shape == "cross":
            # Keep the preview consistent with the overlay: fixed arms with a
            # mid-movement gap so both size sliders remain visible here.
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
            dot_size = max(3, round(self.settings.standing_size + (self.settings.moving_size - self.settings.standing_size) * state.speed_ratio))
            dot_size = self._centred_dot_size(dot_size)
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

    @staticmethod
    def _centred_dot_size(size: int, minimum: int = 1) -> int:
        """Odd pixel widths have one unambiguous centre pixel."""
        return max(minimum, round(size) | 1)


class ProfileNameButton(QPushButton):
    doubleClicked = Signal()

    def mouseDoubleClickEvent(self, event) -> None:
        self.doubleClicked.emit()
        event.accept()


class ScrollSafeSlider(Slider):
    """Let the settings panel own mouse-wheel scrolling instead of changing values."""

    def wheelEvent(self, event) -> None:
        event.ignore()


class RotationTickLabels(QWidget):
    """Draw labels on the exact centres used by QFluent's slider handle."""

    def __init__(self, slider: Slider, angles: tuple[int, ...]) -> None:
        super().__init__()
        self.slider = slider
        self.angles = angles
        self.setFixedHeight(20)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setPen(QColor("#9aa3ad"))
        count = max(1, len(self.angles) - 1)
        radius = self.slider.handle.width() / 2
        usable_width = max(0, self.width() - radius * 2)
        for index, angle in enumerate(self.angles):
            x = radius + usable_width * index / count
            painter.drawText(QRectF(x - 28, 0, 56, self.height()), Qt.AlignmentFlag.AlignCenter, f"{angle}°")


class ShapeChoiceButton(QPushButton):
    """A visual shape picker rather than a row of ordinary text buttons."""

    def __init__(self, title: str, shape: str) -> None:
        super().__init__(title)
        self.shape = shape
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(70)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = self.isChecked()
        background = QColor("#26373a" if selected else "#24282c")
        border = QColor("#28d8e8" if selected else "#3a4046")
        if self.underMouse() and not selected:
            background = QColor("#2b3035")
        painter.setPen(QPen(border, 2 if selected else 1))
        painter.setBrush(background)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 9, 9)

        colour = QColor("#40dfed" if selected else "#b9c3cb")
        pen = QPen(colour, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(colour)
        center = QPointF(self.width() / 2, 26)
        if self.shape == "ring":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(center.x() - 10, center.y() - 10, 20, 20))
        elif self.shape == "cross":
            for x1, y1, x2, y2 in ((-12, 0, -4, 0), (4, 0, 12, 0), (0, -12, 0, -4), (0, 4, 0, 12)):
                painter.drawLine(center + QPointF(x1, y1), center + QPointF(x2, y2))
        else:
            painter.drawEllipse(QRectF(center.x() - 5, center.y() - 5, 10, 10))

        painter.setPen(QColor("#f2f4f6" if selected else "#d7dce0"))
        painter.drawText(QRect(0, 48, self.width(), 18), Qt.AlignmentFlag.AlignCenter, self.text())


class SettingsWindow(FluentWindow):
    def __init__(self, settings: Settings, get_crosshair_state, toggle_overlay, save, sync_overlay, quit_app, restart_app, profile_store: CrosshairProfileStore, set_autostart=None, set_overlay_screen=None) -> None:
        super().__init__()
        self.settings = settings
        self.get_crosshair_state = get_crosshair_state
        self.toggle_overlay = toggle_overlay
        self.save = save
        self.sync_overlay = sync_overlay
        self.quit_app = quit_app
        self.restart_app = restart_app
        self.set_autostart = set_autostart or (lambda _enabled: None)
        self.set_overlay_screen = set_overlay_screen or (lambda _screen_name: None)
        self.profile_store = profile_store
        self.profiles = self.profile_store.load_all(settings)
        self.active_profile = next((profile for profile in self.profiles if profile.id == settings.active_crosshair_profile), self.profiles[0])
        apply_profile(self.settings, self.active_profile)
        self.save()
        self.preview: CrosshairPreview | None = None
        self.preview_reset_timer = QTimer(self)
        self.preview_reset_timer.setSingleShot(True)
        self.preview_reset_timer.setInterval(240)
        self.preview_reset_timer.timeout.connect(self._reset_preview_context)
        self.crosshair_controls: dict[str, tuple[Slider, QLabel, str, QLabel]] = {}
        self.cross_only_widgets: list[QWidget] = []
        self.profile_list: QVBoxLayout | None = None
        self.movement_marker: QLabel | None = None
        self.pages: dict[str, QWidget] = {}
        self.side_buttons: list[tuple[str, QToolButton]] = []
        self.setWindowTitle("Crosshair Tempo")
        self.setWindowIcon(app_icon("crosshair-tempo"))
        self.resize(1280, 860)
        # The crosshair editor is a three-column workspace. Below this width
        # Qt clips the last slider captions after a shape changes visibility.
        self.setMinimumSize(1050, 720)
        # The interface is intentionally a desktop control panel, not a
        # fullscreen workspace. Disable Windows maximise to preserve its layout.
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        self.titleBar.maxBtn.hide()
        self._apply_style()
        self._add_pages()
        self.navigationInterface.setExpandWidth(48)
        self.stackedWidget.setAnimationEnabled(False)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange and self.isMaximized():
            QTimer.singleShot(0, self.showNormal)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "github_button"):
            self.github_button.move(4, max(54, self.navigationInterface.height() - 48))

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI'; }
            QWidget#page { background: #151719; }
            QWidget#header { background: #1d2023; border-bottom: 1px solid #2b3035; }
            QLabel#title { font-size: 28px; font-weight: 700; color: #f4f6f8; }
            QLabel#subtitle, QLabel#panelDescription { font-size: 13px; color: #9aa3ad; }
            QFrame#panel { background: #202326; border: 1px solid #2d3237; border-radius: 10px; }
            QFrame#warning { background: #382d1d; border: 1px solid #b67d28; border-radius: 9px; }
            QLabel#panelTitle { font-size: 16px; font-weight: 650; color: #f1f4f7; }
            QLabel#warningTitle { font-size: 14px; font-weight: 700; color: #ffd070; }
            QLabel#warningText { font-size: 13px; color: #f0c889; }
            QLabel#metric { font-size: 24px; font-weight: 700; color: #ffd14a; }
            QLabel#metricCaption { color: #9aa3ad; font-size: 12px; }
            QWidget#preview { background: #111315; border: 1px solid #353a3f; border-radius: 10px; }
            QScrollArea#profileList, QWidget#profileListContent { background: #202326; border: 0; }
            QToolButton#leftNav { border: 0; border-radius: 9px; padding: 7px; }
            QToolButton#leftNav:hover { background: #292d31; }
            QToolButton#leftNav:checked { background: #2c3538; border-left: 3px solid #28d8e8; }
            QToolButton#githubLink { border: 0; border-radius: 9px; padding: 7px; }
            QToolButton#githubLink:hover { background: #292d31; }
            QPushButton#settingsSection { border: 0; border-radius: 7px; padding: 10px 12px; text-align: left; background: transparent; color: #cbd3da; font-size: 14px; }
            QPushButton#settingsSection:hover { background: #2a2f34; }
            QPushButton#settingsSection:checked { background: #3a4248; color: #f4f6f8; font-weight: 650; }
            QWidget#profileCard { border: 2px solid transparent; border-radius: 7px; }
            QWidget#profileCard[selected="true"] { border: 2px solid #111315; }
            QPushButton#profile { text-align: left; padding: 8px 10px; border: 0; border-radius: 5px; background: transparent; color: #111315; font-weight: 650; }
            QToolButton#profileDots { border: 0; border-radius: 5px; background: transparent; color: #111315; font-size: 17px; font-weight: 700; }
            QToolButton#profileDots:hover { background: rgba(17, 19, 21, 40); }
            QLineEdit#profileRename { border: 0; border-bottom: 1px solid rgba(17, 19, 21, 90); border-radius: 0; padding: 7px 9px; background: rgba(255, 255, 255, 55); color: #111315; font-weight: 650; }
            QLineEdit#profileRename:focus { border-bottom: 1px solid rgba(17, 19, 21, 145); }
            QLineEdit#shareCode { padding: 8px 10px; border: 1px solid #3b4248; border-radius: 6px; background: #171a1d; color: #eef2f5; }
            QLabel#shareStatus { color: #9aa3ad; font-size: 12px; }
            QPushButton#profileAction { border: 0; border-radius: 6px; background: #2b3034; color: #dfe5e9; padding: 7px 10px; }
            QPushButton#profileAction:hover { background: #3a4147; }
        """)

    def _page(self, key: str, title: str, subtitle: str) -> tuple[QScrollArea, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("page")
        shell = QVBoxLayout(page)
        shell.setContentsMargins(0, 0, 0, 0)
        header = QWidget()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(34, 24, 34, 22)
        name = QLabel(title)
        name.setObjectName("title")
        header_layout.addWidget(name)
        text = QLabel(subtitle)
        text.setObjectName("subtitle")
        header_layout.addWidget(text)
        shell.addWidget(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        content = QWidget()
        content.setObjectName("page")
        # Avoid over-stretching cards and sliders when the app is maximised.
        content.setMaximumWidth(1600)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 26, 34, 34)
        content_layout.setSpacing(16)
        content_layout.addStretch()
        scroll.setWidget(content)
        shell.addWidget(scroll, 1)
        return page, content_layout

    def _add_pages(self) -> None:
        dashboard, layout = self._page("dashboard", "Crosshair Tempo", "Movement-reactive visualisation for counter-strafe practice · external crosshair")
        self._build_dashboard(layout)
        crosshair, layout = self._page("crosshair", "Crosshair", "Shape, colour and size update in the overlay immediately.")
        self._build_crosshair(layout)
        settings, layout = self._page("settings", "Settings", "Control overlay behaviour and movement model settings.")
        self._build_settings(layout)
        for page, key, glyph, label in [
            (dashboard, "dashboard", "home", "Dashboard"),
            (crosshair, "crosshair", "crosshair", "Crosshair"),
            (settings, "settings", "settings", "Settings"),
        ]:
            page.setObjectName(key)
            self.pages[key] = page
            self.addSubInterface(page, app_icon(glyph), label, position=NavigationItemPosition.TOP)
            self.navigationInterface.removeWidget(key)
        self._build_left_icon_stack()

    def _build_left_icon_stack(self) -> None:
        self.navigationInterface.setMenuButtonVisible(False)
        stack = QWidget(self.navigationInterface)
        stack.setGeometry(4, 54, 40, 144)
        layout = QVBoxLayout(stack)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        for key, glyph, label in [
            ("dashboard", "home", "Dashboard"),
            ("crosshair", "crosshair", "Crosshair"),
            ("settings", "settings", "Settings"),
        ]:
            button = QToolButton(stack)
            button.setObjectName("leftNav")
            button.setCheckable(True)
            button.setChecked(key == "dashboard")
            button.setToolTip(label)
            button.setIcon(app_icon(glyph))
            button.setIconSize(QSize(22, 22))
            button.setFixedSize(40, 40)
            button.clicked.connect(lambda _checked=False, page_key=key: self._activate_page(page_key))
            self.side_buttons.append((key, button))
            layout.addWidget(button)
        self.github_button = QToolButton(self.navigationInterface)
        self.github_button.setObjectName("githubLink")
        self.github_button.setToolTip("Open Crosshair Tempo on GitHub")
        self.github_button.setIcon(app_icon("github"))
        self.github_button.setIconSize(QSize(22, 22))
        self.github_button.setFixedSize(40, 40)
        self.github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/skvoch/crosshair-tempo")))
        self.github_button.move(4, max(54, self.navigationInterface.height() - 48))
        self.github_button.show()

    def _activate_page(self, key: str) -> None:
        self.stackedWidget.setCurrentWidget(self.pages[key])
        for page_key, button in self.side_buttons:
            button.setChecked(page_key == key)

    def _build_dashboard(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        enabled = Panel("Overlay", "Show the live crosshair over CS2.")
        self.enabled = SwitchButton("Overlay enabled")
        self.enabled.setChecked(self.settings.overlay_enabled)
        self.enabled.checkedChanged.connect(self.toggle_overlay)
        enabled.layout.addWidget(self.enabled)
        focus = Panel("CS2-only mode", "When on, the movement visualisation works only while Counter-Strike 2 is focused.")
        self.focus = SwitchButton("Show only when CS2 is focused")
        self.focus.setChecked(self.settings.only_cs2_focused)
        self.focus.checkedChanged.connect(self._set_focus_scope)
        focus.layout.addWidget(self.focus)
        target = Panel("Movement marker", "Appears when the movement model reaches its compact low-movement state.")
        metric = QLabel("●")
        metric.setObjectName("metric")
        self.movement_marker = metric
        self._refresh_movement_marker()
        target.layout.addWidget(metric)
        caption = QLabel("A compact bullseye uses your chosen marker colour.")
        caption.setObjectName("metricCaption")
        target.layout.addWidget(caption)
        row.addWidget(enabled)
        row.addWidget(focus)
        row.addWidget(target)
        layout.insertLayout(layout.count() - 1, row)
        guide = Panel("Counter-strafe practice", "Hold A/D to expand the crosshair. Release to slow by friction. Changing direction contracts the crosshair more quickly, giving you visual feedback while practising counter-strafes.")
        layout.insertWidget(layout.count() - 1, guide)

    def _build_movement(self, layout: QVBoxLayout) -> None:
        card = Panel("Rifle velocity model", "These values are estimates until a later calibration map measures your in-game behaviour.")
        for label, value, handler, low, high, suffix in [
            ("Rifle max speed", self.settings.max_speed, self._set_max_speed, 150, 280, " u/s"),
            ("Low-movement threshold", self.settings.low_movement_speed, self._set_low_movement_speed, 30, 110, " u/s"),
            ("Ground acceleration", self.settings.ground_acceleration, self._set_acceleration, 600, 2200, " u/s²"),
            ("Ground friction", self.settings.ground_friction, self._set_friction, 300, 1600, " u/s²"),
            ("Crouch speed", self.settings.crouch_speed_percent, self._set_crouch_speed, 20, 60, " %"),
        ]:
            card.layout.addWidget(self._setting_slider(label, value, handler, low, high, suffix))
        layout.insertWidget(layout.count() - 1, card)
        warning = QFrame()
        warning.setObjectName("warning")
        warning_layout = QVBoxLayout(warning)
        warning_layout.setContentsMargins(18, 15, 18, 15)
        warning_layout.setSpacing(5)
        warning_title = QLabel("Recommended: leave these values unchanged")
        warning_title.setObjectName("warningTitle")
        warning_text = QLabel("They are baseline rifle estimates. Changing them without calibration can make the movement visualisation less reliable.")
        warning_text.setObjectName("warningText")
        warning_text.setWordWrap(True)
        warning_layout.addWidget(warning_title)
        warning_layout.addWidget(warning_text)
        layout.insertWidget(layout.count() - 1, warning)

    def _build_settings(self, layout: QVBoxLayout) -> None:
        """A settings workspace with focused sections instead of one long page."""
        workspace = QHBoxLayout()
        workspace.setSpacing(20)
        sidebar = Panel("Settings", "Choose what you want to configure.")
        sidebar.setFixedWidth(250)
        self.settings_section_buttons: list[QPushButton] = []
        self.settings_sections = QStackedWidget()

        for title, index in [
            ("General", 0),
            ("Movement model", 1),
        ]:
            button = QPushButton(title)
            button.setObjectName("settingsSection")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.clicked.connect(lambda _checked=False, section=index: self._activate_settings_section(section))
            sidebar.layout.addWidget(button)
            self.settings_section_buttons.append(button)
        sidebar.layout.addStretch(1)

        general = QWidget()
        general_layout = QVBoxLayout(general)
        general_layout.setContentsMargins(0, 0, 0, 0)
        general_layout.setSpacing(16)
        general_layout.addStretch(1)
        self._build_overlay(general_layout)

        movement = QWidget()
        movement_layout = QVBoxLayout(movement)
        movement_layout.setContentsMargins(0, 0, 0, 0)
        movement_layout.setSpacing(16)
        movement_layout.addStretch(1)
        self._build_movement(movement_layout)

        self.settings_sections.addWidget(general)
        self.settings_sections.addWidget(movement)
        workspace.addWidget(sidebar)
        workspace.addWidget(self.settings_sections, 1)
        layout.insertLayout(layout.count() - 1, workspace)

    def _activate_settings_section(self, index: int) -> None:
        self.settings_sections.setCurrentIndex(index)
        for button_index, button in enumerate(self.settings_section_buttons):
            button.setChecked(button_index == index)

    def _build_crosshair(self, layout: QVBoxLayout) -> None:
        workspace = QHBoxLayout()
        profiles = Panel("Crosshair profiles", "Each profile stores its own appearance.")
        profiles.setMaximumWidth(270)
        profile_scroll = QScrollArea()
        profile_scroll.setObjectName("profileList")
        profile_scroll.setWidgetResizable(True)
        profile_scroll.setFrameShape(QFrame.Shape.NoFrame)
        profile_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        profile_content = QWidget()
        profile_content.setObjectName("profileListContent")
        self.profile_list = QVBoxLayout()
        self.profile_list.setSpacing(7)
        self.profile_list.setContentsMargins(0, 0, 0, 0)
        self.profile_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        profile_content.setLayout(self.profile_list)
        profile_scroll.setWidget(profile_content)
        profiles.layout.addWidget(profile_scroll, 1)
        self.share_import = QWidget()
        share_layout = QVBoxLayout(self.share_import)
        share_layout.setContentsMargins(0, 6, 0, 0)
        share_layout.setSpacing(6)
        self.share_input = QLineEdit()
        self.share_input.setObjectName("shareCode")
        self.share_input.setPlaceholderText("Paste SV1 share code")
        self.share_input.returnPressed.connect(self._import_share_code)
        share_layout.addWidget(self.share_input)
        self.share_status = QLabel("Paste a code and press Enter to import")
        self.share_status.setObjectName("shareStatus")
        share_layout.addWidget(self.share_status)
        profiles.layout.addWidget(self.share_import)
        self._refresh_profile_list()
        workspace.addWidget(profiles, 1)

        editor = QVBoxLayout()
        top = QHBoxLayout()
        appearance = Panel("Appearance", "Choose the visual language of the live crosshair.")
        shapes = QGridLayout()
        shapes.setHorizontalSpacing(8)
        shapes.setVerticalSpacing(8)
        self.shape_buttons: dict[str, ShapeChoiceButton] = {}
        for index, (title, shape) in enumerate((
            ("Ring", "ring"),
            ("Cross", "cross"),
            ("Dot", "dot"),
        )):
            shapes.addWidget(self._shape_button(title, shape), 0, index)
        appearance.layout.addLayout(shapes)
        self.colour_button = PushButton("Choose colour")
        self.colour_button.clicked.connect(self._choose_colour)
        appearance.layout.addWidget(self.colour_button)
        self._refresh_colour_button()
        self.marker_colour_button = PushButton("Choose marker colour")
        self.marker_colour_button.clicked.connect(self._choose_marker_colour)
        appearance.layout.addWidget(self.marker_colour_button)
        self._refresh_marker_colour_button()
        self.outline_colour_button = PushButton("Choose outline colour")
        self.outline_colour_button.clicked.connect(self._choose_outline_colour)
        appearance.layout.addWidget(self.outline_colour_button)
        self._refresh_outline_colour_button()
        preview_card = Panel("Preview", "Updates automatically for the control you are editing.")
        self.preview = CrosshairPreview(self.settings, self.get_crosshair_state)
        preview_card.layout.addWidget(self.preview)
        top.addWidget(appearance, 1)
        top.addWidget(preview_card, 2)
        editor.addLayout(top)
        sizing = Panel("Size & visibility")
        sizing.layout.addWidget(self._setting_slider("Standing size", self.settings.standing_size, self._set_standing_size, 1 if self.settings.crosshair_shape == "dot" else 6, 32, " px", "standing_size", "standing"))
        sizing.layout.addWidget(self._setting_slider("Moving size", self.settings.moving_size, self._set_moving_size, 3 if self.settings.crosshair_shape == "dot" else 24, 120, " px", "moving_size", "moving"))
        sizing.layout.addWidget(self._setting_slider("Opacity", self.settings.opacity, self._set_opacity, 20, 100, " %", "opacity"))
        self.outline_switch = SwitchButton("Outline")
        self.outline_switch.setChecked(self.settings.crosshair_outline)
        self.outline_switch.checkedChanged.connect(self._set_crosshair_outline)
        sizing.layout.addWidget(self.outline_switch)
        sizing.layout.addWidget(self._setting_slider("Outline thickness", self.settings.crosshair_outline_thickness, self._set_crosshair_outline_thickness, 1, 4, " px", "crosshair_outline_thickness"))
        line_thickness = self._setting_slider("Line thickness", self.settings.crosshair_thickness, self._set_crosshair_thickness, 1, 8, " px", "crosshair_thickness")
        line_gap = self._setting_slider("Line gap", self.settings.crosshair_gap, self._set_crosshair_gap, 0, 30, " px", "crosshair_gap", "moving")
        rotation = self._rotation_slider()
        self.cross_only_widgets = [line_thickness, line_gap, rotation]
        for widget in self.cross_only_widgets:
            sizing.layout.addWidget(widget)
        self.center_dot_switch = SwitchButton("Centre dot")
        self.center_dot_switch.setChecked(self.settings.center_dot)
        self.center_dot_switch.checkedChanged.connect(self._set_center_dot)
        sizing.layout.addWidget(self.center_dot_switch)
        centre_dot_size = self._setting_slider("Dot size", self.settings.center_dot_size, self._set_center_dot_size, 1, 10, " px", "center_dot_size")
        self.centre_dot_widgets = [self.center_dot_switch, centre_dot_size]
        sizing.layout.addWidget(centre_dot_size)
        self._refresh_crosshair_controls()
        sizing_scroll = QScrollArea()
        sizing_scroll.setObjectName("crosshairSettingsScroll")
        sizing_scroll.setWidgetResizable(True)
        sizing_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sizing_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sizing_scroll.setMinimumHeight(260)
        sizing_scroll.setMaximumHeight(300)
        sizing_scroll.setWidget(sizing)
        editor.addWidget(sizing_scroll)
        workspace.addLayout(editor, 3)
        layout.insertLayout(layout.count() - 1, workspace)

    def _build_overlay(self, layout: QVBoxLayout) -> None:
        debug = Panel("Debug", "Show the local movement-model estimate beside the crosshair.")
        self.speed_debug = SwitchButton("Show estimated speed")
        self.speed_debug.setChecked(self.settings.show_estimated_speed)
        self.speed_debug.checkedChanged.connect(self._set_speed_debug)
        debug.layout.addWidget(self.speed_debug)
        layout.insertWidget(layout.count() - 1, debug)

        display = Panel("Display", "Choose which monitor shows the live crosshair.")
        self.monitor_picker = ComboBox()
        primary_screen = QGuiApplication.primaryScreen()
        selected_name = self.settings.overlay_screen or (primary_screen.name() if primary_screen else "")
        for index, screen in enumerate(QGuiApplication.screens(), start=1):
            geometry = screen.geometry()
            suffix = " · Primary" if screen is primary_screen else ""
            name = screen.name() or f"Display {index}"
            self.monitor_picker.addItem(f"{name} · {geometry.width()}×{geometry.height()}{suffix}", screen.name())
            if screen.name() == selected_name:
                self.monitor_picker.setCurrentIndex(self.monitor_picker.count() - 1)
        self.monitor_picker.currentIndexChanged.connect(self._set_overlay_screen)
        display.layout.addWidget(self.monitor_picker)
        layout.insertWidget(layout.count() - 1, display)

        startup = Panel("Startup", "Optionally open Crosshair Tempo when you sign in to Windows.")
        self.autostart = SwitchButton("Start with Windows")
        self.autostart.setChecked(self.settings.start_with_windows)
        self.autostart.checkedChanged.connect(self.set_autostart)
        startup.layout.addWidget(self.autostart)
        layout.insertWidget(layout.count() - 1, startup)
        hotkey = Panel("Quick controls", "F8 toggles the overlay from any app. Closing this window exits Crosshair Tempo.")
        button = PushButton("Hide window to tray")
        button.clicked.connect(self.hide)
        hotkey.layout.addWidget(button)
        layout.insertWidget(layout.count() - 1, hotkey)
        restart = PushButton("Restart Crosshair Tempo")
        restart.clicked.connect(self.restart_app)
        layout.insertWidget(layout.count() - 1, restart)

    def _set_overlay_screen(self, index: int) -> None:
        if index < 0:
            return
        screen_name = self.monitor_picker.itemData(index)
        if screen_name:
            self.set_overlay_screen(screen_name)

    def _set_speed_debug(self, value: bool) -> None:
        self.settings.show_estimated_speed = value
        self.save()

    def _setting_slider(self, label: str, value: int, handler, low: int, high: int, suffix: str, setting_key: str | None = None, preview_context: str = "standing") -> QWidget:
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 8, 0, 5)
        header = QHBoxLayout()
        title_label = QLabel(label)
        header.addWidget(title_label)
        header.addStretch()
        value_label = QLabel(f"{value}{suffix}")
        value_label.setObjectName("metricCaption")
        header.addWidget(value_label)
        slider = ScrollSafeSlider(Qt.Orientation.Horizontal)
        slider.setRange(low, high)
        slider.setValue(value)
        def update_value(current: int) -> None:
            handler(current)
            value_label.setText(f"{current}{suffix}")
            if slider.hasFocus() and not slider.isSliderDown():
                self._show_preview_context(preview_context)
                self._schedule_preview_reset()

        slider.valueChanged.connect(update_value)
        slider.sliderPressed.connect(lambda: self._show_preview_context(preview_context))
        slider.sliderReleased.connect(self._schedule_preview_reset)
        if setting_key:
            self.crosshair_controls[setting_key] = (slider, value_label, suffix, title_label)
        box.addLayout(header)
        box.addWidget(slider)
        return container

    def _rotation_slider(self) -> QWidget:
        angles = (0, 15, 30, 45, 60, 90, 135, 180)
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 8, 0, 5)
        header = QHBoxLayout()
        title_label = QLabel("Rotation")
        header.addWidget(title_label)
        header.addStretch()
        value_label = QLabel(f"{self.settings.crosshair_rotation}°")
        value_label.setObjectName("metricCaption")
        header.addWidget(value_label)
        slider = ScrollSafeSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, len(angles) - 1)
        slider.setTickPosition(Slider.TickPosition.TicksBelow)
        slider.setTickInterval(1)
        slider.setValue(min(range(len(angles)), key=lambda index: abs(angles[index] - self.settings.crosshair_rotation)))
        slider.sliderPressed.connect(lambda: self._show_preview_context("standing"))
        slider.sliderReleased.connect(self._schedule_preview_reset)
        slider.valueChanged.connect(lambda index: (self._set_crosshair_rotation(angles[index]), value_label.setText(f"{angles[index]}°")))
        box.addLayout(header)
        box.addWidget(slider)
        box.addWidget(RotationTickLabels(slider, angles))
        self.crosshair_controls["crosshair_rotation"] = (slider, value_label, "°", title_label)
        return container

    def _shape_button(self, title: str, shape: str) -> ShapeChoiceButton:
        button = ShapeChoiceButton(title, shape)
        button.setChecked(self.settings.crosshair_shape == shape)
        button.clicked.connect(lambda: self._set_shape(shape))
        self.shape_buttons[shape] = button
        return button

    def _set_shape(self, shape: str) -> None:
        self.settings.crosshair_shape = shape
        for name, button in self.shape_buttons.items():
            button.setChecked(name == shape)
        self._appearance_changed()
        self._refresh_crosshair_controls()
        self._update_preview()

    def _choose_colour(self) -> None:
        self._show_preview_context("standing")
        colour = QColorDialog.getColor(QColor(self.settings.crosshair_color), self, "Crosshair colour")
        if colour.isValid():
            self.settings.crosshair_color = colour.name()
            self._appearance_changed()
            self._refresh_colour_button()
            self._update_preview()
        self._schedule_preview_reset()

    def _refresh_colour_button(self) -> None:
        self.colour_button.setText(self.settings.crosshair_color.upper())
        self.colour_button.setStyleSheet(f"background: {self.settings.crosshair_color}; color: #101214;")

    def _choose_marker_colour(self) -> None:
        self._show_preview_context("marker")
        colour = QColorDialog.getColor(QColor(self.settings.marker_color), self, "Movement marker colour")
        if colour.isValid():
            self.settings.marker_color = colour.name()
            self._appearance_changed()
            self._refresh_marker_colour_button()
            self._refresh_movement_marker()
            self._update_preview()
        self._schedule_preview_reset()

    def _choose_outline_colour(self) -> None:
        self._show_preview_context("standing")
        colour = QColorDialog.getColor(QColor(self.settings.crosshair_outline_color), self, "Outline colour")
        if colour.isValid():
            self.settings.crosshair_outline_color = colour.name()
            self._appearance_changed()
            self._refresh_outline_colour_button()
            self._update_preview()
        self._schedule_preview_reset()

    def _refresh_marker_colour_button(self) -> None:
        self.marker_colour_button.setText(f"MARKER {self.settings.marker_color.upper()}")
        self.marker_colour_button.setStyleSheet(f"background: {self.settings.marker_color}; color: #101214;")

    def _refresh_outline_colour_button(self) -> None:
        self.outline_colour_button.setText(f"OUTLINE {self.settings.crosshair_outline_color.upper()}")
        self.outline_colour_button.setStyleSheet(f"background: {self.settings.crosshair_outline_color}; color: #f4f6f8;")

    def _refresh_movement_marker(self) -> None:
        if self.movement_marker:
            self.movement_marker.setStyleSheet(f"color: {self.settings.marker_color};")

    def _update_preview(self) -> None:
        if self.preview:
            self.preview.update()

    def _show_preview_context(self, context: str) -> None:
        self.preview_reset_timer.stop()
        if self.preview:
            self.preview.show_context(context)

    def _schedule_preview_reset(self) -> None:
        self.preview_reset_timer.start()

    def _reset_preview_context(self) -> None:
        if self.preview:
            self.preview.show_context("standing")

    def _appearance_changed(self) -> None:
        update_profile_from_settings(self.active_profile, self.settings)
        self.profile_store.save(self.active_profile)
        self.save()

    def _refresh_profile_list(self) -> None:
        if not self.profile_list:
            return
        while self.profile_list.count():
            item = self.profile_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for profile in self.profiles:
            row = QWidget()
            row.setObjectName("profileCard")
            row.setProperty("selected", profile.id == self.active_profile.id)
            row.setStyleSheet(f"background: {profile.accent_color};")
            row.setFixedHeight(38)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(2, 2, 3, 2)
            row_layout.setSpacing(2)
            button = ProfileNameButton(profile.name)
            button.setObjectName("profile")
            button.clicked.connect(lambda _checked=False, selected=profile: self._select_profile(selected))
            button.doubleClicked.connect(lambda selected=profile, card=row, name_button=button: self._start_inline_rename(selected, card, name_button))
            row_layout.addWidget(button, 1)
            menu = QToolButton()
            menu.setObjectName("profileDots")
            menu.setText("⋮")
            menu.setToolTip(f"Actions for {profile.name}")
            menu.setFixedSize(29, 32)
            menu.clicked.connect(lambda _checked=False, selected=profile: self._profile_menu(selected))
            row_layout.addWidget(menu)
            self.profile_list.addWidget(row)

    def _select_profile(self, profile: CrosshairProfile) -> None:
        self.active_profile = profile
        apply_profile(self.settings, profile)
        self.save()
        self._refresh_profile_list()
        self._refresh_crosshair_controls()
        self._update_preview()

    def _refresh_crosshair_controls(self) -> None:
        for name, button in self.shape_buttons.items():
            button.setChecked(self.settings.crosshair_shape == name)
        self._refresh_colour_button()
        self._refresh_marker_colour_button()
        self._refresh_outline_colour_button()
        self._refresh_movement_marker()
        self.center_dot_switch.blockSignals(True)
        self.center_dot_switch.setChecked(self.settings.center_dot)
        self.center_dot_switch.blockSignals(False)
        self.outline_switch.blockSignals(True)
        self.outline_switch.setChecked(self.settings.crosshair_outline)
        self.outline_switch.blockSignals(False)
        self._refresh_shape_dependent_controls()
        for key, (slider, label, suffix, title_label) in self.crosshair_controls.items():
            value = getattr(self.settings, key)
            slider.blockSignals(True)
            if key == "crosshair_rotation":
                angles = (0, 15, 30, 45, 60, 90, 135, 180)
                slider.setValue(min(range(len(angles)), key=lambda index: abs(angles[index] - value)))
            else:
                slider.setValue(value)
            slider.blockSignals(False)
            # QFluent's custom handle is normally moved by its valueChanged
            # signal. Signals are blocked above to avoid writing settings while
            # loading a profile, so synchronise the handle explicitly.
            slider._adjustHandlePos()
            slider.update()
            label.setText(f"{value}{suffix}")
        labels = {
            "ring": ("Still diameter", "Movement diameter"),
            "cross": ("Arm size", "Movement spread"),
            "dot": ("Still dot size", "Movement dot size"),
        }
        standing_label, moving_label = labels.get(self.settings.crosshair_shape, labels["ring"])
        self.crosshair_controls["standing_size"][3].setText(standing_label)
        self.crosshair_controls["moving_size"][3].setText(moving_label)

    def _refresh_shape_dependent_controls(self) -> None:
        is_line_shape = self.settings.crosshair_shape == "cross"
        for widget in self.cross_only_widgets:
            widget.setVisible(is_line_shape)
        is_dot = self.settings.crosshair_shape == "dot"
        for widget in self.centre_dot_widgets:
            widget.setVisible(not is_dot)
        if "standing_size" in self.crosshair_controls:
            self.crosshair_controls["standing_size"][0].setMinimum(1 if is_dot else 6)
            self.crosshair_controls["moving_size"][0].setMinimum(3 if is_dot else 24)

    def _new_profile(self) -> None:
        name = self._next_profile_name("New crosshair")
        profile_id = self.profile_store.make_id(name)
        profile = CrosshairProfile.from_settings(profile_id, name.strip(), self.settings, self._next_profile_accent())
        self.profiles.append(profile)
        self.profile_store.save(profile)
        self._select_profile(profile)

    def _clone_profile(self) -> None:
        name = self._next_profile_name(f"{self.active_profile.name} copy")
        profile = CrosshairProfile.from_settings(self.profile_store.make_id(name), name.strip(), self.settings, self._next_profile_accent())
        self.profiles.append(profile)
        self.profile_store.save(profile)
        self._select_profile(profile)

    def _profile_menu(self, profile: CrosshairProfile | None = None) -> None:
        profile = profile or self.active_profile
        menu = QMenu(self)
        new_action = menu.addAction("New profile")
        clone_action = menu.addAction("Clone")
        menu.addSeparator()
        copy_action = menu.addAction("Copy share code")
        import_action = menu.addAction("Import share code")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.cursor().pos())
        if chosen == new_action:
            self._new_profile()
        elif chosen == clone_action:
            self._select_profile(profile)
            self._clone_profile()
        elif chosen == copy_action:
            QApplication.clipboard().setText(export_share_code(profile))
            self._show_share_import("Share code copied — paste an SV1 code here to import.")
        elif chosen == import_action:
            self._show_share_import("Paste a share code and press Enter.")
        elif chosen == delete_action:
            if len(self.profiles) == 1:
                return
            self.profile_store.delete(profile)
            self.profiles.remove(profile)
            if self.active_profile is profile:
                self._select_profile(self.profiles[0])
            else:
                self._refresh_profile_list()

    def _show_share_import(self, status: str) -> None:
        self.share_status.setText(status)
        self.share_input.setFocus()

    def _import_share_code(self) -> None:
        code = self.share_input.text()
        name = self._next_profile_name("Imported crosshair")
        try:
            profile = import_share_code(
                code, self.settings, self.profile_store.make_id(name), self._next_profile_accent(),
            )
        except ValueError as error:
            self.share_status.setText(str(error))
            return
        profile.name = self._next_profile_name(profile.name)
        profile.id = self.profile_store.make_id(profile.name)
        self.profiles.append(profile)
        self.profile_store.save(profile)
        self.share_input.clear()
        self.share_status.setText(f"Imported “{profile.name}”.")
        self._select_profile(profile)

    def _start_inline_rename(self, profile: CrosshairProfile, card: QWidget, button: ProfileNameButton) -> None:
        edit = QLineEdit(profile.name, card)
        edit.setObjectName("profileRename")
        layout = card.layout()
        layout.insertWidget(0, edit, 1)
        button.hide()
        edit.editingFinished.connect(lambda: self._finish_inline_rename(profile, edit))
        edit.setFocus()
        edit.selectAll()

    def _finish_inline_rename(self, profile: CrosshairProfile, edit: QLineEdit) -> None:
        name = edit.text().strip()
        if name:
            old_id = profile.id
            profile.name = self._next_profile_name(name, excluded=profile)
            profile.id = self.profile_store.make_id(profile.name, excluded=old_id)
            if old_id != profile.id:
                self.profile_store.delete_id(old_id)
            self.profile_store.save(profile)
            if self.active_profile is profile:
                self.settings.active_crosshair_profile = profile.id
                self.save()
        self._refresh_profile_list()

    def _next_profile_accent(self) -> str:
        accents = ("#FFB84D", "#8BE28B", "#64C9FF", "#C99BFF", "#FF8EAE", "#64E0C0", "#F7D85C")
        used = {profile.accent_color for profile in self.profiles}
        unused = [colour for colour in accents if colour not in used]
        return random.choice(unused or list(accents))

    def _next_profile_name(self, base: str, excluded: CrosshairProfile | None = None) -> str:
        names = {profile.name.casefold() for profile in self.profiles if profile is not excluded}
        if base.casefold() not in names:
            return base
        number = 2
        while f"{base} {number}".casefold() in names:
            number += 1
        return f"{base} {number}"

    def _set_focus_scope(self, value: bool) -> None: self.settings.only_cs2_focused = value; self.save(); self.sync_overlay()
    def _set_max_speed(self, value: int) -> None: self.settings.max_speed = value; self.save()
    def _set_low_movement_speed(self, value: int) -> None: self.settings.low_movement_speed = value; self.save()
    def _set_acceleration(self, value: int) -> None: self.settings.ground_acceleration = value; self.save()
    def _set_friction(self, value: int) -> None: self.settings.ground_friction = value; self.save()
    def _set_crouch_speed(self, value: int) -> None: self.settings.crouch_speed_percent = value; self.save()
    def _set_standing_size(self, value: int) -> None: self.settings.standing_size = value; self._appearance_changed(); self._update_preview()
    def _set_moving_size(self, value: int) -> None: self.settings.moving_size = value; self._appearance_changed(); self._update_preview()
    def _set_opacity(self, value: int) -> None: self.settings.opacity = value; self._appearance_changed()
    def _set_crosshair_outline(self, value: bool) -> None: self.settings.crosshair_outline = value; self._appearance_changed(); self._update_preview()
    def _set_crosshair_outline_thickness(self, value: int) -> None: self.settings.crosshair_outline_thickness = value; self._appearance_changed(); self._update_preview()
    def _set_crosshair_thickness(self, value: int) -> None: self.settings.crosshair_thickness = value; self._appearance_changed(); self._update_preview()
    def _set_crosshair_gap(self, value: int) -> None: self.settings.crosshair_gap = value; self._appearance_changed(); self._update_preview()
    def _set_crosshair_rotation(self, value: int) -> None: self.settings.crosshair_rotation = value; self._appearance_changed(); self._update_preview()
    def _set_center_dot(self, value: bool) -> None: self.settings.center_dot = value; self._appearance_changed(); self._update_preview()
    def _set_center_dot_size(self, value: int) -> None: self.settings.center_dot_size = value; self._appearance_changed(); self._update_preview()

    def closeEvent(self, event) -> None:
        event.accept()
        self.quit_app()

class CrosshairTempoApp(QObject):
    def __init__(self) -> None:
        super().__init__()
        if sys.platform == "win32":
            # Give Windows a stable identity so its taskbar/Start integration
            # can associate a Crosshair Tempo shortcut with this running app.
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("skvoch.CrosshairTempo")
        self.qt = QApplication(sys.argv)
        self.qt.setQuitOnLastWindowClosed(False)
        self.qt.setWindowIcon(app_icon("crosshair-tempo"))
        setTheme(Theme.DARK)
        self.settings = load_settings()
        self.profile_store = CrosshairProfileStore()
        available_profiles = self.profile_store.load_all(self.settings)
        selected_profile = next((profile for profile in available_profiles if profile.id == self.settings.active_crosshair_profile), available_profiles[0])
        apply_profile(self.settings, selected_profile)
        self.engine = MovementFeedbackEngine(self.settings)
        self.overlay = CrosshairOverlay(self.engine.snapshot, self.settings)
        self.window = SettingsWindow(self.settings, self.engine.snapshot, self.set_overlay_enabled, self._save_settings, self._sync_overlay_visibility, self.quit, self.restart, self.profile_store, self.set_autostart, self.set_overlay_screen)
        self.tracker = InputTracker(self.should_track)
        self.tracker.input_event.connect(self._consume_input_event)
        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self._sync_overlay_visibility)
        self.focus_timer.start(250)
        signal.signal(signal.SIGINT, lambda _signum, _frame: self.quit())
        self._setup_tray()

    def should_track(self) -> bool:
        return not self.settings.only_cs2_focused or cs2_is_foreground()

    def _save_settings(self) -> None:
        save_settings(self.settings)

    @Slot(str, object)
    def _consume_input_event(self, kind: str, key: str | None) -> None:
        if kind == "press" and key is not None:
            self.engine.on_key_press(key)
        elif kind == "release" and key is not None:
            self.engine.on_key_release(key)
        elif kind == "toggle":
            self.toggle_overlay()

    def set_overlay_enabled(self, enabled: bool) -> None:
        self.settings.overlay_enabled = enabled
        self.window.enabled.blockSignals(True)
        self.window.enabled.setChecked(enabled)
        self.window.enabled.blockSignals(False)
        self._sync_overlay_visibility()
        self._save_settings()

    def set_autostart(self, enabled: bool) -> None:
        if set_start_with_windows(enabled):
            self.settings.start_with_windows = enabled
            self._save_settings()
            return
        self.window.autostart.blockSignals(True)
        self.window.autostart.setChecked(self.settings.start_with_windows)
        self.window.autostart.blockSignals(False)

    def set_overlay_screen(self, screen_name: str) -> None:
        self.settings.overlay_screen = screen_name
        self.overlay.sync_screen()
        self._save_settings()

    def _sync_overlay_visibility(self) -> None:
        self.overlay.setVisible(self.settings.overlay_enabled and self.should_track())

    def toggle_overlay(self) -> None:
        self.set_overlay_enabled(not self.settings.overlay_enabled)

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.window)
        menu = QMenu()
        open_action = QAction("Open Crosshair Tempo", self.window)
        open_action.triggered.connect(self.window.showNormal)
        toggle_action = QAction("Toggle overlay (F8)", self.window)
        toggle_action.triggered.connect(self.toggle_overlay)
        quit_action = QAction("Quit", self.window)
        quit_action.triggered.connect(self.quit)
        menu.addActions([open_action, toggle_action, quit_action])
        self.tray.setContextMenu(menu)
        self.tray.setIcon(app_icon("crosshair-tempo"))
        self.tray.setToolTip("Crosshair Tempo")
        self.tray.activated.connect(self._open_window_from_tray)
        self.tray.show()

    def _open_window_from_tray(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Bring the control window back with a normal left-click in the tray."""
        if reason not in {QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick}:
            return
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def quit(self) -> None:
        self._save_settings()
        self.tracker.stop()
        self.qt.quit()

    def restart(self) -> None:
        project_directory = str(Path(__file__).resolve().parent.parent)
        QProcess.startDetached(sys.executable, ["-m", "crosshair_tempo"], project_directory)
        self.quit()

    def run(self) -> int:
        self._sync_overlay_visibility()
        self.window.show()
        self.tracker.start()
        return self.qt.exec()


def run() -> None:
    raise SystemExit(CrosshairTempoApp().run())
