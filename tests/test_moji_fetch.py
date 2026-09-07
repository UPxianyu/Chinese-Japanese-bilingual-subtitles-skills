import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import moji_fetch


class LrcParsingTests(unittest.TestCase):
    def test_parse_lrc_filters_metadata(self):
        text = "[00:00.00]作词: 某人\n[00:01.23]第一句\n[00:04.56][00:05.00]第二句"
        self.assertEqual(moji_fetch.parse_lrc(text), [(1.23, "第一句"), (4.56, "第二句")])

    def test_mojigeci_provider_requires_secret(self):
        old = os.environ.pop("MOJIGECI_SECRET", None)
        try:
            with self.assertRaises(moji_fetch.ProviderConfigError):
                moji_fetch.MojigeciProvider(secret="")
        finally:
            if old is not None:
                os.environ["MOJIGECI_SECRET"] = old

    def test_file_provider_reads_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lyrics.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"name": "测试", "lyrics": "[00:01.00]第一句", "tlyric": "[00:01.00]译文"}, f)
            data = moji_fetch.FileProvider().fetch(path)
            self.assertEqual(data["name"], "测试")


if __name__ == "__main__":
    unittest.main()
