from __future__ import annotations

import sqlite3
from collections import deque

from .governance import validate_ontology

LINE_KEY = "order_id || '#' || line_id"

EXTRACTORS = {
    "SUPPLIES": ("components", "supplier_id", "component_id"),
    "USED_IN": ("bom", "component_id", "product_id"),
    "PLACES": ("orders", "customer_id", "order_id"),
    "HAS_LINE": ("order_lines", "order_id", LINE_KEY),
    "REFERENCES": ("order_lines", LINE_KEY, "product_id"),
    "FULFILLS": ("shipments", "shipment_id", "order_id"),
}


def edges(con: sqlite3.Connection) -> list[dict]:
    model = validate_ontology()
    result = []
    for relationship in model["relationships"]:
        predicate = relationship["predicate"]
        if predicate not in EXTRACTORS:
            raise ValueError(f"Approved relationship has no reviewed extractor: {predicate}")
        table, from_sql, to_sql = EXTRACTORS[predicate]
        query = f"SELECT DISTINCT {from_sql} AS src, {to_sql} AS dst FROM {table} ORDER BY 1, 2"
        for row in con.execute(query):
            result.append({
                "from": f"{relationship['from']}:{row['src']}",
                "predicate": predicate,
                "to": f"{relationship['to']}:{row['dst']}",
                "impact_direction": relationship["impact_direction"],
                "source": relationship["source"],
                "ontology_version": model["version"],
            })
    return result


def impact_adjacency(edge_list: list[dict]) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    for edge in edge_list:
        if edge["impact_direction"] == "forward":
            src, dst = edge["from"], edge["to"]
        else:
            src, dst = edge["to"], edge["from"]
        adjacency.setdefault(src, []).append(dst)
    return adjacency


def undirected_adjacency(edge_list: list[dict]) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    for edge in edge_list:
        adjacency.setdefault(edge["from"], []).append(edge["to"])
        adjacency.setdefault(edge["to"], []).append(edge["from"])
    return adjacency


def reachable(adjacency: dict[str, list[str]], start: str) -> dict[str, int]:
    depth = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbour in adjacency.get(node, ()):
            if neighbour not in depth:
                depth[neighbour] = depth[node] + 1
                queue.append(neighbour)
    del depth[start]
    return depth


def downstream(con: sqlite3.Connection, start: str) -> dict[str, int]:
    return reachable(impact_adjacency(edges(con)), start)


def downstream_sql(con: sqlite3.Connection, start: str) -> dict[str, int]:
    con.execute("DROP TABLE IF EXISTS temp.impact_edge")
    con.execute("CREATE TEMP TABLE impact_edge (src TEXT NOT NULL, dst TEXT NOT NULL)")
    con.executemany(
        "INSERT INTO temp.impact_edge VALUES (?, ?)",
        [(src, dst) for src, targets in impact_adjacency(edges(con)).items() for dst in targets],
    )
    query = """
        WITH RECURSIVE walk(node, hops) AS (
            SELECT dst, 1 FROM temp.impact_edge WHERE src = ?
            UNION
            SELECT e.dst, w.hops + 1
            FROM walk w JOIN temp.impact_edge e ON e.src = w.node
        )
        SELECT node, MIN(hops) AS hops FROM walk GROUP BY node ORDER BY node
    """
    result = {row["node"]: row["hops"] for row in con.execute(query, (start,))}
    con.execute("DROP TABLE temp.impact_edge")
    return result


def connected_open_line_keys(con: sqlite3.Connection, component_id: str) -> list[tuple[str, int]]:
    reached = downstream(con, f"Component:{component_id}")
    line_ids = sorted(node.split(":", 1)[1] for node in reached if node.startswith("SalesOrderLine:"))
    open_orders = {row[0] for row in con.execute(
        "SELECT order_id FROM orders WHERE order_status = 'open'")}
    keys = []
    for line in line_ids:
        order_id, line_id = line.split("#")
        if order_id in open_orders:
            keys.append((order_id, int(line_id)))
    return keys
