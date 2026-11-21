from __future__ import annotations

import sqlite3


def naive_fanout_by_customer(con: sqlite3.Connection) -> list[dict]:
    query = """
        SELECT o.customer_id,
               SUM(l.quantity * l.unit_price_usd - l.discount_usd) AS net_order_value,
               SUM(s.shipping_fee_usd) AS shipping_fees_wrong,
               COUNT(o.order_id) AS orders_count_wrong
        FROM orders o
        JOIN order_lines l ON l.order_id = o.order_id
        JOIN shipments s ON s.order_id = o.order_id
        GROUP BY o.customer_id
        ORDER BY o.customer_id
    """
    return [dict(row) for row in con.execute(query)]


def naive_shipping_fees(con: sqlite3.Connection) -> int:
    return sum(row["shipping_fees_wrong"] for row in naive_fanout_by_customer(con))


def whole_order_exposure(con: sqlite3.Connection, component_id: str) -> int:
    query = """
        SELECT SUM(l.quantity * l.unit_price_usd - l.discount_usd)
        FROM order_lines l
        JOIN orders o ON o.order_id = l.order_id
        WHERE o.order_status = 'open'
          AND l.order_id IN (
              SELECT l2.order_id FROM order_lines l2
              JOIN bom b ON b.product_id = l2.product_id
              WHERE b.component_id = ?)
    """
    return con.execute(query, (component_id,)).fetchone()[0] or 0


def status_blind_exposure(con: sqlite3.Connection, component_id: str) -> int:
    query = """
        SELECT SUM(l.quantity * l.unit_price_usd - l.discount_usd)
        FROM order_lines l
        JOIN bom b ON b.product_id = l.product_id
        WHERE b.component_id = ?
    """
    return con.execute(query, (component_id,)).fetchone()[0] or 0
