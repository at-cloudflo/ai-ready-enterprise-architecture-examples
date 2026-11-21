import unittest
from forgeworks.outcomes import summarize

class OutcomeTests(unittest.TestCase):
    def test_observed_synthetic_outcomes(self):
        result = summarize()
        self.assertEqual(4, result["observations"])
        self.assertEqual(3, result["on_time_deliveries"])
        self.assertEqual(340, result["actual_recovery_cost_usd"])
        self.assertEqual(4, result["total_delay_days"])
        self.assertIn("cannot establish", result["caveat"])

if __name__ == "__main__":
    unittest.main()
