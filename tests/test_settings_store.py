import tempfile
import unittest
from pathlib import Path

from crosshair_tempo.models import Settings
from crosshair_tempo.settings_store import load_settings, save_settings


class SettingsStoreTests(unittest.TestCase):
    def test_round_trip_preserves_input_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings(Settings(only_cs2_focused=True, crosshair_shape="cross"), path)
            restored = load_settings(path)
            self.assertTrue(restored.only_cs2_focused)
            self.assertEqual(restored.crosshair_shape, "cross")

    def test_invalid_file_uses_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not JSON", encoding="utf-8")
            self.assertTrue(load_settings(path).only_cs2_focused)

    def test_legacy_settings_fields_are_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"accurate_speed": 62, "precision_color": "#00FFAA"}', encoding="utf-8")
            restored = load_settings(path)
            self.assertEqual(restored.low_movement_speed, 62)
            self.assertEqual(restored.marker_color, "#00FFAA")
