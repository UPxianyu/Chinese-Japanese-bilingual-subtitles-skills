import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import make_bilingual_subs as subs


class SubtitleFormatTests(unittest.TestCase):
    def test_srt_time_rollover(self):
        self.assertEqual(subs.srt_time(59.9996), "00:01:00,000")
        self.assertEqual(subs.srt_time(3599.999), "00:59:59,999")

    def test_ass_uses_both_fonts(self):
        ass = subs.build_ass(
            [[1.2, 4.5, "原文", "译文"]],
            font_ja=42,
            font_zh=44,
            font_ja_name="Meiryo",
            font_zh_name="Microsoft YaHei",
        )
        dialogue = [line for line in ass.splitlines() if line.startswith("Dialogue:")][0]
        self.assertIn(r"\fnMeiryo\fs42", dialogue)
        self.assertIn(r"\fnMicrosoft YaHei\fs44", dialogue)


if __name__ == "__main__":
    unittest.main()
