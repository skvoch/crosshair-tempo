from __future__ import annotations

import json
import random
import re
import base64
import shutil
import zlib
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .models import Settings

CROSSHAIRS_PATH = Path(__file__).resolve().parent.parent / "crosshairs"
TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "templates"
PROFILE_FIELDS = (
    "opacity", "moving_size", "standing_size", "crosshair_shape", "crosshair_color",
    "marker_color", "crosshair_rotation", "crosshair_thickness", "crosshair_gap",
    "center_dot", "center_dot_size",
)
ACCENT_COLOURS = ("#FFB84D", "#8BE28B", "#64C9FF", "#C99BFF", "#FF8EAE", "#64E0C0", "#F7D85C")
SHARE_CODE_PREFIX = "SV1:"


@dataclass
class CrosshairProfile:
    id: str
    name: str
    accent_color: str
    opacity: int
    moving_size: int
    standing_size: int
    crosshair_shape: str
    crosshair_color: str
    marker_color: str
    crosshair_rotation: int
    crosshair_thickness: int
    crosshair_gap: int
    center_dot: bool
    center_dot_size: int

    @classmethod
    def from_settings(cls, profile_id: str, name: str, settings: Settings, accent_color: str | None = None) -> "CrosshairProfile":
        return cls(
            id=profile_id,
            name=name,
            accent_color=accent_color or random.choice(ACCENT_COLOURS),
            **{field: getattr(settings, field) for field in PROFILE_FIELDS},
        )


def _profile_id(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return normalized or "crosshair"


class CrosshairProfileStore:
    def __init__(self, path: Path = CROSSHAIRS_PATH) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    def load_all(self, fallback: Settings) -> list[CrosshairProfile]:
        self._install_templates_if_needed()
        profiles: list[CrosshairProfile] = []
        allowed = {field.name for field in fields(CrosshairProfile)}
        for profile_path in sorted(self.path.glob("*.json")):
            try:
                data = json.loads(profile_path.read_text(encoding="utf-8"))
                profile_defaults = asdict(CrosshairProfile.from_settings(profile_path.stem, profile_path.stem, fallback))
                if "precision_color" in data and "marker_color" not in data:
                    data["marker_color"] = data["precision_color"]
                profile_defaults.update({key: value for key, value in data.items() if key in allowed})
                profile = CrosshairProfile(**profile_defaults)
            except (OSError, TypeError, json.JSONDecodeError):
                continue
            if profile.id and profile.name:
                profiles.append(profile)
        if not profiles:
            default = CrosshairProfile.from_settings("default", "Default", fallback, "#28D8E8")
            self.save(default)
            profiles.append(default)
        return profiles

    def _install_templates_if_needed(self) -> None:
        """Seed first-run profiles without ever touching an existing library."""
        if any(self.path.glob("*.json")):
            return
        for template in TEMPLATES_PATH.glob("*.json"):
            shutil.copy2(template, self.path / template.name)

    def save(self, profile: CrosshairProfile) -> None:
        (self.path / f"{profile.id}.json").write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")

    def delete(self, profile: CrosshairProfile) -> None:
        self.delete_id(profile.id)

    def delete_id(self, profile_id: str) -> None:
        profile_path = self.path / f"{profile_id}.json"
        if profile_path.exists():
            profile_path.unlink()

    def make_id(self, name: str, excluded: str | None = None) -> str:
        base = _profile_id(name)
        candidate, number = base, 2
        while (self.path / f"{candidate}.json").exists() and candidate != excluded:
            candidate = f"{base}-{number}"
            number += 1
        return candidate


def apply_profile(settings: Settings, profile: CrosshairProfile) -> None:
    for field in PROFILE_FIELDS:
        setattr(settings, field, getattr(profile, field))
    settings.active_crosshair_profile = profile.id


def update_profile_from_settings(profile: CrosshairProfile, settings: Settings) -> None:
    for field in PROFILE_FIELDS:
        setattr(profile, field, getattr(settings, field))


def export_share_code(profile: CrosshairProfile) -> str:
    """Create a compact, self-contained, versioned appearance-only profile code."""
    payload = {"name": profile.name, **{field: getattr(profile, field) for field in PROFILE_FIELDS}}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.urlsafe_b64encode(zlib.compress(raw, level=9)).decode("ascii").rstrip("=")
    return f"{SHARE_CODE_PREFIX}{encoded}"


def import_share_code(code: str, fallback: Settings, profile_id: str, accent_color: str) -> CrosshairProfile:
    compact_code = "".join(code.strip().split())
    if not compact_code.startswith(SHARE_CODE_PREFIX):
        raise ValueError("This is not a Crosshair Tempo SV1 code.")
    encoded = compact_code[len(SHARE_CODE_PREFIX):]
    try:
        padding = "=" * (-len(encoded) % 4)
        data = json.loads(zlib.decompress(base64.urlsafe_b64decode(encoded + padding)).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, zlib.error, json.JSONDecodeError) as error:
        raise ValueError("This share code is invalid or incomplete.") from error
    if not isinstance(data, dict):
        raise ValueError("This share code has no profile data.")
    name = data.get("name", "Imported crosshair")
    if not isinstance(name, str) or not name.strip():
        name = "Imported crosshair"
    defaults = asdict(CrosshairProfile.from_settings(profile_id, name.strip(), fallback, accent_color))
    if "precision_color" in data and "marker_color" not in data:
        data["marker_color"] = data["precision_color"]
    defaults.update({field: data[field] for field in PROFILE_FIELDS if field in data})
    return CrosshairProfile(**defaults)
