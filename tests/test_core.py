import unittest

from rings.core import PetMotionTracker, Quota, Quotas, Rect, follow_position, parse_quotas, explain
from rings.state import parse_pet_placement
from rings.pet import host_score, sprite_from_host


class QuotaTests(unittest.TestCase):
    def test_both_windows_any_order(self):
        data = {"rateLimitsByLimitId": {"codex": {
            "primary": {"windowDurationMins": 10080, "usedPercent": 7, "resetsAt": 1793000000},
            "secondary": {"windowDurationMins": 300, "usedPercent": 47, "resetsAt": 1792900000},
        }}}
        q = parse_quotas(data)
        self.assertEqual(q.five_hour.remaining, 53)
        self.assertEqual(q.weekly.remaining, 93)
        self.assertEqual(q.five_hour.resets_at, 1792900000)

    def test_weekly_only_does_not_get_mislabelled_as_5h(self):
        data = {"rateLimits": {
            "primary": {"windowDurationMins": 10080, "usedPercent": 25}
        }}
        quotas = parse_quotas(data)
        self.assertIsNone(quotas.five_hour.remaining)
        self.assertEqual(quotas.weekly.remaining, 75)

    def test_thirty_day_is_not_weekly(self):
        data = {"rateLimits": {
            "primary": {"windowDurationMins": 43200, "usedPercent": 10}
        }}
        quotas = parse_quotas(data)
        self.assertIsNone(quotas.five_hour.remaining)
        self.assertIsNone(quotas.weekly.remaining)

    def test_invalid_out_of_range_does_not_become_zero(self):
        data = {"rateLimits": {
            "primary": {"windowDurationMins": 300, "usedPercent": 110}
        }}
        self.assertIsNone(parse_quotas(data).five_hour.remaining)

    def test_missing_or_non_object_response_fails(self):
        for payload in (None, [], {}, {"rateLimits": None}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_quotas(payload)

    def test_zero_and_full(self):
        data = {"rateLimits": {
            "primary": {"windowDurationMins": 300, "usedPercent": 0},
            "secondary": {"windowDurationMins": 10080, "usedPercent": 100},
        }}
        q = parse_quotas(data)
        self.assertEqual(explain(q)["five_hour"]["remaining_percent"], 100)
        self.assertEqual(q.weekly.remaining, 0)

    def test_relative_position_flips_and_clamps(self):
        area = Rect(0, 0, 800, 600)
        self.assertEqual(follow_position(Rect(650, 100, 750, 300), 120, 70, area), (520, 124))
        self.assertEqual(follow_position(Rect(150, 100, 250, 300), 120, 70, area), (20, 124))
        self.assertEqual(follow_position(Rect(650, 100, 750, 300), 120, 70, area, 900, -500), (680, 0))


    def test_real_codex_sprite_not_huge_host(self):
        # The user observed this 888x1080 host: its full rect is NOT the pet.
        state = {
            "electron-avatar-overlay-open": True,
            "electron-avatar-overlay-bounds": {
                "x": 3632, "y": 0,
                "displayId": "secondary",
                "byDisplayId": {"secondary": {
                    "width": 848, "height": 1080,
                    "mascot": {"left": 648, "top": 764, "width": 146, "height": 178}
                }}
            }
        }
        placement = parse_pet_placement(state)
        self.assertIsNotNone(placement)
        self.assertTrue(placement.has_mascot_geometry)
        self.assertEqual(placement.mascot, Rect(4280, 764, 4426, 942))
        host = Rect(3632, 0, 4480, 1080)
        self.assertIsNotNone(host_score(host, 0x00080080, placement))
        sprite, precise, source = sprite_from_host(host, placement)
        self.assertTrue(precise)
        self.assertEqual(sprite, placement.mascot)
        work = Rect(2560, 0, 4480, 1040)
        x, y = follow_position(sprite, 86, 86, work)
        self.assertEqual((x, y), (4184, 785))
        self.assertLess(x, sprite.left)

    def test_main_display_wide_host_is_detected(self):
        state = {
            "electron-avatar-overlay-open": True,
            "electron-avatar-overlay-bounds": {
                "x": 100, "y": 100, "width": 260, "height": 320,
                "mascot": {"left": 40, "top": 50, "width": 135, "height": 140}
            },
        }
        placement = parse_pet_placement(state)
        self.assertEqual(placement.mascot, Rect(140, 150, 275, 290))
        # Unlike V1, a 1920px wide transparent host must not be discarded.
        host = Rect(0, 0, 1920, 1080)
        self.assertIsNotNone(host_score(host, 0x00080000, placement))
        sprite, precise, _ = sprite_from_host(host, placement)
        self.assertTrue(precise)
        self.assertEqual(sprite, placement.mascot)

    def test_state_closed_and_missing_mascot(self):
        self.assertIsNone(parse_pet_placement({"electron-avatar-overlay-open": False}))
        data = {"electron-avatar-overlay-open": True,
                "electron-avatar-overlay-bounds": {"x": 120, "y": 310, "width": 240, "height": 200}}
        p = parse_pet_placement(data)
        self.assertIsNotNone(p)
        self.assertFalse(p.has_mascot_geometry)
        self.assertEqual(p.mascot, Rect(120, 310, 248, 449))
        self.assertIsNone(host_score(Rect(0, 0, 1920, 1080), 0, p))  # opaque main app excluded

    def test_hide_until_motion_settles(self):
        watch = PetMotionTracker(settle_seconds=0.55)
        rect = Rect(2560, 0, 3448, 1080)
        moved = Rect(2580, 0, 3468, 1080)
        self.assertFalse(watch.should_show(rect, 42, 1.0))
        self.assertFalse(watch.should_show(rect, 42, 1.3))
        self.assertTrue(watch.should_show(rect, 42, 1.56))
        self.assertFalse(watch.should_show(moved, 42, 1.60))
        self.assertFalse(watch.should_show(moved, 42, 1.95))
        self.assertTrue(watch.should_show(moved, 42, 2.18))
        # A newly opened native HWND must not inherit "settled".
        self.assertFalse(watch.should_show(moved, 43, 2.2))
        watch.reset()
        self.assertFalse(watch.should_show(moved, 43, 2.3))

    def test_negative_monitor_coordinates(self):
        area = Rect(-1920, 0, 0, 1080)
        pet = Rect(-300, 400, -100, 650)
        x, y = follow_position(pet, 130, 75, area)
        self.assertTrue(-1920 <= x <= -130)
        self.assertTrue(0 <= y <= 1005)


if __name__ == "__main__":
    unittest.main()
