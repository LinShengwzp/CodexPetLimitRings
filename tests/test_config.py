import json
import tempfile
import unittest
from pathlib import Path

from rings.calibration import create_anchor, move_anchor, sprite_from_anchor
from rings.config import DEFAULT, ConfigWatcher, load_config, normalize
from rings.core import Rect, follow_position
from rings.state import inspect_state_file, parse_pet_placement


class ConfigTests(unittest.TestCase):
    def test_external_theme_sizes_colors_font_and_background(self):
        conf = normalize({
            "rings": {
                "outer": {"diameter": 110, "stroke": 9, "color": "#AF6DAA"},
                "inner": {"diameter": 66, "stroke": 5, "color": "#20b8ec"},
                "trackColor": "#eeeeee",
            },
            "background": {"enabled": True, "color": "#fefefe", "padding": 10},
            "text": {"fontFamily": "Microsoft YaHei UI", "fontSize": 14, "bold": False,
                     "color": "#654321", "separator": "|", "showPercentSign": True},
            "position": {"side": "right", "gap": 15, "offsetY": -90, "verticalRatio": 0.7},
        })
        self.assertEqual(conf["rings"]["outer"]["diameter"], 110)
        self.assertEqual(conf["rings"]["inner"]["diameter"], 66)
        self.assertEqual(conf["rings"]["outer"]["color"], "#AF6DAA")
        self.assertTrue(conf["background"]["enabled"])
        self.assertEqual(conf["text"]["fontFamily"], "Microsoft YaHei UI")
        self.assertEqual(conf["position"]["offsetY"], -90)

    def test_invalid_properties_are_safe(self):
        conf = normalize({
            "rings": {"outer": {"diameter": 90000, "color": "red", "stroke": -10},
                      "inner": {"diameter": 300, "stroke": 20}},
            "background": {"enabled": "yes", "color": "rgba(1,1,1,.2)"},
            "text": {"fontSize": 5000},
            "position": {"side": "north", "verticalRatio": -1},
        })
        self.assertEqual(conf["rings"]["outer"], DEFAULT["rings"]["outer"])
        self.assertLess(conf["rings"]["inner"]["diameter"], conf["rings"]["outer"]["diameter"])
        self.assertFalse(conf["background"]["enabled"])
        self.assertEqual(conf["text"]["fontSize"], DEFAULT["text"]["fontSize"])
        self.assertEqual(conf["position"]["verticalRatio"], 0.12)

    def test_fallback_when_json_is_corrupt(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "config.json"
            file.write_text("{invalid", encoding="utf-8")
            self.assertEqual(load_config(file), DEFAULT)
            file.write_text(json.dumps({"text": {"fontSize": 15}}), encoding="utf-8")
            watch = ConfigWatcher(file)
            self.assertTrue(watch.refresh())
            self.assertEqual(watch.value["text"]["fontSize"], 15)
            file.write_text(json.dumps({"text": {"fontSize": 19}}), encoding="utf-8")
            self.assertTrue(watch.refresh())
            self.assertEqual(watch.value["text"]["fontSize"], 19)


class CalibrationTests(unittest.TestCase):
    def test_calibrate_on_full_height_host_and_follow_drag(self):
        host = Rect(2560, 0, 3464, 1080)
        anchor = create_anchor(host, 3340, 430)   # Pet is in the upper half
        rect = sprite_from_anchor(host, anchor)
        self.assertEqual((rect.left + rect.right) // 2, 3340)
        self.assertEqual((rect.top + rect.bottom) // 2, 430)
        anchor = move_anchor(anchor, 100, 400)
        rect = sprite_from_anchor(host, anchor)
        self.assertEqual((rect.left + rect.right) // 2, 3440)
        self.assertEqual((rect.top + rect.bottom) // 2, 830)

    def test_monitor_side_and_gap(self):
        area = Rect(2560, 0, 4480, 1040)
        pet = Rect(4240, 500, 4390, 660)
        x, y = follow_position(pet, 98, 98, area, side="left", gap=20, vertical_ratio=0.5)
        self.assertEqual((x, y), (4122, 580))
        x, y = follow_position(pet, 98, 98, area, side="right", gap=20, vertical_ratio=0.5)
        self.assertEqual((x, y), (4122, 580))  # right side would go off screen

    def test_missing_avatar_state_reports_safe_details(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "codex.json"
            result = inspect_state_file(file)
            self.assertFalse(result["exists"])
            file.write_text(json.dumps({
                "electron-avatar-overlay-open": True,
                "electron-avatar-overlay-bounds": {"x": 12, "y": 10},
                "secret-credential-do-not-print": "secret"
            }), encoding="utf-8")
            result = inspect_state_file(file)
            self.assertTrue(result["exists"])
            self.assertTrue(result["readable"])
            self.assertTrue(result["bounds_present"])
            self.assertNotIn("secret", repr(result))


if __name__ == "__main__":
    unittest.main()
