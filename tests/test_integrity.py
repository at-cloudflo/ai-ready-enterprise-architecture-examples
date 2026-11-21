import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from forgeworks import demo, outcomes, pitfalls, semantics
from forgeworks.data import connect
from forgeworks.decision import rank_recovery
from forgeworks.discovery import evidence
from forgeworks.governance import validate_mappings, validate_ontology
from forgeworks.graph import connected_exposure, dependency_paths
from forgeworks.screening import operational_screen
from forgeworks.semantics import (ALL_CUSTOMERS, ANALYST, Caller, NotAuthorized, UnmodeledQuestion,
                                  execute, execute_plan)

ROOT = Path(__file__).resolve().parents[1]
FINANCE = frozenset({"net_order_value", "open_order_value", "orders_count", "shipping_fees"})


class Base(unittest.TestCase):
    def setUp(self):
        self.con = connect()
        self.addCleanup(self.con.close)


class GrainAndKeyTests(Base):
    def test_duplicate_compound_key_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("INSERT INTO order_lines VALUES ('SO-104', 1, 'VAL-2', 1, 600, 0)")

    def test_line_id_alone_is_not_a_key(self):
        count = self.con.execute("SELECT COUNT(*) FROM order_lines WHERE line_id = 1").fetchone()[0]
        self.assertEqual(4, count)

    def test_orphan_line_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("INSERT INTO order_lines VALUES ('SO-999', 1, 'VAL-2', 1, 600, 0)")

    def test_discount_cannot_exceed_gross_or_go_negative(self):
        for discount in (601, -1):
            with self.assertRaises(sqlite3.IntegrityError):
                self.con.execute(
                    "INSERT INTO order_lines VALUES ('SO-105', 2, 'VAL-2', 1, 600, ?)", (discount,))

    def test_fan_out_join_is_wrong_by_exactly_one_repeated_fee(self):
        certified = execute(self.con, "shipping_fees")[0]["value"]
        naive = pitfalls.naive_shipping_fees(self.con)
        self.assertEqual(415, certified)
        self.assertEqual(535, naive)
        self.assertEqual(120, naive - certified)
        by_customer = {r["customer_id"]: r for r in pitfalls.naive_fanout_by_customer(self.con)}
        self.assertEqual(240, by_customer["C-101"]["shipping_fees_wrong"])
        self.assertEqual(2, by_customer["C-101"]["orders_count_wrong"])
        self.assertEqual(7400, sum(r["net_order_value"] for r in by_customer.values()))

    def test_three_exposure_numbers_are_distinct(self):
        self.assertEqual(3950, connected_exposure(self.con, "CMP-9"))
        self.assertEqual(4550, pitfalls.whole_order_exposure(self.con, "CMP-9"))
        self.assertEqual(5150, pitfalls.status_blind_exposure(self.con, "CMP-9"))
        self.assertEqual(6200, execute(self.con, "open_order_value")[0]["value"])

    def test_line_formula_has_one_meaning_in_two_modules(self):
        certified = {r["dimension"]: r["value"] for r in execute(self.con, "net_order_value", "order_id")}
        from forgeworks.graph import connected_open_lines
        by_order: dict = {}
        for component in ("CMP-9", "CMP-4", "CMP-2"):
            for line in connected_open_lines(self.con, component):
                by_order.setdefault(line["order_id"], {})[line["line_id"]] = line["connected_line_value"]
        for order_id, lines in by_order.items():
            self.assertEqual(certified[order_id], sum(lines.values()), order_id)

    def test_paths_keep_the_order_line(self):
        self.assertEqual(
            [["SUP-A", "CMP-9", "PMP-7", "SO-104#1", "SO-104", "C-101"],
             ["SUP-A", "CMP-9", "PMP-8", "SO-105#1", "SO-105", "C-102"]],
            dependency_paths(self.con, "CMP-9"))


