import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import build_segments
import make_bilingual_subs as subs


class ScriptHelperTests(unittest.TestCase):
    def test_escape_ass_text(self):
        self.assertEqual(subs.escape_ass_text(r"a{Nb"), r"a\{Nb")
        self.assertEqual(subs.escape_ass_text(r"a\Nb"), r"a\\Nb")

    def test_validate_manifest(self):
        valid = [{"key": "01", "name": "测试", "start": 0, "end": 5}]
        self.assertEqual(build_segments.validate_manifest(valid), valid)
        with self.assertRaises(ValueError):
            build_segments.validate_manifest([{"key": "01", "name": "测试", "start": 5, "end": 5}])

    def test_validate_cues(self):
        valid = {"01": [[0, 2, "原文", "译文"]]}
        self.assertEqual(build_segments.validate_cues(valid), valid)
        with self.assertRaises(ValueError):
            build_segments.validate_cues({"01": [[2, 0, "原文", "译文"]]})


if __name__ == "__main__":
    unittest.main()
