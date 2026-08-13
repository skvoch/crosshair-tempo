from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


def icon(name: str) -> QIcon:
    """Load a bundled Lucide SVG without a runtime icon-font dependency."""
    if name == "crosshair-tempo":
        return QIcon(str(Path(__file__).with_name("assets") / "slim-vizier.png"))
    return QIcon(str(Path(__file__).with_name("assets") / "icons" / f"{name}.svg"))