class ModelDriftTests(Base):
    def test_catalog_and_templates_name_the_same_things(self):
        self.assertEqual(set(semantics.CATALOG["metrics"]), set(semantics.METRIC_SOURCES))
        self.assertEqual(set(semantics.CATALOG["dimensions"]), set(semantics.DIMENSIONS))
        self.assertEqual({"metrics", "group_by", "filters"}, set(semantics.PLAN_FIELDS))

    def test_every_template_exposes_orders_for_scope_and_filters(self):
        for name, (source, _measure, _filter) in semantics.METRIC_SOURCES.items():
            self.assertRegex(source, r"\borders o\b", name)

    def test_models_are_valid_json_with_versions(self):
        for name in ("ontology.json", "semantic_model.json", "glossary.json"):
            json.loads((ROOT / "models" / name).read_text(encoding="utf-8"))
        self.assertEqual("1.1", semantics.CATALOG["version"])
        self.assertEqual("1.1", validate_ontology()["version"])

    def test_ontology_rejects_invalid_candidates(self):
        good = validate_ontology()
        def variant(**change):
            model = json.loads(json.dumps(good))
            model["relationships"][0].update(change)
            return model
        for bad in (variant(to="Warehouse"), variant(status="proposed"), variant(impact_direction="sideways")):
            with self.assertRaises(ValueError):
                validate_ontology(model=bad)
        duplicate = json.loads(json.dumps(good))
        duplicate["relationships"].append(dict(duplicate["relationships"][0]))
        with self.assertRaises(ValueError):
            validate_ontology(model=duplicate)
        keyless = json.loads(json.dumps(good))
        del keyless["keys"]["Shipment"]
        with self.assertRaises(ValueError):
            validate_ontology(model=keyless)

    def test_ontology_mappings_exist_in_schema(self):
        self.assertEqual(13, len(validate_mappings(self.con)))
        broken = json.loads(json.dumps(validate_ontology()))
        broken["relationships"][0]["source"] = "components.vendor_id"
        with self.assertRaises(ValueError):
            validate_mappings(self.con, broken)
        broken["relationships"][0]["source"] = "purchase_orders.supplier_id"
        with self.assertRaises(ValueError):
            validate_mappings(self.con, broken)

    def test_ontology_diagram_matches_model(self):
        import re
        figure = ROOT / "series" / "part03_ontology" / "figures" / "03-ontology.mmd"
        if not figure.exists():
            self.skipTest("figure not included in this checkout (public companion code)")
        text = figure.read_text(encoding="utf-8")
        drawn = set(re.findall(r"^\s*(\w+)\s*-->\|\s*(\w+)[^|]*\|\s*(\w+)", text, re.MULTILINE))
        modelled = {(r["from"], r["predicate"], r["to"]) for r in validate_ontology()["relationships"]}
        self.assertEqual(modelled, drawn)


