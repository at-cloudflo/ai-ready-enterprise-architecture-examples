from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

TABLES = {
    "suppliers": """CREATE TABLE suppliers (
        supplier_id TEXT PRIMARY KEY, name TEXT NOT NULL)""",
    "components": """CREATE TABLE components (
        component_id TEXT PRIMARY KEY, component_name TEXT NOT NULL,
        supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
        expected_day INTEGER NOT NULL, delay_days INTEGER NOT NULL CHECK(delay_days >= 0))""",
    "products": """CREATE TABLE products (
        product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL)""",
    "bom": """CREATE TABLE bom (
        product_id TEXT NOT NULL REFERENCES products(product_id),
        component_id TEXT NOT NULL REFERENCES components(component_id),
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        PRIMARY KEY(product_id,component_id))""",
    "customers": """CREATE TABLE customers (
        customer_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, tier TEXT NOT NULL)""",
    "orders": """CREATE TABLE orders (
        order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        order_status TEXT NOT NULL CHECK(order_status IN ('open','fulfilled')),
        promised_day INTEGER NOT NULL)""",
    "order_lines": """CREATE TABLE order_lines (
        order_id TEXT NOT NULL REFERENCES orders(order_id), line_id INTEGER NOT NULL,
        product_id TEXT NOT NULL REFERENCES products(product_id),
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price_usd INTEGER NOT NULL CHECK(unit_price_usd >= 0),
        discount_usd INTEGER NOT NULL CHECK(discount_usd >= 0 AND discount_usd <= quantity * unit_price_usd),
        PRIMARY KEY(order_id,line_id))""",
    "inventory": """CREATE TABLE inventory (
        component_id TEXT PRIMARY KEY REFERENCES components(component_id),
        on_hand INTEGER NOT NULL CHECK(on_hand >= 0))""",
    "shipments": """CREATE TABLE shipments (
        shipment_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL REFERENCES orders(order_id),
        shipping_fee_usd INTEGER NOT NULL CHECK(shipping_fee_usd >= 0),
        shipment_status TEXT NOT NULL)""",
}

def connect() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    for name, ddl in TABLES.items():
        con.execute(ddl)
        with (DATA / (name + ".csv")).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValueError(f"Fixture {name} is empty")
        columns = list(rows[0].keys())
        if any(list(r.keys()) != columns for r in rows):
            raise ValueError(f"Inconsistent columns in {name}")
        placeholders = ",".join("?" for _ in columns)
        con.executemany(
            f"INSERT INTO {name} ({','.join(columns)}) VALUES ({placeholders})",
            [tuple(row[column] for column in columns) for row in rows],
        )
    violations = con.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise ValueError(f"Foreign-key violations: {violations}")
    return con
