"""Pure tests for opacity transitions and UIA output semantics."""
import json
import unittest

from rings.transition import OpacityTransition
from rings.uia import parse_uia_line


class FadeTests(unittest.TestCase):
    def test_fade_in_and_out_without_flickering(self):
        fade = OpacityTransition()
        fade.request(True, 10.0, fade_in=0.2, fade_out=0.12)
        self.assertAlmostEqual(fade.advance(10.0), 0.0)
        self.assertAlmostEqual(fade.advance(10.1), 0.5, places=5)
        self.assertAlmostEqual(fade.advance(10.2), 1.0, places=5)
        # Unchanged requests must never restart a transition.
        fade.request(True, 10.21, fade_in=0.2, fade_out=0.12)
        self.assertEqual(fade.advance(10.21), 1.0)
        fade.request(False, 10.25, fade_in=0.2, fade_out=0.12)
        self.assertAlmostEqual(fade.advance(10.31), 0.5, places=5)
        self.assertAlmostEqual(fade.advance(10.37), 0.0, places=5)

    def test_reverse_inflight_fade_when_pet_reappears(self):
        fade = OpacityTransition()
        fade.request(True, 1.0, fade_in=0.2, fade_out=0.15)
        fade.advance(1.2)
        fade.request(False, 1.3, fade_in=0.2, fade_out=0.15)
        self.assertTrue(0 < fade.advance(1.37) < 1)
        current = fade.alpha
        fade.request(True, 1.37, fade_in=0.2, fade_out=0.15)
        self.assertAlmostEqual(fade.alpha, current)
        self.assertAlmostEqual(fade.advance(1.57), 1.0)

    def test_disable_fade_immediate_hide(self):
        fade = OpacityTransition()
        fade.request(True, 0.0, fade_in=0.0, fade_out=0.0)
        self.assertEqual(fade.alpha, 1.0)
        fade.request(False, 0.0, fade_in=0.0, fade_out=0.0)
        self.assertEqual(fade.alpha, 0.0)


class VisibilitySourceTests(unittest.TestCase):
    def test_hidden_element_has_no_usable_coordinates(self):
        self.assertIsNone(parse_uia_line('{"status":"not_found"}', 1234))
        self.assertIsNone(parse_uia_line('{"status":"unavailable"}', 1234))
        self.assertIsNone(parse_uia_line('{"status":"ok","hwnd":2345,"left":0,"top":0,"right":224,"bottom":243}', 1234))


if __name__ == "__main__":
    unittest.main()