class PlanTests(Base):
    PLAN = {"metrics": ["open_order_value", "shipping_fees", "orders_count"],
            "group_by": "customer_id", "filters": {"order_status": "open"}}

    def test_plan_merges_three_grains_without_fan_out(self):
        answer = execute_plan(self.con, self.PLAN, ANALYST)
        self.assertEqual(
            [{"customer_id": "C-101", "open_order_value": 2900, "shipping_fees": 120, "orders_count": 1},
             {"customer_id": "C-102", "open_order_value": 1650, "shipping_fees": 75, "orders_count": 1},
             {"customer_id": "C-103", "open_order_value": 1650, "shipping_fees": 140, "orders_count": 1}],
            answer["rows"])
        self.assertEqual({"open_order_value": "order_id,line_id", "shipping_fees": "shipment_id",
                          "orders_count": "order_id"}, answer["base_grains"])
        self.assertEqual("1.1", answer["semantic_model_version"])

    def test_ungrouped_plan_returns_certified_totals(self):
        answer = execute_plan(self.con, {"metrics": ["net_order_value", "open_order_value",
                                                     "orders_count", "shipping_fees"]}, ANALYST)
        self.assertEqual([{"net_order_value": 7400, "open_order_value": 6200,
                           "orders_count": 4, "shipping_fees": 415}], answer["rows"])

    def test_plan_refuses_anything_outside_the_contract(self):
        refused = [
            "SELECT * FROM orders",
            {},
            {"metrics": []},
            {"metrics": ["expected_loss"]},
            {"metrics": ["open_order_value", "open_order_value"]},
            {"metrics": ["open_order_value"], "sql": "SELECT 1"},
            {"metrics": ["open_order_value"], "context": {"component_id": "CMP-9"}},
            {"metrics": ["open_order_value"], "group_by": ["customer_id"]},
            {"metrics": ["open_order_value"], "group_by": "product_id"},
            {"metrics": ["open_order_value"], "filters": {"customer_id": "C-102"}},
            {"metrics": ["open_order_value"], "filters": {"order_status": "cancelled"}},
            {"metrics": ["open_order_value"], "filters": {"order_status": "fulfilled"}},
            {"metrics": ["open_order_value"], "filters": "order_status='open' OR 1=1"},
        ]
        for plan in refused:
            with self.assertRaises(UnmodeledQuestion, msg=repr(plan)):
                execute_plan(self.con, plan, ANALYST)

    def test_caller_scope_limits_rows_and_cannot_be_widened(self):
        account_manager = Caller("am-northstar", FINANCE, frozenset({"C-101"}))
        answer = execute_plan(self.con, self.PLAN, account_manager)
        self.assertEqual(["C-101"], [row["customer_id"] for row in answer["rows"]])
        self.assertEqual(["C-101"], answer["customer_scope"])
        total = execute_plan(self.con, {"metrics": ["open_order_value"]}, account_manager)
        self.assertEqual(2900, total["rows"][0]["open_order_value"])

    def test_caller_without_grant_or_scope_is_refused(self):
        planner = Caller("planner", frozenset({"orders_count"}), ALL_CUSTOMERS)
        with self.assertRaises(NotAuthorized):
            execute_plan(self.con, self.PLAN, planner)
        nobody = Caller("nobody", FINANCE, frozenset())
        with self.assertRaises(NotAuthorized):
            execute_plan(self.con, {"metrics": ["orders_count"]}, nobody)

    def test_governed_tools_deny_by_default(self):
        from forgeworks.graph import dependency_lookup
        for caller in (None, Caller("no-scope", FINANCE, None), Caller("empty", FINANCE, frozenset()),
                       Caller("string", FINANCE, "C-101")):
            with self.assertRaises(NotAuthorized, msg=repr(caller)):
                execute_plan(self.con, {"metrics": ["orders_count"]}, caller)
            with self.assertRaises(NotAuthorized, msg=repr(caller)):
                dependency_lookup(self.con, "CMP-9", caller)
        with self.assertRaises(NotAuthorized):
            dependency_lookup(self.con, "CMP-9", Caller("ops", frozenset({"orders_count"}), ALL_CUSTOMERS))

    def test_governed_dependency_lookup_is_scoped(self):
        from forgeworks.graph import dependency_lookup
        manager = Caller("am-northstar", FINANCE, frozenset({"C-101"}))
        found = dependency_lookup(self.con, "CMP-9", manager)
        self.assertEqual([("SO-104", 1)], [(l["order_id"], l["line_id"]) for l in found["lines"]])
        self.assertEqual((2300, ["C-101"]), (found["connected_exposure_usd"], found["customer_scope"]))
        self.assertEqual(3950, dependency_lookup(self.con, "CMP-9", ANALYST)["connected_exposure_usd"])

    def test_answer_echoes_filters_so_mixed_populations_are_visible(self):
        plan = {"metrics": ["open_order_value", "orders_count"], "group_by": "customer_id"}
        answer = execute_plan(self.con, plan, ANALYST)
        c103 = [r for r in answer["rows"] if r["customer_id"] == "C-103"][0]
        self.assertEqual((1650, 2), (c103["open_order_value"], c103["orders_count"]))
        self.assertEqual({"order_status": "any"}, answer["filters"])
        self.assertEqual({"open_order_value": "order_status = 'open'", "orders_count": None},
                         answer["certified_filters"])
        filtered = execute_plan(self.con, {**plan, "filters": {"order_status": "open"}}, ANALYST)
        self.assertEqual(1, [r for r in filtered["rows"] if r["customer_id"] == "C-103"][0]["orders_count"])

    def test_dependency_tool_applies_the_same_row_scope(self):
        from forgeworks.graph import connected_open_lines
        northstar = frozenset({"C-101"})
        self.assertEqual([("SO-104", 1)], [(l["order_id"], l["line_id"])
                                            for l in connected_open_lines(self.con, "CMP-9", northstar)])
        self.assertEqual(2300, connected_exposure(self.con, "CMP-9", northstar))
        self.assertEqual(0, connected_exposure(self.con, "CMP-9", frozenset({"C-103"})))
        with self.assertRaises(NotAuthorized):
            connected_exposure(self.con, "CMP-9", frozenset())

    def test_field_and_metric_order_do_not_change_the_answer(self):
        first = execute_plan(self.con, self.PLAN, ANALYST)["rows"]
        reordered = {"filters": {"order_status": "open"}, "group_by": "customer_id",
                     "metrics": ["orders_count", "open_order_value", "shipping_fees"]}
        second = execute_plan(self.con, reordered, ANALYST)["rows"]
        self.assertEqual([sorted(r.items()) for r in first], [sorted(r.items()) for r in second])


