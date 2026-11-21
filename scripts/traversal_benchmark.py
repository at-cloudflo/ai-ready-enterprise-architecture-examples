from __future__ import annotations

import argparse
import random
import sqlite3
import statistics
import time
from collections import deque


def build_network(layers: int, width: int, fan_out: int, seed: int) -> list[tuple[str, str]]:
    if layers < 2 or width < 1 or fan_out < 1:
        raise ValueError("layers must be >= 2; width and fan_out must be >= 1")
    if fan_out > width:
        raise ValueError("fan_out cannot exceed width")
    rng = random.Random(seed)
    edges = []
    for layer in range(layers - 1):
        targets = [f"SYN-L{layer + 1}-{i:05d}" for i in range(width)]
        for i in range(width):
            for target in rng.sample(targets, fan_out):
                edges.append((f"SYN-L{layer}-{i:05d}", target))
    return edges


def load_sql(edges: list[tuple[str, str]]) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE edge (src TEXT NOT NULL, dst TEXT NOT NULL)")
    con.executemany("INSERT INTO edge VALUES (?, ?)", edges)
    con.execute("CREATE INDEX edge_src ON edge (src)")
    return con


def load_adjacency(edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    for src, dst in edges:
        adjacency.setdefault(src, []).append(dst)
    return adjacency


def reach_sql(con: sqlite3.Connection, start: str, max_hops: int) -> set[str]:
    query = """
        WITH RECURSIVE walk(node, hops) AS (
            SELECT dst, 1 FROM edge WHERE src = ?
            UNION
            SELECT e.dst, w.hops + 1 FROM walk w JOIN edge e ON e.src = w.node
            WHERE w.hops < ?
        )
        SELECT DISTINCT node FROM walk
    """
    return {row[0] for row in con.execute(query, (start, max_hops))}


def reach_adjacency(adjacency: dict[str, list[str]], start: str, max_hops: int) -> set[str]:
    depth = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if depth[node] == max_hops:
            continue
        for neighbour in adjacency.get(node, ()):
            if neighbour not in depth:
                depth[neighbour] = depth[node] + 1
                queue.append(neighbour)
    del depth[start]
    return set(depth)


def run(layers: int = 8, width: int = 400, fan_out: int = 3, seed: int = 2026,
        starts: int = 20, repeats: int = 5) -> list[dict]:
    edges = build_network(layers, width, fan_out, seed)
    con = load_sql(edges)
    adjacency = load_adjacency(edges)
    rng = random.Random(seed + 1)
    start_nodes = [f"SYN-L0-{i:05d}" for i in rng.sample(range(width), min(starts, width))]
    rows = []
    for max_hops in range(1, layers):
        sql_times, walk_times, sizes, identical = [], [], [], True
        for start in start_nodes:
            best_sql = best_walk = float("inf")
            for _ in range(repeats):
                t0 = time.perf_counter()
                via_sql = reach_sql(con, start, max_hops)
                t1 = time.perf_counter()
                via_walk = reach_adjacency(adjacency, start, max_hops)
                t2 = time.perf_counter()
                best_sql, best_walk = min(best_sql, t1 - t0), min(best_walk, t2 - t1)
            identical = identical and via_sql == via_walk
            sizes.append(len(via_sql))
            sql_times.append(best_sql)
            walk_times.append(best_walk)
        rows.append({
            "max_hops": max_hops,
            "median_nodes_reached": int(statistics.median(sizes)),
            "identical_results": identical,
            "recursive_sql_ms": round(statistics.median(sql_times) * 1000, 3),
            "adjacency_walk_ms": round(statistics.median(walk_times) * 1000, 3),
        })
    con.close()
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="Compare a recursive SQL query and an adjacency walk on one synthetic network.")
    p.add_argument("--layers", type=int, default=8)
    p.add_argument("--width", type=int, default=400)
    p.add_argument("--fan-out", type=int, default=3)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--starts", type=int, default=20)
    p.add_argument("--repeats", type=int, default=5)
    args = p.parse_args()
    rows = run(args.layers, args.width, args.fan_out, args.seed, args.starts, args.repeats)
    if not all(row["identical_results"] for row in rows):
        raise SystemExit("Implementations disagree: fix correctness before reading any timing")
    print(f"Synthetic layered network: {args.layers} layers x {args.width} nodes, "
          f"fan-out {args.fan_out}, seed {args.seed}")
    print("Both implementations run in-process and in memory. This shows a method, not a product result.")
    print(f"{'hops':>4}  {'nodes reached':>13}  {'identical':>9}  {'recursive SQL ms':>16}  {'adjacency walk ms':>17}")
    for row in rows:
        print(f"{row['max_hops']:>4}  {row['median_nodes_reached']:>13}  {str(row['identical_results']):>9}  "
              f"{row['recursive_sql_ms']:>16.3f}  {row['adjacency_walk_ms']:>17.3f}")


if __name__ == "__main__":
    main()
