import unittest

from crosshair_tempo.models import MovementState, Settings
from crosshair_tempo.timing import MovementFeedbackEngine


class MovementFeedbackEngineTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(max_speed=200, low_movement_speed=68, ground_acceleration=1000, ground_friction=400)
        self.engine = MovementFeedbackEngine(self.settings)

    def test_holding_a_accelerates_to_full_speed_and_expands_ring(self):
        self.engine.on_key_press("A", 1.0)
        state = self.engine.snapshot(1.3)
        self.assertEqual(state.movement, MovementState.MOVING_LEFT)
        self.assertEqual(self.engine.velocity, -200)
        self.assertEqual(state.progress, 1.0)
        self.assertEqual(state.estimated_speed, 200)

    def test_release_slows_down_with_friction(self):
        self.engine.on_key_press("A", 1.0)
        self.engine.snapshot(1.3)
        self.engine.on_key_release("A", 1.3)
        self.engine.snapshot(1.4)
        self.assertAlmostEqual(self.engine.velocity, -160, places=4)

    def test_counter_strafe_stops_faster_than_release(self):
        self.engine.on_key_press("A", 1.0)
        self.engine.snapshot(1.3)
        self.engine.on_key_release("A", 1.3)
        self.engine.on_key_press("D", 1.3)
        state = self.engine.snapshot(1.4)
        self.assertEqual(state.movement, MovementState.COUNTER_LEFT_TO_RIGHT)
        self.assertAlmostEqual(self.engine.velocity, -100, places=4)

    def test_both_keys_held_is_overlap_and_uses_friction(self):
        self.engine.on_key_press("A", 1.0)
        self.engine.snapshot(1.3)
        self.engine.on_key_press("D", 1.3)
        state = self.engine.snapshot(1.4)
        self.assertEqual(state.movement, MovementState.OVERLAP)
        self.assertAlmostEqual(self.engine.velocity, -160, places=4)

    def test_releasing_a_after_overlap_accelerates_right_then_expands_again(self):
        self.engine.on_key_press("A", 1.0)
        self.engine.snapshot(1.3)
        self.engine.on_key_press("D", 1.3)
        self.engine.snapshot(1.4)
        self.engine.on_key_release("A", 1.4)
        marker = self.engine.snapshot(1.56)
        self.assertTrue(marker.marker_active)
        moving = self.engine.snapshot(1.7)
        self.assertEqual(moving.movement, MovementState.MOVING_RIGHT)
        self.assertGreater(moving.progress, 0)

    def test_speed_under_low_movement_threshold_keeps_small_ring(self):
        self.engine.on_key_press("D", 1.0)
        state = self.engine.snapshot(1.05)
        self.assertAlmostEqual(self.engine.velocity, 50)
        self.assertEqual(state.progress, 0.0)

    def test_ctrl_caps_crouch_speed_below_low_movement_threshold(self):
        self.engine.on_key_press("CTRL", 1.0)
        idle = self.engine.snapshot(1.01)
        self.assertTrue(idle.crouching)
        self.assertEqual(idle.speed_ratio, 0.0)
        self.engine.on_key_press("D", 1.0)
        state = self.engine.snapshot(1.3)
        self.assertAlmostEqual(self.engine.velocity, 68)
        self.assertEqual(state.progress, 0.0)
        self.assertTrue(state.crouching)
        self.assertEqual(state.speed_ratio, 1.0)

    def test_direction_change_activates_movement_marker(self):
        self.engine.on_key_press("A", 1.0)
        self.engine.snapshot(1.3)
        self.engine.on_key_release("A", 1.3)
        self.engine.on_key_press("D", 1.3)
        state = self.engine.snapshot(1.5)
        self.assertTrue(state.marker_active)
        self.assertTrue(state.direction_change_marker)

    def test_holding_w_accelerates_forward(self):
        self.engine.on_key_press("W", 1.0)
        state = self.engine.snapshot(1.3)
        self.assertEqual(self.engine.forward_velocity, 200)
        self.assertEqual(state.movement, MovementState.MOVING_FORWARD)
        self.assertEqual(state.progress, 1.0)

    def test_w_to_s_counter_strafe_reduces_forward_velocity(self):
        self.engine.on_key_press("W", 1.0)
        self.engine.snapshot(1.3)
        self.engine.on_key_release("W", 1.3)
        self.engine.on_key_press("S", 1.3)
        state = self.engine.snapshot(1.4)
        self.assertAlmostEqual(self.engine.forward_velocity, 100, places=4)
        self.assertEqual(state.movement, MovementState.COUNTER_FORWARD_TO_BACKWARD)

    def test_diagonal_speed_is_normalised_to_weapon_maximum(self):
        self.engine.on_key_press("W", 1.0)
        self.engine.on_key_press("A", 1.0)
        state = self.engine.snapshot(1.4)
        self.assertAlmostEqual((self.engine.velocity ** 2 + self.engine.forward_velocity ** 2) ** 0.5, 200, places=4)
        self.assertEqual(state.progress, 1.0)

    def test_w_and_s_is_overlap(self):
        self.engine.on_key_press("W", 1.0)
        self.engine.snapshot(1.3)
        self.engine.on_key_press("S", 1.3)
        self.assertEqual(self.engine.snapshot(1.4).movement, MovementState.OVERLAP)

    def test_movement_marker_expires_after_hold_period(self):
        self.engine.on_key_press("A", 1.0)
        self.engine.snapshot(1.3)
        self.engine.on_key_release("A", 1.3)
        self.assertTrue(self.engine.snapshot(1.65).marker_active)
        self.assertFalse(self.engine.snapshot(1.75).marker_active)

    def test_unknown_key_does_not_change_velocity(self):
        self.engine.on_key_press("SPACE", 1.0)
        self.engine.snapshot(1.3)
        self.assertEqual(self.engine.velocity, 0.0)
        self.assertEqual(self.engine.forward_velocity, 0.0)


if __name__ == "__main__":
    unittest.main()
