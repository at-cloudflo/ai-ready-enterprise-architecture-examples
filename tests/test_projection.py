import unittest
from collections import Counter

from forgeworks import projection
from forgeworks.data import connect
from forgeworks.governance import validate_ontology
from forgeworks.graph import connected_open_lines
from scripts import traversal_benchmark


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.con = connect()
        self.addCleanup(self.con.close)
        self.edges = projection.edges(self.con)

    def test_one_extractor_per_approved_relationship(self):
        self.assertEqual({r["predicate"] for r in validate_ontology()["relationships"]},
                         set(projection.EXTRACTORS))

    def test_edge_counts_and_provenance(self):
        self.assertEqual({"SUPPLIES": 3, "USED_IN": 5, "PLACES": 4, "HAS_LINE": 5,
                          "REFERENCES": 5, "FULFILLS": 4},
                         dict(Counter(e["predicate"] for e in self.edges)))
        self.assertEqual(26, len(self.edges))
        self.assertTrue(all(e["source"] and e["ontology_version"] == "1.1" for e in self.edges))

    def test_projection_walk_finds_the_same_lines_as_the_join(self):
        self.assertEqual([(r["order_id"], r["line_id"]) for r in connected_open_lines(self.con, "CMP-9")],
                         projection.connected_open_line_keys(self.con, "CMP-9"))

    def test_recursive_sql_and_adjacency_walk_agree_from_every_node(self):
        nodes = {e["from"] for e in self.edges} | {e["to"] for e in self.edges}
        self.assertEqual(25, len(nodes))
        for node in sorted(nodes):
            self.assertEqual(projection.downstream(self.con, node),
                             projection.downstream_sql(self.con, node), node)

    def test_impact_direction_keeps_the_walk_honest(self):
        directed = projection.downstream(self.con, "Component:CMP-9")
        self.assertEqual(14, len(directed))
        self.assertIn("SalesOrderLine:SO-104#1", directed)
        self.assertNotIn("SalesOrderLine:SO-104#2", directed)
        self.assertNotIn("Product:VAL-2", directed)
        self.assertNotIn("Supplier:SUP-A", directed)
        undirected = projection.reachable(projection.undirected_adjacency(self.edges), "Component:CMP-9")
        self.assertEqual(24, len(undirected))
        self.assertEqual(6, max(undirected.values()))


class BenchmarkHarnessTests(unittest.TestCase):
    def test_both_implementations_return_identical_sets(self):
        rows = traversal_benchmark.run(layers=5, width=30, fan_out=2, seed=7, starts=6, repeats=1)
        self.assertEqual([1, 2, 3, 4], [row["max_hops"] for row in rows])
        self.assertTrue(all(row["identical_results"] for row in rows))
        self.assertEqual(2, rows[0]["median_nodes_reached"])

    def test_network_is_repeatable_and_validated(self):
        self.assertEqual(traversal_benchmark.build_network(3, 10, 2, 1),
                         traversal_benchmark.build_network(3, 10, 2, 1))
        with self.assertRaises(ValueError):
            traversal_benchmark.build_network(1, 10, 2, 1)
        with self.assertRaises(ValueError):
            traversal_benchmark.build_network(3, 2, 5, 1)


if __name__ == "__main__":
    unittest.main()
