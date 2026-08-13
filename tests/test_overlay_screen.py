import unittest

from crosshair_tempo.overlay import select_overlay_screen


class FakeScreen:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name


class OverlayScreenSelectionTests(unittest.TestCase):
    def setUp(self):
        self.primary = FakeScreen("\\\\.\\DISPLAY1")
        self.second = FakeScreen("\\\\.\\DISPLAY2")
        self.screens = [self.primary, self.second]

    def test_uses_the_saved_second_display_when_connected(self):
        selected = select_overlay_screen(self.screens, self.primary, "\\\\.\\DISPLAY2")
        self.assertIs(selected, self.second)

    def test_falls_back_to_primary_when_saved_display_is_disconnected(self):
        selected = select_overlay_screen([self.primary], self.primary, "\\\\.\\DISPLAY2")
        self.assertIs(selected, self.primary)

    def test_uses_primary_when_no_display_is_saved(self):
        selected = select_overlay_screen(self.screens, self.primary, "")
        self.assertIs(selected, self.primary)


if __name__ == "__main__":
    unittest.main()
