"""No Windows or Tk required: rate limiting and output safety of position traces."""
import json
import logging
import tempfile
import unittest
from pathlib import Path

from rings.position_trace import PositionTracer, make_position_tracer


class FakeLogger:
    def __init__(self):
        self.lines = []

    def info(self, text):
        self.lines.append(json.loads(text))


class TraceTests(unittest.TestCase):
    def test_state_transition_and_rate_limit(self):
        sink = FakeLogger()
        tracer = PositionTracer(logger=sink, interval=0.5)
        a = {"visible": True, "reason": "visible", "pet_hwnd": 42,
             "position_source": "manually-calibrated",
             "host_rect": [2560, 0, 3464, 1080],
             "ring_target_rect": [3230, 400, 3320, 490]}
        self.assertTrue(tracer.emit("sample", a, now=10.0))
        self.assertFalse(tracer.emit("sample", a, now=10.1))
        self.assertTrue(tracer.emit("sample", a, now=10.51))
        b = dict(a, reason="pet_drag", visible=False)
        self.assertTrue(tracer.emit("sample", b, now=10.60))
        self.assertTrue(tracer.emit("calibration_end", b, force=True, now=10.61))
        self.assertEqual(len(sink.lines), 4)
        self.assertEqual(sink.lines[2]["reason"], "pet_drag")
        self.assertEqual(sink.lines[3]["event"], "calibration_end")
        self.assertRegex(sink.lines[0]["at"], r"\d{4}-\d{2}-\d{2}T")

    def test_rolling_file_records_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            tracer = make_position_tracer(directory=Path(directory), console=False)
            tracer.emit("sample", {"host_rect": [1, 2, 3, 4],
                                   "ring_target_rect": [5, 6, 7, 8]}, force=True)
            for handler in tracer.logger.handlers[:]:
                handler.flush()
                tracer.logger.removeHandler(handler)
                handler.close()
            payload = json.loads(tracer.file_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["host_rect"], [1, 2, 3, 4])
            self.assertEqual(payload["ring_target_rect"], [5, 6, 7, 8])


if __name__ == "__main__":
    unittest.main()
