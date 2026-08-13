import os
import tempfile
import unittest
from pathlib import Path

# Run Qt in memory so these tests never create a desktop window.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from crosshair_tempo.app import SettingsWindow
from crosshair_tempo.crosshair_profiles import CrosshairProfileStore
from crosshair_tempo.models import CrosshairState, MovementState, Settings


class CrosshairSettingsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = Settings(standing_size=16, moving_size=50)
        self.window = SettingsWindow(
            self.settings,
            lambda: CrosshairState(MovementState.STANDING),
            lambda _enabled: None,
            lambda: None,
            lambda: None,
            lambda: None,
            lambda: None,
            CrosshairProfileStore(Path(self.directory.name)),
        )
        self.window.resize(1280, 860)
        self.window.show()
        self.application.processEvents()
        # The window applies the selected template profile during creation;
        # set a known test profile after that behaviour has completed.
        self.settings.standing_size = 16
        self.settings.moving_size = 50
        self.window._refresh_crosshair_controls()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        self.directory.cleanup()

    def test_shape_switch_does_not_overwrite_profile_sizes(self):
        self.window._set_shape("dot")
        self.assertEqual(self.settings.standing_size, 16)
        self.assertEqual(self.settings.moving_size, 50)

    def test_shape_specific_labels_and_visibility_are_correct(self):
        self.window._set_shape("cross")
        self.assertEqual(self.window.crosshair_controls["standing_size"][3].text(), "Arm size")
        self.assertEqual(self.window.crosshair_controls["moving_size"][3].text(), "Movement spread")
        self.assertTrue(all(not widget.isHidden() for widget in self.window.cross_only_widgets))

        self.window._set_shape("dot")
        self.assertEqual(self.window.crosshair_controls["standing_size"][3].text(), "Still dot size")
        self.assertEqual(self.window.crosshair_controls["moving_size"][3].text(), "Movement dot size")
        self.assertTrue(all(widget.isHidden() for widget in self.window.cross_only_widgets))
        self.assertTrue(all(widget.isHidden() for widget in self.window.centre_dot_widgets))

    def test_slider_handle_syncs_after_form_change(self):
        self.window._set_shape("dot")
        self.application.processEvents()
        slider = self.window.crosshair_controls["standing_size"][0]
        self.assertGreater(slider.handle.x(), 0)
        self.assertLess(slider.handle.x(), slider.width())

    def test_settings_workspace_switches_between_general_and_movement(self):
        self.window._activate_page("settings")
        self.assertEqual(self.window.settings_sections.currentIndex(), 0)
        self.assertTrue(self.window.settings_section_buttons[0].isChecked())

        self.window._activate_settings_section(1)
        self.application.processEvents()

        self.assertEqual(self.window.settings_sections.currentIndex(), 1)
        self.assertTrue(self.window.settings_section_buttons[1].isChecked())
        self.assertFalse(self.window.settings_section_buttons[0].isChecked())


if __name__ == "__main__":
    unittest.main()
