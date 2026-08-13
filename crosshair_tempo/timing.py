from __future__ import annotations

import math
import time

from .models import CrosshairState, MovementState, Settings


class MovementFeedbackEngine:
    """Two-axis input-only estimate of CS2 ground velocity for rifles."""

    MARKER_HOLD_MS = 90

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._held: set[str] = set()
        self._velocity_x = 0.0
        self._velocity_y = 0.0
        self._last_update: float | None = None
        self._marker_at: float | None = None
        self._direction_change_marker = False
        self._just_reached_marker = False
        self._just_direction_change_marker = False

    @property
    def velocity(self) -> float:
        return self._velocity_x

    @property
    def forward_velocity(self) -> float:
        return self._velocity_y

    @property
    def speed(self) -> float:
        return self._speed()

    def on_key_press(self, key: str, at: float | None = None) -> None:
        if key not in {"A", "D", "W", "S", "CTRL"}:
            return
        self._advance(at if at is not None else time.perf_counter())
        self._held.add(key)

    def on_key_release(self, key: str, at: float | None = None) -> None:
        if key not in {"A", "D", "W", "S", "CTRL"}:
            return
        self._advance(at if at is not None else time.perf_counter())
        self._held.discard(key)

    def snapshot(self, at: float | None = None) -> CrosshairState:
        now = at if at is not None else time.perf_counter()
        self._advance(now)
        if self._just_reached_marker:
            self._marker_at = now
            self._direction_change_marker = self._just_direction_change_marker
            self._just_reached_marker = False
            self._just_direction_change_marker = False
        if self._marker_at is not None:
            if (now - self._marker_at) * 1000 <= self.MARKER_HOLD_MS:
                return CrosshairState(MovementState.STANDING, 0.0, True, self._direction_change_marker,
                                      self._is_crouching(), self._speed_ratio())
            self._marker_at = None
            self._direction_change_marker = False
        return CrosshairState(self._movement_state(), self._movement_progress(), False, False,
                              self._is_crouching(), self._speed_ratio())

    def _advance(self, now: float) -> None:
        if self._last_update is None:
            self._last_update = now
            return
        remaining = max(0.0, now - self._last_update)
        while remaining > 0:
            dt = min(remaining, 1 / 240)
            previous_speed = self._speed()
            target_x, target_y = self._target_velocity()
            previous_x, previous_y = self._velocity_x, self._velocity_y
            self._velocity_x = self._advance_axis(self._velocity_x, target_x, dt)
            self._velocity_y = self._advance_axis(self._velocity_y, target_y, dt)
            if previous_speed > self.settings.low_movement_speed >= self._speed():
                self._just_reached_marker = True
                self._just_direction_change_marker = ((target_x != 0 and previous_x * target_x < 0) or
                                                      (target_y != 0 and previous_y * target_y < 0))
            remaining -= dt
        self._last_update = now

    def _target_velocity(self) -> tuple[float, float]:
        x, y = self._horizontal_direction(), self._vertical_direction()
        length = math.hypot(x, y)
        if length == 0:
            return 0.0, 0.0
        speed = self._current_max_speed() / length
        return x * speed, y * speed

    def _advance_axis(self, velocity: float, target: float, dt: float) -> float:
        if target == 0:
            result = self._move_toward(velocity, 0.0, self.settings.ground_friction * dt)
        else:
            ratio = abs(target) / self._current_max_speed()
            result = self._move_toward(velocity, target, self.settings.ground_acceleration * ratio * dt)
        return 0.0 if abs(result) < 1e-6 else result

    @staticmethod
    def _move_toward(value: float, target: float, step: float) -> float:
        return min(value + step, target) if value < target else max(value - step, target)

    def _horizontal_direction(self) -> int:
        keys = self._held & {"A", "D"}
        return -1 if keys == {"A"} else 1 if keys == {"D"} else 0

    def _vertical_direction(self) -> int:
        keys = self._held & {"W", "S"}
        return 1 if keys == {"W"} else -1 if keys == {"S"} else 0

    def _current_max_speed(self) -> float:
        return self.settings.max_speed * self.settings.crouch_speed_percent / 100 if self._is_crouching() else self.settings.max_speed

    def _is_crouching(self) -> bool:
        return "CTRL" in self._held

    def _speed(self) -> float:
        return math.hypot(self._velocity_x, self._velocity_y)

    def _speed_ratio(self) -> float:
        return min(1.0, self._speed() / max(1.0, self._current_max_speed()))

    def _has_overlap(self) -> bool:
        return {"A", "D"}.issubset(self._held) or {"W", "S"}.issubset(self._held)

    def _movement_state(self) -> MovementState:
        if self._has_overlap():
            return MovementState.OVERLAP
        if self._speed() == 0:
            return MovementState.STANDING
        x, y = self._horizontal_direction(), self._vertical_direction()
        if x and self._velocity_x * x < 0:
            return MovementState.COUNTER_LEFT_TO_RIGHT if x > 0 else MovementState.COUNTER_RIGHT_TO_LEFT
        if y and self._velocity_y * y < 0:
            return MovementState.COUNTER_FORWARD_TO_BACKWARD if y < 0 else MovementState.COUNTER_BACKWARD_TO_FORWARD
        if abs(self._velocity_x) >= abs(self._velocity_y):
            return MovementState.MOVING_RIGHT if self._velocity_x > 0 else MovementState.MOVING_LEFT
        return MovementState.MOVING_FORWARD if self._velocity_y > 0 else MovementState.MOVING_BACKWARD

    def _movement_progress(self) -> float:
        threshold = self.settings.low_movement_speed
        maximum = max(threshold + 1, self._current_max_speed())
        linear = max(0.0, min(1.0, (self._speed() - threshold) / (maximum - threshold)))
        return linear * linear * (3 - 2 * linear)
