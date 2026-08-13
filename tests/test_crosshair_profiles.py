import tempfile
import unittest
from pathlib import Path

from crosshair_tempo.crosshair_profiles import (
    CrosshairProfileStore, apply_profile, export_share_code, import_share_code,
    update_profile_from_settings,
)
from crosshair_tempo.models import Settings


class CrosshairProfileStoreTests(unittest.TestCase):
    def test_empty_library_uses_bundled_templates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(crosshair_color="#FF00AA", moving_size=77)
            profiles = CrosshairProfileStore(Path(directory)).load_all(settings)
            self.assertEqual(profiles[0].name, "Cross 45")
            self.assertTrue((Path(directory) / "cross-45.json").exists())

    def test_empty_library_installs_bundled_templates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profiles = CrosshairProfileStore(Path(directory)).load_all(Settings())
            self.assertEqual([profile.name for profile in profiles], ["Cross 45", "Cross", "Ring"])

    def test_profile_applies_and_updates_appearance_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(max_speed=222)
            store = CrosshairProfileStore(Path(directory))
            profile = store.load_all(settings)[0]
            settings.crosshair_color = "#00FFAA"
            settings.moving_size = 60
            update_profile_from_settings(profile, settings)
            store.save(profile)
            restored = store.load_all(Settings())[0]
            target = Settings(max_speed=222)
            apply_profile(target, restored)
            self.assertEqual(target.crosshair_color, "#00FFAA")
            self.assertEqual(target.moving_size, 60)
            self.assertEqual(target.max_speed, 222)

    def test_share_code_round_trip_is_versioned_and_appearance_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = CrosshairProfileStore(Path(directory))
            profile = store.load_all(Settings(crosshair_color="#BADA55"))[0]
            profile.crosshair_color = "#BADA55"
            profile.crosshair_rotation = 45
            profile.crosshair_outline = True
            profile.crosshair_outline_thickness = 3
            code = export_share_code(profile)
            restored = import_share_code(code, Settings(), "imported", "#FFB84D")
            self.assertTrue(code.startswith("SV1:"))
            self.assertEqual(restored.name, profile.name)
            self.assertEqual(restored.crosshair_color, "#BADA55")
            self.assertEqual(restored.crosshair_rotation, 45)
            self.assertTrue(restored.crosshair_outline)
            self.assertEqual(restored.crosshair_outline_thickness, 3)

    def test_bad_share_code_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            import_share_code("SV1:not-a-real-code", Settings(), "imported", "#FFB84D")
