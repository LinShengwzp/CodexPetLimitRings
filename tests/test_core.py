import unittest

from rings.core import Quota, Quotas, Rect, follow_position, parse_quotas, explain


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
        self.assertEqual(follow_position(Rect(650, 100, 750, 300), 120, 70, area), (522, 165))
        self.assertEqual(follow_position(Rect(150, 100, 250, 300), 120, 70, area), (258, 165))
        self.assertEqual(follow_position(Rect(650, 100, 750, 300), 120, 70, area, 900, -500), (680, 0))

    def test_negative_monitor_coordinates(self):
        area = Rect(-1920, 0, 0, 1080)
        pet = Rect(-300, 400, -100, 650)
        x, y = follow_position(pet, 130, 75, area)
        self.assertTrue(-1920 <= x <= -130)
        self.assertTrue(0 <= y <= 1005)


if __name__ == "__main__":
    unittest.main()
