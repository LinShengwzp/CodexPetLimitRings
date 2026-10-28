"""Reset-aware local statistics, Codex JSONL token/model accounting."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from rings.core import Quota, Quotas
from rings.history import (
    connect, quota_history, quota_summary, store_quotas, token_summary,
)
from rings.sessions import import_sessions, parse_session_lines, UNKNOWN
from rings.stats_ui import points_for_plot


class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbfile = Path(self.temp.name) / "local.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def _sample(self, when, five, weekly, reset5=20000, reset7=80000):
        store_quotas(
            Quotas(Quota(five, reset5), Quota(weekly, reset7)),
            ts=when, path=self.dbfile,
        )

    def test_observed_consumption_without_reset_inflation(self):
        self._sample(1000, 98, 94)
        self._sample(1100, 90, 92)
        self._sample(1200, 100, 91, reset5=30000)  # 5-hour reset!
        self._sample(1300, 96, 90, reset5=30000)
        data = quota_summary(1000, until=1300, path=self.dbfile)
        self.assertEqual(data["5h"]["observed_spent_pp"], 12)
        self.assertEqual(data["7d"]["observed_spent_pp"], 4)
        self.assertEqual(data["5h"]["last_remaining"], 96)

    def test_no_history_guess_and_window_baseline(self):
        self._sample(1000, 90, 90)
        self._sample(1100, 88, 89)
        self._sample(1200, 84, 89)
        rows = quota_history("5h", 1050, until=1200, path=self.dbfile)
        self.assertEqual(sum(r["observed_spent_pp"] for r in rows), 6)
        self.assertEqual(len(rows), 2)
        self.assertEqual(quota_summary(1, until=500, path=self.dbfile)["5h"]["sample_count"], 0)
        with self.assertRaises(ValueError):
            quota_history("not-window", 0, path=self.dbfile)

    def test_missing_quota_is_skipped(self):
        n = store_quotas(
            Quotas(Quota(None, None), Quota(64, 4000)),
            ts=500, path=self.dbfile,
        )
        self.assertEqual(n, 1)
        self.assertEqual(len(quota_history("5h", 0, until=500, path=self.dbfile)), 0)

    def test_reset_breaks_plot_segments(self):
        items = [
            {"ts": 1000, "remaining": 80, "resets_at": 2000},
            {"ts": 1100, "remaining": 70, "resets_at": 2000},
            {"ts": 1200, "remaining": 100, "resets_at": 3000},
            {"ts": 1300, "remaining": 96, "resets_at": 3000},
        ]
        segments = points_for_plot(items, 500, 30, 450, 20, 150, 900, 1500)
        self.assertEqual([len(s) for s in segments], [2, 2])
        self.assertGreater(segments[0][-1][1], segments[1][0][1])

    def test_token_event_cumulative_dedup_model_switch(self):
        def line(ts, kind, payload):
            return json.dumps({"timestamp": f"2026-10-28T10:00:{ts:02d}Z",
                               "type": kind, "payload": payload}) + "\n"
        def usage(i, o, c=0):
            return {"input_tokens": i, "output_tokens": o,
                    "cached_input_tokens": c, "reasoning_output_tokens": 0}
        lines = [
            line(0, "session_meta", {"cwd": "secret-dir", "base_instructions": "secret!"}),
            line(1, "turn_context", {"model": "gpt-6-low"}),
            line(2, "event_msg", {"type": "token_count", "info": {
                "total_token_usage": usage(500, 20, 400),
                "last_token_usage": usage(500, 20, 400),
            }}),
            line(3, "event_msg", {"type": "token_count", "info": {
                "total_token_usage": usage(500, 20, 400),
                "last_token_usage": usage(500, 20, 400),
            }}),
            line(4, "turn_context", {"model": "gpt-6-high"}),
            line(5, "event_msg", {"type": "token_count", "info": {
                "total_token_usage": usage(800, 30, 650),
                "last_token_usage": usage(300, 10, 250),
            }}),
        ]
        root = Path(self.temp.name) / "sessions" / "2026" / "10" / "28"
        root.mkdir(parents=True)
        file = root / "rollout-test.jsonl"
        file.write_text("".join(lines), encoding="utf-8")
        meta = import_sessions(root=root.parent.parent.parent, db_path=self.dbfile, days=90)
        self.assertEqual(meta["new_events"], 2)
        now = int(datetime(2026, 10, 28, 11, 0, tzinfo=timezone.utc).timestamp())
        result = token_summary(now-3600, until=now, path=self.dbfile)
        self.assertEqual(result["total_tokens"], 830)
        models = {row["model"]: row for row in result["models"]}
        self.assertEqual(models["gpt-6-low"]["input"], 500)
        self.assertEqual(models["gpt-6-high"]["output"], 10)
        # Re-import must not double-count cumulative token snapshots.
        again = import_sessions(root=root.parent.parent.parent, db_path=self.dbfile, days=90)
        self.assertEqual(again["new_events"], 0)
        self.assertEqual(token_summary(now-3600, until=now, path=self.dbfile)["total_tokens"], 830)
        self.assertNotIn("secret", repr(result))

    def test_append_only_import_preserves_model(self):
        folder = Path(self.temp.name) / "sessions"
        folder.mkdir()
        file = folder / "rollout-test.jsonl"
        def entry(t, payload):
            return json.dumps({"timestamp":"2026-10-28T10:00:00Z","type":t,"payload":payload}) + "\n"
        with file.open("w", encoding="utf-8") as w:
            w.write(entry("turn_context", {"model":"gpt-6-low"}))
            w.write(entry("event_msg", {"type":"token_count","info":{
                "total_token_usage":{"input_tokens": 100, "output_tokens": 10},
            }}))
        import_sessions(root=folder, db_path=self.dbfile)
        with file.open("a", encoding="utf-8") as w:
            w.write(entry("event_msg", {"type":"token_count","info":{
                "total_token_usage":{"input_tokens": 150, "output_tokens": 20},
            }}))
        result = import_sessions(root=folder, db_path=self.dbfile)
        self.assertEqual(result["new_events"], 1)
        now = int(datetime(2026, 10, 28, 11, tzinfo=timezone.utc).timestamp())
        models = token_summary(now-3600, until=now, path=self.dbfile)["models"]
        self.assertEqual(models[0]["input"], 150)
        self.assertEqual(models[0]["output"], 20)
        self.assertEqual(models[0]["model"], "gpt-6-low")


if __name__ == "__main__":
    unittest.main()
