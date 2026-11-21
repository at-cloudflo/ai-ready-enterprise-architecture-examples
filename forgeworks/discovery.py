from __future__ import annotations

import sqlite3


def _id_columns(con: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    by_field: dict[str, list[str]] = {}
    for table in tables:
        for row in con.execute(f"PRAGMA table_info({table})"):
            col = row[1]
            if col.endswith("_id"):
                by_field.setdefault(col, []).append(table)
    return by_field


def candidates(con: sqlite3.Connection) -> list[dict]:
    return [
        {"candidate_key": field, "observed_in": observed,
         "status": "proposed", "confidence": None,
         "explanation": "Matching column name; steward review required"}
        for field, observed in sorted(_id_columns(con).items()) if len(observed) > 1
    ]


def evidence(con: sqlite3.Connection) -> list[dict]:
    proposals = []
    for column, tables in sorted(_id_columns(con).items()):
        if len(tables) < 2:
            continue
        distinct = {
            table: {row[0] for row in con.execute(f"SELECT DISTINCT {column} FROM {table}")}
            for table in tables
        }
        rows = {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
        declared = {
            (table, fk[2]) for table in tables
            for fk in con.execute(f"PRAGMA foreign_key_list({table})")
            if fk[3] == column and fk[4] == column
        }
        for parent in tables:
            if len(distinct[parent]) != rows[parent]:
                continue
            for child in tables:
                if child == parent:
                    continue
                max_rows = con.execute(
                    f"SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM {child} GROUP BY {column})"
                ).fetchone()[0]
                proposals.append({
                    "proposed_reference": f"{child}.{column} -> {parent}.{column}",
                    "name_match": True,
                    "unique_in_target": True,
                    "declared_foreign_key": (child, parent) in declared,
                    "containment": round(len(distinct[child] & distinct[parent]) / len(distinct[child]), 2),
                    "max_rows_per_key": max_rows,
                    "status": "proposed",
                })
    return proposals
