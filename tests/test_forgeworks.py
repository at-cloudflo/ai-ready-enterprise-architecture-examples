import json
import unittest

from forgeworks.data import connect
from forgeworks.semantics import execute, UnmodeledQuestion
from forgeworks.graph import connected_open_lines, connected_exposure, dependency_paths
from forgeworks.governance import validate_ontology, decision_record
from forgeworks.decision import rank_recovery
from forgeworks.discovery import candidates

class ForgeWorksTests(unittest.TestCase):
    def setUp(self):
        self.con = connect()

    def tearDown(self):
        self.con.close()

    def test_fixtures_have_integrity(self):
        self.assertEqual([], self.con.execute("PRAGMA foreign_key_check").fetchall())

    def test_net_sales_correct(self):
        self.assertEqual(7400, execute(self.con, "net_order_value")[0]["value"])

    def test_open_sales_correct(self):
        self.assertEqual(6200, execute(self.con, "open_order_value")[0]["value"])

    def test_shipping_grain_not_multiplied(self):
        self.assertEqual(415, execute(self.con, "shipping_fees")[0]["value"])

    def test_counts(self):
        self.assertEqual(4, execute(self.con, "orders_count")[0]["value"])
        self.assertEqual(3, execute(self.con, "orders_count", order_status="open")[0]["value"])

    def test_group_by_customer(self):
        rows = execute(self.con, "open_order_value", group_by="customer_id")
        self.assertEqual({"C-101": 2900, "C-102": 1650, "C-103": 1650},
                         {r["dimension"]: r["value"] for r in rows})

    def test_refuse_unknown_metric(self):
        with self.assertRaises(UnmodeledQuestion):
            execute(self.con, "total_expected_loss")

    def test_refuse_injected_dimension(self):
        with self.assertRaises(UnmodeledQuestion):
            execute(self.con, "open_order_value", group_by="customer_id; DROP TABLE orders")

    def test_refuse_invalid_status(self):
        with self.assertRaises(UnmodeledQuestion):
            execute(self.con, "orders_count", order_status="cancelled")

    def test_refuse_contradictory_filter(self):
        with self.assertRaises(UnmodeledQuestion):
            execute(self.con, "open_order_value", order_status="fulfilled")

    def test_connected_exposure_is_line_grain(self):
        self.assertEqual(3950, connected_exposure(self.con, "CMP-9"))
        self.assertEqual(["SO-104","SO-105"],
                         [r["order_id"] for r in connected_open_lines(self.con, "CMP-9")])

    def test_paths_are_explainable(self):
        paths = dependency_paths(self.con, "CMP-9")
        self.assertEqual(2, len(paths))
        self.assertTrue(all(path[0]=="SUP-A" and path[1]=="CMP-9" for path in paths))

    def test_ontology_valid(self):
        self.assertEqual(7, len(validate_ontology()["classes"]))

    def test_discovery_does_not_auto_approve(self):
        self.assertTrue(candidates(self.con))
        self.assertTrue(all(x["status"]=="proposed" for x in candidates(self.con)))

    def test_ranking_respects_engineering_approval(self):
        recommendations = rank_recovery()
        self.assertEqual("EXPEDITE", recommendations[0]["action"])
        self.assertNotIn("ALTERNATE_PART", [r["action"] for r in recommendations])
        allowed = rank_recovery(engineering_approved=True)
        self.assertIn("ALTERNATE_PART", [r["action"] for r in allowed])

    def test_recommendation_not_executed(self):
        r = decision_record("SO-104", 1, rank_recovery()[0])
        self.assertEqual("AWAITING_APPROVAL", r["state"])
        self.assertFalse(r["execution_allowed"])
        self.assertFalse(r["executed"])

if __name__ == "__main__":
    unittest.main()