class ScreenDecisionOutcomeTests(Base):
    def test_operational_screen_arithmetic(self):
        screen = operational_screen(self.con, "CMP-9")
        self.assertEqual((1, 4, 3, 22), (screen["on_hand"], screen["units_required"],
                                         screen["shortfall_units"], screen["revised_arrival_day"]))
        self.assertEqual([("SO-104", 1, 2, -4), ("SO-105", 1, 2, 0)],
                         [(l["order_id"], l["line_id"], l["units_required"], l["slack_days"])
                          for l in screen["lines"]])
        self.assertFalse(any(l["covered_by_on_hand_alone"] for l in screen["lines"]))
        self.assertNotIn("probability", json.dumps({k: v for k, v in screen.items() if k != "caveats"}))
        with self.assertRaises(ValueError):
            operational_screen(self.con, "CMP-404")

    def test_undelayed_component_has_no_shortfall(self):
        screen = operational_screen(self.con, "CMP-4")
        self.assertEqual(0, screen["shortfall_units"])
        self.assertTrue(all(l["slack_days"] > 0 for l in screen["lines"]))

    def test_ranking_flips_with_the_assumed_penalty(self):
        first = lambda **kw: rank_recovery(**kw)[0]["action"]
        self.assertEqual("NORMAL", first(day_penalty_usd=36))
        self.assertEqual("EXPEDITE", first(day_penalty_usd=37))
        approved = lambda penalty: first(day_penalty_usd=penalty, engineering_approved=True)
        self.assertEqual(["NORMAL", "ALTERNATE_PART", "ALTERNATE_PART", "ALTERNATE_PART", "EXPEDITE"],
                         [approved(p) for p in (27, 28, 69, 70, 71)])
        self.assertEqual(["NORMAL"], [r["action"] for r in rank_recovery(max_direct_cost_usd=100)])
        self.assertEqual({"EXPEDITE": 180, "NORMAL": 600},
                         {r["action"]: r["score_usd_equivalent"] for r in rank_recovery()})
        self.assertEqual(230, [r for r in rank_recovery(engineering_approved=True)
                               if r["action"] == "ALTERNATE_PART"][0]["score_usd_equivalent"])
        with self.assertRaises(ValueError):
            rank_recovery(day_penalty_usd=-1)

    def test_naive_outcome_comparison_exposes_its_own_weakness(self):
        table = {r["action_taken"]: r for r in outcomes.naive_comparison(self.con, "CMP-9")["by_action"]}
        self.assertEqual((2, 2, ["SO-104"]), (table["EXPEDITE"]["on_time"], table["EXPEDITE"]["of"],
                                              table["EXPEDITE"]["exposed_orders"]))
        self.assertEqual((1, 2, ["SO-105"]), (table["NORMAL"]["on_time"], table["NORMAL"]["of"],
                                              table["NORMAL"]["exposed_orders"]))

    def test_outcome_rows_are_validated(self):
        self.assertEqual(4, outcomes.summarize(self.con)["observations"])
        header = "order_id,action_taken,actual_delay_days,actual_recovery_cost_usd,delivered_on_time\n"
        for bad in ("SO-999,EXPEDITE,0,10,yes\n", "SO-104,TELEPORT,0,10,yes\n",
                    "SO-104,EXPEDITE,0,10,maybe\n", "SO-104,EXPEDITE,-1,10,yes\n",
                    "SO-104,EXPEDITE,0,10,yes\nSO-104,NORMAL,0,0,yes\n"):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "outcomes.csv"
                path.write_text(header + bad, encoding="utf-8")
                with mock.patch.object(outcomes, "DATA", path), self.assertRaises(ValueError, msg=bad):
                    outcomes.summarize(self.con)


class DiscoveryEvidenceTests(Base):
    def test_profiling_cannot_separate_real_keys_from_coincidence(self):
        from forgeworks.discovery import candidates
        self.assertEqual(5, len(candidates(self.con)))
        proposals = evidence(self.con)
        self.assertEqual(13, len(proposals))
        self.assertTrue(all(p["status"] == "proposed" for p in proposals))
        self.assertEqual(8, sum(p["declared_foreign_key"] for p in proposals))
        self.assertEqual({1.0}, {p["containment"] for p in proposals})
        self.assertEqual(
            ["bom.component_id -> inventory.component_id",
             "components.component_id -> inventory.component_id",
             "order_lines.order_id -> shipments.order_id",
             "orders.order_id -> shipments.order_id",
             "suppliers.supplier_id -> components.supplier_id"],
            sorted(p["proposed_reference"] for p in proposals if not p["declared_foreign_key"]))


class DemoTests(unittest.TestCase):
    def test_demo_is_serializable_and_never_executes(self):
        result = demo.run()
        json.dumps(result)
        record = result["decision_record"]
        self.assertEqual(("AWAITING_APPROVAL", False, False),
                         (record["state"], record["execution_allowed"], record["executed"]))
        self.assertTrue(result["edge_projection"]["agrees_with_sql_join"])
        self.assertEqual(3950, result["supplier_disruption"]["connected_exposure_usd"])

    def test_demo_runs_clean_with_warnings_as_errors(self):
        done = subprocess.run([sys.executable, "-X", "dev", "-W", "error", "-m", "forgeworks.demo"],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual("", done.stderr)

    def test_connection_helper_closes(self):
        with closing(connect()) as con:
            con.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            con.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
