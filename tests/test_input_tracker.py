import unittest

from pynput import keyboard

from crosshair_tempo.input_tracker import InputTracker


class VirtualKey:
    def __init__(self, value: int) -> None:
        self.vk = value


class InputTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[tuple[str, str | None]] = []
        self.tracker = InputTracker(lambda: True)
        self.tracker.input_event.connect(lambda kind, key: self.events.append((kind, key)))

    def test_physical_movement_keys_emit_events(self) -> None:
        self.tracker._pressed(VirtualKey(0x41))
        self.tracker._released(VirtualKey(0x41))
        self.assertEqual(self.events, [("press", "A"), ("release", "A")])

    def test_f8_emits_toggle_without_input_scope(self) -> None:
        tracker = InputTracker(lambda: False)
        tracker.input_event.connect(lambda kind, key: self.events.append((kind, key)))
        tracker._pressed(keyboard.Key.f8)
        self.assertEqual(self.events, [("toggle", None)])

    def test_input_scope_blocks_movement_events(self) -> None:
        tracker = InputTracker(lambda: False)
        tracker.input_event.connect(lambda kind, key: self.events.append((kind, key)))
        tracker._pressed(VirtualKey(0x44))
        tracker._released(VirtualKey(0x44))
        self.assertEqual(self.events, [])

    def test_unknown_key_is_ignored(self) -> None:
        self.tracker._pressed(VirtualKey(0x20))
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
