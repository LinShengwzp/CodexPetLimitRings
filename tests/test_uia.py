import json
import unittest

from rings.core import Rect
from rings.uia import parse_uia_line


class UIAMascotTests(unittest.TestCase):
    def test_read_exact_pet_image_on_secondary_screen(self):
        msg = {
            "status": "ok", "hwnd": 134082,
            "left": 3617, "top": 286, "right": 3841, "bottom": 529,
            "source": "uia-image",
        }
        self.assertEqual(
            parse_uia_line(json.dumps(msg), 134082),
            Rect(3617, 286, 3841, 529),
        )

    def test_read_exact_pet_image_on_main_screen(self):
        msg = {
            "status": "ok", "hwnd": 134082,
            "left": 1594, "top": 429, "right": 1818, "bottom": 672,
        }
        self.assertEqual(parse_uia_line(json.dumps(msg), 134082),
                         Rect(1594, 429, 1818, 672))

    def test_reject_wrong_hwnd_invalid_size_and_status(self):
        base = {"status": "ok", "hwnd": 134082, "left": 100,
                "top": 100, "right": 324, "bottom": 343}
        self.assertIsNone(parse_uia_line(json.dumps(base), 17))
        self.assertIsNone(parse_uia_line(json.dumps({**base, "status": "not_found"}), 134082))
        self.assertIsNone(parse_uia_line(json.dumps({**base, "right": 5000}), 134082))
        self.assertIsNone(parse_uia_line(json.dumps({**base, "top": True}), 134082))
        self.assertIsNone(parse_uia_line("not JSON", 134082))


if __name__ == "__main__":
    unittest.main()
