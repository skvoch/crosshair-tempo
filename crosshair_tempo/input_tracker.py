from __future__ import annotations

import ctypes
from typing import Callable

from pynput import keyboard
from PySide6.QtCore import QObject, Signal


def cs2_is_foreground() -> bool:
    window = ctypes.windll.user32.GetForegroundWindow()
    if not window:
        return False
    title = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetWindowTextW(window, title, len(title))
    return "counter-strike 2" in title.value.lower()


class InputTracker(QObject):
    """Read movement keys locally without modifying or replaying input."""

    # pynput invokes callbacks from its own listener thread. Qt queues this
    # signal back to the application thread, so no polling loop is needed.
    input_event = Signal(str, object)

    def __init__(self, should_track: Callable[[], bool]) -> None:
        super().__init__()
        self._should_track = should_track
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
            self.input_event.emit("toggle", None)
            return
        movement_key = self._movement_key(key)
        if movement_key and self._should_track():
            self.input_event.emit("press", movement_key)

    def _released(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        movement_key = self._movement_key(key)
        if movement_key and self._should_track():
            self.input_event.emit("release", movement_key)

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
