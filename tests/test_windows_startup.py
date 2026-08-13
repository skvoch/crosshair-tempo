import unittest
from unittest.mock import patch

from crosshair_tempo import windows_startup


class WindowsStartupTests(unittest.TestCase):
    def test_source_startup_command_launches_the_package(self) -> None:
        with patch.object(windows_startup.sys, "frozen", False, create=True):
            command = windows_startup.startup_command()
        self.assertIn("-m crosshair_tempo", command)
        self.assertIn("cmd.exe /d /c", command)

    def test_startup_is_a_noop_outside_windows(self) -> None:
        with patch.object(windows_startup.sys, "platform", "linux"):
            self.assertFalse(windows_startup.set_start_with_windows(True))


if __name__ == "__main__":
    unittest.main()
