from __future__ import annotations

import ctypes
from queue import SimpleQueue
from typing import Callable

from pynput import keyboard


def cs2_is_foreground() -> bool:
    window = ctypes.windll.user32.GetForegroundWindow()
    if not window:
        return False
    title = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(window, title, len(title))
    return "counter-strike 2" in title.value.lower()


class InputTracker:
    """Read movement keys locally without modifying or replaying input."""

    def __init__(self, should_track: Callable[[], bool]) -> None:
        self._should_track = should_track
        self.events: SimpleQueue[tuple[str, str | None]] = SimpleQueue()
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        self._listener = keyboard.Listener(on_press=self._pressed, on_release=self._released)
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _pressed(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if key == keyboard.Key.f8:
            self.events.put(("toggle", None))
            return
        movement_key = self._movement_key(key)
        if movement_key and self._should_track():
            self.events.put(("press", movement_key))

    def _released(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        movement_key = self._movement_key(key)
        if movement_key and self._should_track():
            self.events.put(("release", movement_key))

    @staticmethod
    def _movement_key(key: keyboard.Key | keyboard.KeyCode) -> str | None:
        """Map physical Windows keys, not layout-dependent text characters."""
        if key in {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}:
            return "CTRL"
        virtual_key = getattr(key, "vk", None)
        if virtual_key == 0x41:  # physical A, including Russian layout 'ф'
            return "A"
        if virtual_key == 0x44:  # physical D, including Russian layout 'в'
            return "D"
        if virtual_key == 0x57:
            return "W"
        if virtual_key == 0x53:
            return "S"
        if virtual_key in {0xA2, 0xA3}:  # left/right Ctrl: crouch in default CS2 binds
            return "CTRL"
        return None
