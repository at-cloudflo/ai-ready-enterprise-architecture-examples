import contextlib
import importlib
import io
import re
import unittest
from pathlib import Path

from series import PARTS

ROOT = Path(__file__).resolve().parents[1]


class PartScriptTests(unittest.TestCase):
    maxDiff = None

    def test_each_part_prints_its_expected_output(self):
        self.assertTrue(PARTS)
        for name, _article, _title in PARTS:
            module = importlib.import_module(f"series.{name}.run")
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                module.main()
            expected = (ROOT / "series" / name / "expected_output.txt").read_text(encoding="utf-8")
            self.assertEqual(expected, buffer.getvalue(), name)

    def test_scripts_are_read_only(self):
        forbidden = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|CREATE)\b|open\([^)]*['\"][wa]|write_text"
                               r"|^\s*(import|from)\s+(urllib|socket|http|requests)\b", re.MULTILINE)
        for path in ROOT.glob("series/part*/run.py"):
            self.assertIsNone(forbidden.search(path.read_text(encoding="utf-8")), path.name)


if __name__ == "__main__":
    unittest.main()
