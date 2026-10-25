"""Glass appearance is rendered without screenshot capture or Pillow."""
import struct
import unittest
import zlib

from rings.config import DEFAULT, normalize
from rings.glass import render_glass_png, render_glass_rgba, encode_png


class FauxGlassTests(unittest.TestCase):
    def test_default_glass_is_enabled_and_configurable(self):
        self.assertTrue(DEFAULT["glass"]["enabled"])
        c = normalize({
            "glass": {
                "enabled": False, "fillColor": "#ffeedd", "fillOpacity": 33,
                "shadowBlur": 15, "shadowOpacity": 60, "rimOpacity": 20,
                "shadowOffsetY": -4,
            }
        })
        self.assertFalse(c["glass"]["enabled"])
        self.assertEqual(c["glass"]["fillColor"], "#ffeedd")
        self.assertEqual(c["glass"]["fillOpacity"], 33)
        self.assertEqual(c["glass"]["shadowBlur"], 15)
        self.assertEqual(c["glass"]["shadowOffsetY"], -4)

    def test_invalid_theme_is_rejected_individually(self):
        c = normalize({"glass": {
            "fillOpacity": -20, "shadowOpacity": "loud",
            "shadowBlur": 999, "fillColor": "white",
        }})
        self.assertEqual(c["glass"]["fillOpacity"], DEFAULT["glass"]["fillOpacity"])
        self.assertEqual(c["glass"]["shadowBlur"], DEFAULT["glass"]["shadowBlur"])
        self.assertEqual(c["glass"]["fillColor"], DEFAULT["glass"]["fillColor"])

    def test_shadow_is_soft_and_background_translucent(self):
        size = 116
        rgba = render_glass_rgba(size, 78, DEFAULT["glass"])
        self.assertEqual(len(rgba), size * size * 4)
        def alpha(x, y):
            return rgba[4 * (y * size + x) + 3]
        self.assertEqual(alpha(0, 0), 0)
        self.assertGreater(alpha(58, 58), 100)
        # Shadow softens outward beyond the glass disc (~radius 41).
        self.assertGreater(alpha(107, 58), 0)
        self.assertLess(alpha(107, 58), alpha(98, 58))

    def test_png_is_valid_rgba_with_expected_dimensions(self):
        image = render_glass_png(104, 78, DEFAULT["glass"])
        self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(image[12:16], b"IHDR")
        self.assertEqual(struct.unpack("!II", image[16:24]), (104, 104))
        self.assertEqual(image[24:26], bytes((8, 6)))
        with self.assertRaises(ValueError):
            encode_png(4, 3, b"123")

    def test_disabled_opacity_can_be_zero(self):
        glass = dict(DEFAULT["glass"], shadowOpacity=0, fillOpacity=0,
                     rimOpacity=0, highlightOpacity=0)
        rgba = render_glass_rgba(90, 70, glass)
        self.assertFalse(any(rgba[i + 3] for i in range(0, len(rgba), 4)))


if __name__ == "__main__":
    unittest.main()
