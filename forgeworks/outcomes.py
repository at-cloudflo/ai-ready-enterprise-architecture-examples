from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Optional

from .decision import SCENARIOS

DATA = Path(__file__).resolve().parents[1] / "data" / "outcomes.csv"
KNOWN_ACTIONS = frozenset(scenario.action for scenario in SCENARIOS)


def load(con: Optional[sqlite3.Connection] = None) -> list[dict]:
    with DATA.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Outcome fixture is empty")
    known_orders = None
    if con is not None:
        known_orders = {row[0] for row in con.execute("SELECT order_id FROM orders")}
    seen = set()
    for row in rows:
        if row["order_id"] in seen:
            raise ValueError(f"Duplicate outcome for order: {row['order_id']}")
        seen.add(row["order_id"])
        if known_orders is not None and row["order_id"] not in known_orders:
            raise ValueError(f"Outcome for unknown order: {row['order_id']}")
        if row["action_taken"] not in KNOWN_ACTIONS:
            raise ValueError(f"Outcome with unknown action: {row['action_taken']}")
        if row["delivered_on_time"] not in ("yes", "no"):
            raise ValueError(f"Outcome with invalid on-time flag: {row['delivered_on_time']}")
        if int(row["actual_delay_days"]) < 0 or int(row["actual_recovery_cost_usd"]) < 0:
            raise ValueError(f"Outcome with negative delay or cost: {row['order_id']}")
    return rows


def summarize(con: Optional[sqlite3.Connection] = None) -> dict:
    rows = load(con)
    return {
        "observations": len(rows),
        "on_time_deliveries": sum(row["delivered_on_time"] == "yes" for row in rows),
        "actual_recovery_cost_usd": sum(int(row["actual_recovery_cost_usd"]) for row in rows),
        "total_delay_days": sum(int(row["actual_delay_days"]) for row in rows),
        "caveat": "Descriptive synthetic observations; cannot establish treatment effects",
    }


def naive_comparison(con: sqlite3.Connection, component_id: str) -> dict:
    exposed = {row[0] for row in con.execute(
        """SELECT DISTINCT o.order_id FROM orders o
           JOIN order_lines l ON l.order_id = o.order_id
           JOIN bom b ON b.product_id = l.product_id
           WHERE b.component_id = ? AND o.order_status = 'open'""", (component_id,))}
    table = []
    for action in sorted({row["action_taken"] for row in load(con)}):
        group = [row for row in load(con) if row["action_taken"] == action]
        table.append({
            "action_taken": action,
            "orders": [row["order_id"] for row in group],
            "on_time": sum(row["delivered_on_time"] == "yes" for row in group),
            "of": len(group),
            "exposed_orders": [row["order_id"] for row in group if row["order_id"] in exposed],
        })
    return {
        "component_id": component_id,
        "by_action": table,
        "caveat": "Naive comparison: actions were not assigned at random and most orders were "
                  "not exposed to the event; this is not an estimate of any action's effect",
    }
