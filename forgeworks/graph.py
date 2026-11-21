from __future__ import annotations

import sqlite3
from typing import Optional

from .semantics import Caller, NotAuthorized, resolve_scope


def connected_open_lines(
    con: sqlite3.Connection,
    component_id: str,
    customer_scope: Optional[frozenset] = None,
) -> list[dict]:
    if customer_scope is not None and not customer_scope:
        raise NotAuthorized("Caller has an empty customer scope")
    scope_sql, values = "", [component_id]
    if customer_scope is not None:
        scope = sorted(customer_scope)
        scope_sql = " AND o.customer_id IN (" + ",".join("?" for _ in scope) + ")"
        values.extend(scope)
    query = f"""
        SELECT c.supplier_id, b.component_id, b.product_id,
               o.order_id, l.line_id, o.customer_id,
               (l.quantity*l.unit_price_usd-l.discount_usd) AS connected_line_value
        FROM bom b
        JOIN components c ON c.component_id=b.component_id
        JOIN order_lines l ON l.product_id=b.product_id
        JOIN orders o ON o.order_id=l.order_id
        WHERE b.component_id=? AND o.order_status='open'{scope_sql}
        ORDER BY o.order_id,l.line_id
    """
    return [dict(row) for row in con.execute(query, values).fetchall()]


def dependency_paths(con: sqlite3.Connection, component_id: str) -> list[list[str]]:
    rows = connected_open_lines(con, component_id)
    return [[r["supplier_id"], r["component_id"], r["product_id"],
             f"{r['order_id']}#{r['line_id']}", r["order_id"], r["customer_id"]]
            for r in rows]


def connected_exposure(
    con: sqlite3.Connection,
    component_id: str,
    customer_scope: Optional[frozenset] = None,
) -> int:
    return sum(r["connected_line_value"]
               for r in connected_open_lines(con, component_id, customer_scope))


def dependency_lookup(con: sqlite3.Connection, component_id: str, caller: Caller) -> dict:
    scope = resolve_scope(caller)
    if "open_order_value" not in caller.allowed_metrics:
        raise NotAuthorized(f"{caller.name} is not granted metric: open_order_value")
    lines = connected_open_lines(con, component_id, scope)
    return {
        "component_id": component_id,
        "caller": caller.name,
        "customer_scope": sorted(scope) if scope is not None else "all",
        "lines": lines,
        "connected_exposure_usd": sum(line["connected_line_value"] for line in lines),
        "interpretation": "structural dependency at order-line grain; not a delay, risk or loss",
    }
