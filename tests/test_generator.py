import csv
import tempfile
import unittest
from pathlib import Path
from scripts.generate_order_samples import generate

class GeneratorTests(unittest.TestCase):
    def test_repeatability(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/"one",Path(d)/"two"
            generate(a,12,42)
            generate(b,12,42)
            for name in ("customers.csv","orders.csv","order_lines.csv"):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
            with (a/"orders.csv").open(newline="") as f:
                self.assertEqual(12,len(list(csv.DictReader(f))))

    def test_invalid_count(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                generate(Path(d),0)

if __name__=="__main__":
    unittest.main()
