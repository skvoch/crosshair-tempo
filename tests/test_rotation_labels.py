import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Slider

from crosshair_tempo.app import RotationTickLabels


class RotationTickLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_endpoints_match_the_slider_handle_centres(self):
        slider = Slider(Qt.Orientation.Horizontal)
        slider.resize(800, 22)
        labels = RotationTickLabels(slider, (0, 15, 30, 45, 60, 90, 135, 180))
        labels.resize(800, 20)
        radius = slider.handle.width() / 2
        self.assertEqual(radius, 11)
        self.assertEqual(radius + (labels.width() - radius * 2) * 0 / 7, radius)
        self.assertEqual(radius + (labels.width() - radius * 2) * 7 / 7, labels.width() - radius)


if __name__ == "__main__":
    unittest.main()
