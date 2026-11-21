from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "models" / "semantic_model.json").read_text(encoding="utf-8"))

METRIC_SOURCES = {
    "net_order_value": (
        "order_lines l JOIN orders o ON o.order_id=l.order_id",
        "SUM(l.quantity * l.unit_price_usd - l.discount_usd)",
        None,
    ),
    "open_order_value": (
        "order_lines l JOIN orders o ON o.order_id=l.order_id",
        "SUM(l.quantity * l.unit_price_usd - l.discount_usd)",
        "o.order_status='open'",
    ),
    "orders_count": ("orders o", "COUNT(DISTINCT o.order_id)", None),
    "shipping_fees": (
        "shipments s JOIN orders o ON o.order_id=s.order_id",
        "SUM(s.shipping_fee_usd)",
        None,
    ),
}
DIMENSIONS = {"customer_id": "o.customer_id", "order_id": "o.order_id"}
ALLOWED_STATUS = frozenset(CATALOG["allowed_order_statuses"])
PLAN_FIELDS = frozenset(CATALOG["plan_contract"]["fields"])
PLAN_FILTERS = frozenset(CATALOG["plan_contract"]["filters"])


class UnmodeledQuestion(ValueError):
    pass


class NotAuthorized(PermissionError):
    pass


class _AllCustomers:

    def __repr__(self) -> str:
        return "ALL_CUSTOMERS"


ALL_CUSTOMERS = _AllCustomers()


@dataclass(frozen=True)
class Caller:

    name: str
    allowed_metrics: frozenset
    customer_scope: object


def resolve_scope(caller: Optional[Caller]) -> Optional[frozenset]:
    if not isinstance(caller, Caller):
        raise NotAuthorized("No caller: governed tools deny by default")
    if caller.customer_scope is ALL_CUSTOMERS:
        return None
    if isinstance(caller.customer_scope, frozenset) and caller.customer_scope:
        return caller.customer_scope
    raise NotAuthorized(f"{caller.name} has no customer scope")


ANALYST = Caller("finance-analyst", frozenset(METRIC_SOURCES), ALL_CUSTOMERS)


def execute(
    con: sqlite3.Connection,
    metric: str,
    group_by: Optional[str] = None,
    order_status: Optional[str] = None,
    customer_scope: Optional[frozenset] = None,
) -> list[dict]:
    if metric not in METRIC_SOURCES or metric not in CATALOG["metrics"]:
        raise UnmodeledQuestion(f"Unmodeled metric: {metric}")
    if group_by is not None and group_by not in DIMENSIONS:
        raise UnmodeledQuestion(f"Unsupported dimension: {group_by}")
    if order_status is not None and order_status not in ALLOWED_STATUS:
        raise UnmodeledQuestion(f"Unsupported order status: {order_status}")
    if metric == "open_order_value" and order_status == "fulfilled":
        raise UnmodeledQuestion("open_order_value cannot use fulfilled filter")
    if customer_scope is not None and not customer_scope:
        raise NotAuthorized("Caller has an empty customer scope")

    source, measure, fixed_filter = METRIC_SOURCES[metric]
    where = []
    values: list[str] = []
    if fixed_filter:
        where.append(fixed_filter)
    if order_status:
        where.append("o.order_status=?")
        values.append(order_status)
    if customer_scope is not None:
        scope = sorted(customer_scope)
        where.append("o.customer_id IN (" + ",".join("?" for _ in scope) + ")")
        values.extend(scope)
    dimension_sql = DIMENSIONS.get(group_by)
    if dimension_sql:
        select_sql = f"{dimension_sql} AS dimension, {measure} AS value"
        group_sql = f" GROUP BY {dimension_sql} ORDER BY {dimension_sql}"
    else:
        select_sql = f"{measure} AS value"
        group_sql = ""
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    statement = f"SELECT {select_sql} FROM {source}{where_sql}{group_sql}"
    rows = con.execute(statement, values).fetchall()
    return [dict(row) for row in rows]


def validate_plan(plan: object) -> tuple[list[str], Optional[str], Optional[str]]:
    if not isinstance(plan, dict):
        raise UnmodeledQuestion("A plan must be a JSON object")
    unknown = sorted(set(plan) - PLAN_FIELDS)
    if unknown:
        raise UnmodeledQuestion(f"Unsupported plan field: {unknown[0]}")
    metrics = plan.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise UnmodeledQuestion("A plan needs a non-empty list of metrics")
    if any(not isinstance(metric, str) for metric in metrics):
        raise UnmodeledQuestion("Metric names must be strings")
    if len(set(metrics)) != len(metrics):
        raise UnmodeledQuestion("A metric may appear only once in a plan")
    for metric in metrics:
        if metric not in METRIC_SOURCES or metric not in CATALOG["metrics"]:
            raise UnmodeledQuestion(f"Unmodeled metric: {metric}")
    group_by = plan.get("group_by")
    if group_by is not None and (not isinstance(group_by, str) or group_by not in DIMENSIONS):
        raise UnmodeledQuestion(f"Unsupported dimension: {group_by}")
    filters = plan.get("filters") or {}
    if not isinstance(filters, dict):
        raise UnmodeledQuestion("Filters must be a JSON object")
    unknown = sorted(set(filters) - PLAN_FILTERS)
    if unknown:
        raise UnmodeledQuestion(f"Unsupported filter: {unknown[0]}")
    order_status = filters.get("order_status")
    if order_status is not None and order_status not in ALLOWED_STATUS:
        raise UnmodeledQuestion(f"Unsupported order status: {order_status}")
    return list(metrics), group_by, order_status


def execute_plan(con: sqlite3.Connection, plan: object, caller: Caller) -> dict:
    metrics, group_by, order_status = validate_plan(plan)
    scope = resolve_scope(caller)
    for metric in metrics:
        if metric not in caller.allowed_metrics:
            raise NotAuthorized(f"{caller.name} is not granted metric: {metric}")
    per_metric = {
        metric: execute(con, metric, group_by=group_by, order_status=order_status,
                        customer_scope=scope)
        for metric in metrics
    }
    if group_by is None:
        rows = [{metric: per_metric[metric][0]["value"] for metric in metrics}]
    else:
        members = sorted({row["dimension"] for result in per_metric.values() for row in result})
        lookup = {metric: {row["dimension"]: row["value"] for row in result}
                  for metric, result in per_metric.items()}
        rows = [{group_by: member, **{metric: lookup[metric].get(member) for metric in metrics}}
                for member in members]
    return {
        "semantic_model_version": CATALOG["version"],
        "caller": caller.name,
        "customer_scope": sorted(scope) if scope is not None else "all",
        "filters": {"order_status": order_status or "any"},
        "certified_filters": {metric: CATALOG["metrics"][metric].get("certified_filter")
                              for metric in metrics},
        "base_grains": {metric: CATALOG["metrics"][metric]["base_grain"] for metric in metrics},
        "rows": rows,
    }
