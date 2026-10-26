"""Faux glass must never rely on translucent PNG in Tk transparent windows."""
import unittest

from rings.config import DEFAULT, normalize
from rings.glass import blend_hex, plan_glass


class FauxGlassTests(unittest.TestCase):
    def test_default_theme_and_external_options(self):
        self.assertFalse(DEFAULT["glass"]["enabled"])
        c = normalize({"glass": {
            "enabled": False, "fillColor": "#ffeedd", "fillOpacity": 33,
            "shadowBlur": 15, "shadowOpacity": 60, "rimOpacity": 20,
            "shadowOffsetY": -4,
        }})
        self.assertFalse(c["glass"]["enabled"])
        self.assertEqual(c["glass"]["fillColor"], "#ffeedd")
        self.assertEqual(c["glass"]["fillOpacity"], 33)
        self.assertEqual(c["glass"]["shadowBlur"], 15)
        self.assertEqual(c["glass"]["shadowOffsetY"], -4)

    def test_invalid_config_is_clamped(self):
        c = normalize({"glass": {
            "fillOpacity": -20, "shadowOpacity": "loud",
            "shadowBlur": 999, "fillColor": "white",
        }})
        self.assertEqual(c["glass"]["fillOpacity"], DEFAULT["glass"]["fillOpacity"])
        self.assertEqual(c["glass"]["shadowBlur"], DEFAULT["glass"]["shadowBlur"])
        self.assertEqual(c["glass"]["fillColor"], DEFAULT["glass"]["fillColor"])

    def test_blend_is_opaque_safe_hex_and_not_black(self):
        self.assertEqual(blend_hex("#ffffff", "#000000", 0.5), "#808080")
        self.assertEqual(blend_hex("#ffffff", "#000000", -1), "#000000")
        self.assertEqual(blend_hex("#ffffff", "#000000", 2), "#ffffff")

    def test_dither_runs_are_opaque_and_inside_the_window(self):
        for scale in (1.0, 1.5, 2.3):
            plan = plan_glass(78, 6, 54, 5, DEFAULT["glass"], scale)
            self.assertGreater(len(plan.runs), 100, f"scale={scale}")
            half_units = plan.pad_units + 39  # outer radius in config units
            for x0, x1, y, color in plan.runs:
                self.assertLessEqual(x0, x1)
                self.assertRegex(color, r"^#[0-9A-Fa-f]{6}$")
                # Never paint the transparent color key itself.
                self.assertNotEqual(color.lower(), "#010203")
                for x in (x0, x1):
                    self.assertLessEqual(abs(x) / scale, half_units + 1.5)
                self.assertLessEqual(abs(y) / scale, half_units + 1.5)
            # A soft stipple halo really extends beyond the ring silhouette.
            self.assertGreater(max(abs(y) for _, _, y, _ in plan.runs) / scale, 44)

    def test_shadow_strength_follows_opacity(self):
        dim = dict(DEFAULT["glass"], shadowOpacity=8)
        strong = dict(DEFAULT["glass"], shadowOpacity=90)

        def shadow_pixels(opts):
            plan = plan_glass(78, 6, 54, 5, opts, 1.0)
            return sum(x1 - x0 + 1 for x0, x1, _, c in plan.runs
                       if c == opts["shadowColor"])

        self.assertGreater(shadow_pixels(strong), shadow_pixels(dim) * 4)

    def test_fill_opacity_controls_frost_density(self):
        faint = dict(DEFAULT["glass"], fillOpacity=20)
        dense = dict(DEFAULT["glass"], fillOpacity=95)

        def fill_pixels(opts):
            plan = plan_glass(78, 6, 54, 5, opts, 1.0)
            return sum(x1 - x0 + 1 for x0, x1, _, c in plan.runs
                       if c == opts["fillColor"])

        self.assertGreater(fill_pixels(dense), fill_pixels(faint) * 2.5)

    def test_planning_is_deterministic(self):
        args = (78, 6, 54, 5, DEFAULT["glass"], 1.5)
        self.assertEqual(plan_glass(*args), plan_glass(*args))

    def test_source_no_photo_image_alpha_dependency(self):
        from pathlib import Path
        ui = (Path(__file__).resolve().parent.parent / "rings" / "ui.py").read_text(encoding="utf-8")
        self.assertNotIn("tk.PhotoImage", ui)
        self.assertNotIn("create_image(", ui)


if __name__ == "__main__":
    unittest.main()
