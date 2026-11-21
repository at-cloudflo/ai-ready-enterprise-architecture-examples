from __future__ import annotations

import json
from contextlib import closing

from .data import connect
from .semantics import ANALYST, execute, execute_plan
from .graph import connected_open_lines, connected_exposure, dependency_paths
from .governance import validate_ontology, validate_mappings, decision_record
from .decision import rank_recovery
from .discovery import candidates, evidence
from .outcomes import summarize, naive_comparison
from .pitfalls import naive_shipping_fees, whole_order_exposure, status_blind_exposure
from .projection import edges, connected_open_line_keys
from .screening import operational_screen

PLAN = {
    "metrics": ["open_order_value", "shipping_fees", "orders_count"],
    "group_by": "customer_id",
    "filters": {"order_status": "open"},
}


def run() -> dict:
    with closing(connect()) as con:
        ontology = validate_ontology()
        mappings = validate_mappings(con)
        metrics = {
            metric: execute(con, metric)
            for metric in ("net_order_value", "open_order_value", "orders_count", "shipping_fees")
        }
        component_id = "CMP-9"
        paths = dependency_paths(con, component_id)
        lines = connected_open_lines(con, component_id)
        ranking = rank_recovery()
        record = decision_record("SO-104", 1, ranking[0])
        proposals = evidence(con)
        return {
            "company": "ForgeWorks Manufacturing (fictional)",
            "ontology_version": ontology["version"],
            "ontology_mappings_checked": len(mappings),
            "certified_metrics": metrics,
            "governed_plan": {"plan": PLAN, "caller": ANALYST.name, "answer": execute_plan(con, PLAN, ANALYST)},
            "counter_examples": {
                "shipping_fees_after_fan_out_join": naive_shipping_fees(con),
                "shipping_fees_certified": metrics["shipping_fees"][0]["value"],
                "exposure_at_whole_order_value": whole_order_exposure(con, component_id),
                "exposure_ignoring_order_status": status_blind_exposure(con, component_id),
                "note": "Wrong on purpose; see forgeworks/pitfalls.py",
            },
            "supplier_disruption": {
                "component_id": component_id,
                "paths": paths,
                "open_order_lines": lines,
                "connected_exposure_usd": connected_exposure(con, component_id),
                "interpretation": "structural exposure, not lateness probability or lost revenue",
            },
            "edge_projection": {
                "edges": len(edges(con)),
                "open_lines_found_by_walking_edges": [
                    f"{order_id}#{line_id}" for order_id, line_id in connected_open_line_keys(con, component_id)],
                "agrees_with_sql_join": connected_open_line_keys(con, component_id)
                    == [(line["order_id"], line["line_id"]) for line in lines],
            },
            "operational_screen": operational_screen(con, component_id),
            "ontology_discovery_candidates": candidates(con),
            "ontology_discovery_evidence": {
                "proposals": len(proposals),
                "with_declared_foreign_key": sum(p["declared_foreign_key"] for p in proposals),
                "name_and_profile_only": [p["proposed_reference"] for p in proposals
                                          if not p["declared_foreign_key"]],
                "status": "all proposed; none approved",
            },
            "ranked_recovery_options": ranking,
            "decision_record": record,
            "observed_outcome_summary": summarize(con),
            "outcomes_by_action": naive_comparison(con, component_id),
            "disclaimer": "No ML, external actions, authorization or real company information",
        }


def main() -> None:
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
