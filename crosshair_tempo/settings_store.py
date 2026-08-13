from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

from .models import Settings

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"


def load_settings(path: Path = SETTINGS_PATH) -> Settings:
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Settings()
    if "accurate_speed" in data and "low_movement_speed" not in data:
        data["low_movement_speed"] = data["accurate_speed"]
    if "precision_color" in data and "marker_color" not in data:
        data["marker_color"] = data["precision_color"]
    allowed = {field.name for field in fields(Settings)}
    return Settings(**{key: value for key, value in data.items() if key in allowed})


def save_settings(settings: Settings, path: Path = SETTINGS_PATH) -> None:
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
