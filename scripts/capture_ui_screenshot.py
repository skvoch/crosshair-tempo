"""Capture the Crosshair settings page for the README."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from crosshair_tempo.app import SettingsWindow
from crosshair_tempo.crosshair_profiles import CrosshairProfileStore
from crosshair_tempo.models import Settings
from crosshair_tempo.timing import MovementFeedbackEngine


OUTPUT_PATH = PROJECT_ROOT / "assets" / "crosshair-customisation.png"


def main() -> int:
    application = QApplication(sys.argv)
    setTheme(Theme.DARK)
    # Do not use a developer's local settings or profiles: the README image
    # must stay identical for every clone and every push.
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(
            active_crosshair_profile="cross",
            only_cs2_focused=True,
            overlay_enabled=False,
        )
        profiles = CrosshairProfileStore(Path(directory))
        engine = MovementFeedbackEngine(settings)
        window = SettingsWindow(
            settings, engine.snapshot, lambda _enabled: None, lambda: None,
            lambda: None, application.quit, application.quit, profiles,
        )
        window.resize(1280, 860)
        window._activate_page("crosshair")
        window.show()

        def capture() -> None:
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(OUTPUT_PATH), "PNG")
            application.quit()

        QTimer.singleShot(350, capture)
        return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
