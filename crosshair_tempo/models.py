from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class MovementState(Enum):
    STANDING = auto()
    MOVING_LEFT = auto()
    MOVING_RIGHT = auto()
    COUNTER_LEFT_TO_RIGHT = auto()
    COUNTER_RIGHT_TO_LEFT = auto()
    MOVING_FORWARD = auto()
    MOVING_BACKWARD = auto()
    COUNTER_FORWARD_TO_BACKWARD = auto()
    COUNTER_BACKWARD_TO_FORWARD = auto()
    OVERLAP = auto()


@dataclass(frozen=True)
class CrosshairState:
    movement: MovementState
    # 0 = low movement, 1 = full movement.
    progress: float = 0.0
    marker_active: bool = False
    direction_change_marker: bool = False
    crouching: bool = False
    speed_ratio: float = 0.0


@dataclass
class Settings:
    overlay_enabled: bool = True
    only_cs2_focused: bool = True
    hotkey: str = "F8"
    opacity: int = 100
    moving_size: int = 44
    standing_size: int = 16
    crosshair_shape: str = "ring"
    crosshair_color: str = "#F0F3F8"
    marker_color: str = "#43D297"
    crosshair_rotation: int = 0
    crosshair_thickness: int = 2
    crosshair_gap: int = 7
    crosshair_outline: bool = False
    crosshair_outline_thickness: int = 1
    center_dot: bool = False
    center_dot_size: int = 3
    active_crosshair_profile: str = "default"
    # Rifle movement-model defaults. Values stay configurable until a later
    # calibration pass can replace them with measured per-weapon values.
    max_speed: int = 215
    low_movement_speed: int = 73
    ground_acceleration: int = 1400
    ground_friction: int = 800
    crouch_speed_percent: int = 34
