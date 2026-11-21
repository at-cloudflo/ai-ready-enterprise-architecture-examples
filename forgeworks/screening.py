from __future__ import annotations

import sqlite3

CAVEATS = [
    "On-hand stock is a snapshot; it is not reserved for these lines and other demand may claim it.",
    "Slack ignores production and transit lead time, which the fixtures do not contain.",
    "A screen is not a probability of late delivery and not a financial consequence.",
]


def operational_screen(con: sqlite3.Connection, component_id: str) -> dict:
    component = con.execute(
        """SELECT c.expected_day, c.delay_days, COALESCE(i.on_hand, 0) AS on_hand
           FROM components c LEFT JOIN inventory i ON i.component_id = c.component_id
           WHERE c.component_id = ?""", (component_id,)).fetchone()
    if component is None:
        raise ValueError(f"Unknown component: {component_id}")
    revised_arrival_day = component["expected_day"] + component["delay_days"]
    lines = []
    for row in con.execute(
        """SELECT l.order_id, l.line_id, l.product_id, o.promised_day,
                  l.quantity * b.quantity AS units_required
           FROM bom b
           JOIN order_lines l ON l.product_id = b.product_id
           JOIN orders o ON o.order_id = l.order_id
           WHERE b.component_id = ? AND o.order_status = 'open'
           ORDER BY o.promised_day, l.order_id, l.line_id""", (component_id,)):
        slack = row["promised_day"] - revised_arrival_day
        lines.append({
            "order_id": row["order_id"],
            "line_id": row["line_id"],
            "product_id": row["product_id"],
            "units_required": row["units_required"],
            "covered_by_on_hand_alone": row["units_required"] <= component["on_hand"],
            "promised_day": row["promised_day"],
            "slack_days": slack,
            "screen": "promise cannot be met from the delayed receipt" if slack < 0
                      else "feasible only if lead time is at most the slack; unknown",
        })
    required = sum(line["units_required"] for line in lines)
    return {
        "component_id": component_id,
        "on_hand": component["on_hand"],
        "units_required": required,
        "shortfall_units": max(0, required - component["on_hand"]),
        "revised_arrival_day": revised_arrival_day,
        "lines": lines,
        "caveats": CAVEATS,
    }
