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

    def test_small_center_disc_and_subtle_shadow(self):
        plan = plan_glass(78, 54, 5, DEFAULT["glass"], 1)
        self.assertLess(plan.disc_radius, 25)
        self.assertGreater(plan.disc_radius, 18)
        self.assertEqual(len(plan.shadow_colors), 3)
        self.assertLess(max(plan.shadow_radii), 49)
        # The old PNG rendered as a black annulus on the user's Windows Tk.
        # The new halo is entirely light, opaque Tk colors.
        for color in plan.shadow_colors:
            self.assertRegex(color, r"^#[0-9a-f]{6}$")
            self.assertGreater(int(color[1:3], 16), 170)
            self.assertGreater(int(color[3:5], 16), 160)
            self.assertGreater(int(color[5:7], 16), 180)

    def test_shadow_offset_is_capped_without_dark_halo(self):
        opts = dict(DEFAULT["glass"], shadowBlur=24, shadowSpread=20,
                    shadowOffsetY=20, shadowOpacity=100)
        plan = plan_glass(78, 54, 5, opts)
        self.assertLess(max(plan.shadow_radii), 50)
        self.assertEqual(plan.shadow_offset[1], 2.0)

    def test_source_no_photo_image_alpha_dependency(self):
        from pathlib import Path
        ui = (Path(__file__).resolve().parent.parent / "rings" / "ui.py").read_text(encoding="utf-8")
        self.assertNotIn("tk.PhotoImage", ui)
        self.assertNotIn("create_image(", ui)


if __name__ == "__main__":
    unittest.main()
