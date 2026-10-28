"""Cached quota status: transient network failures do not erase valid readings."""
import unittest
from datetime import datetime
from unittest.mock import patch

from rings.quota_status import brief_error, format_refresh_status, retry_delay_ms


class QuotaRefreshStatusTests(unittest.TestCase):
    def test_backoff_has_single_regular_ceiling(self):
        self.assertEqual([retry_delay_ms(x) for x in range(6)],
                         [60000, 15000, 30000, 60000, 60000, 60000])

    def test_success_does_not_look_like_cache_failure(self):
        stamp = datetime(2026, 10, 28, 20, 40, 0).timestamp()
        text = format_refresh_status(
            last_success_wall=stamp, consecutive_failures=0,
        )
        self.assertIn("额度已刷新", text)
        self.assertIn("20:40:00", text)
        self.assertNotIn("缓存", text)

    def test_network_error_stays_quiet_and_marks_cached_value(self):
        stamp = datetime(2026, 10, 28, 20, 40, 0).timestamp()
        error = "Codex 拒绝查询: failed to fetch codex rate limits: error sending request for url (https://chatgpt.com/backend-api/...)"
        text = format_refresh_status(
            last_success_wall=stamp, consecutive_failures=1, error=error,
        )
        self.assertIn("连接失败", text)
        self.assertIn("20:40:00", text)
        self.assertIn("缓存", text)
        self.assertNotIn("https://", text)
        self.assertNotIn("额度已刷新", text)

    def test_error_without_prior_success_never_claims_valid_balance(self):
        text = format_refresh_status(
            last_success_wall=None, consecutive_failures=2,
            error="timeout fetching quotas",
        )
        self.assertIn("查询超时", text)
        self.assertIn("暂无有效数据", text)

    def test_classification_and_demo(self):
        self.assertEqual(brief_error("HTTP 401 Unauthorized"), "额度查询认证失败")
        self.assertEqual(brief_error("HTTP 429"), "额度查询暂时受限")
        self.assertEqual(brief_error("Something unexpected"), "额度查询失败")
        self.assertEqual(format_refresh_status(
            last_success_wall=None, consecutive_failures=1,
            demo=True, error="network error",
        ), "演示数据")


if __name__ == "__main__":
    unittest.main()
