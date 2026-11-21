from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from . import policy

ROOT = Path(__file__).resolve().parents[1]
IMPACT_DIRECTIONS = frozenset({"forward", "reverse"})
SOURCE_SNAPSHOT = "demo-fixture-v1"


def _load(name: str) -> dict:
    return json.loads((ROOT / "models" / name).read_text(encoding="utf-8"))


def validate_ontology(path: Optional[Path] = None, model: Optional[dict] = None) -> dict:
    if model is None:
        model = json.loads((path or ROOT / "models" / "ontology.json").read_text(encoding="utf-8"))
    classes = model.get("classes", [])
    if not classes or len(classes) != len(set(classes)):
        raise ValueError("Ontology classes must be nonempty and unique")
    seen = set()
    for relationship in model.get("relationships", []):
        if relationship["from"] not in classes or relationship["to"] not in classes:
            raise ValueError(f"Unrecognized ontology relationship: {relationship}")
        key = (relationship["from"], relationship["predicate"], relationship["to"])
        if key in seen:
            raise ValueError(f"Duplicate ontology relationship: {key}")
        seen.add(key)
        if relationship.get("status") != "approved":
            raise ValueError("Runtime ontology contains nonapproved relations")
        if relationship.get("impact_direction") not in IMPACT_DIRECTIONS:
            raise ValueError(f"Relationship needs an approved impact_direction: {key}")
    missing_keys = sorted(set(classes) - set(model.get("keys", {})))
    if missing_keys:
        raise ValueError(f"Ontology classes without a declared key: {missing_keys}")
    return model


def _parse_mapping(mapping: str) -> tuple[str, list[str]]:
    table, _, columns = mapping.partition(".")
    return table, [column for column in columns.split("+") if column]


def validate_mappings(con: sqlite3.Connection, model: Optional[dict] = None) -> list[str]:
    model = validate_ontology(model=model)
    schema = {
        row[0]: {column[1] for column in con.execute(f"PRAGMA table_info({row[0]})")}
        for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    }
    mappings = list(model["keys"].values()) + [r["source"] for r in model["relationships"]]
    for mapping in mappings:
        table, columns = _parse_mapping(mapping)
        if table not in schema:
            raise ValueError(f"Ontology mapping names an unknown table: {mapping}")
        unknown = [column for column in columns if column not in schema[table]]
        if not columns or unknown:
            raise ValueError(f"Ontology mapping names an unknown column: {mapping}")
    return mappings


def decision_record(order_id: str, line_id: int, recommendation: dict,
                    requested_by: str = "demo-planner") -> dict:
    semantic_version = _load("semantic_model.json")["version"]
    ontology_version = _load("ontology.json")["version"]
    action = recommendation["action"]
    if not order_id or not isinstance(line_id, int) or line_id < 1:
        raise ValueError("A decision needs an order id and a positive line id")
    record = {
        "decision_id": f"DEMO-{order_id}-{line_id}",
        "idempotency_key": policy.idempotency_key(order_id, line_id, action, SOURCE_SNAPSHOT,
                                                  semantic_version),
        "order_id": order_id,
        "line_id": line_id,
        "recommended_action": action,
        "estimated_cost_usd": recommendation["direct_cost_usd"],
        "estimated_delay_days": recommendation["expected_delay_days"],
        "score_usd_equivalent": recommendation["score_usd_equivalent"],
        "source_snapshot": SOURCE_SNAPSHOT,
        "semantic_model_version": semantic_version,
        "ontology_version": ontology_version,
        "requested_by": requested_by,
        "required_approvals": list(policy.required_approvals(action)),
        "approvals": [],
        "state": "PROPOSED",
        "history": ["PROPOSED"],
        "execution_allowed": False,
        "executed": False,
    }
    record = policy.advance(record, "VALIDATED")
    return policy.advance(record, "AWAITING_APPROVAL")
