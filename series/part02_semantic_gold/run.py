import json

from forgeworks import pitfalls
from forgeworks.semantics import ANALYST, CATALOG, execute_plan

from series._common import fixtures, note, refused, section, show_json, table, title


def main() -> None:
    title(2, "ELTM and the Governed Semantic Gold Layer")
    with fixtures() as con:
        section("One join across three grains")
        table(["customer", "net order value", "shipping fees", "orders"],
              [(r["customer_id"], r["net_order_value"], r["shipping_fees_wrong"], r["orders_count_wrong"])
               for r in pitfalls.naive_fanout_by_customer(con)])
        note("C-101 is wrong in two of three columns: fees 240 (true 120), orders 2 (true 1).")

        section("What the model step produces: one certified measure")
        show_json({"shipping_fees": CATALOG["metrics"]["shipping_fees"]})
        note(f"Semantic model {CATALOG['version']}: {len(CATALOG['metrics'])} measures, "
             f"dimensions {sorted(CATALOG['dimensions'])}, filter order_status.")

        section("A typed plan, answered one query per grain and merged")
        plan = {"metrics": ["net_order_value", "shipping_fees", "orders_count"], "group_by": "customer_id"}
        note("plan = " + json.dumps(plan))
        answer = execute_plan(con, plan, ANALYST)
        table(["customer", "net order value", "shipping fees", "orders"],
              [(r["customer_id"], r["net_order_value"], r["shipping_fees"], r["orders_count"])
               for r in answer["rows"]])
        table(["metric", "base grain", "certified filter"],
              [(m, g, answer["certified_filters"][m]) for m, g in answer["base_grains"].items()])
        note(f"caller {answer['caller']}, scope {answer['customer_scope']}, "
             f"model version {answer['semantic_model_version']}")

        section("Refusal is part of the contract")
        for request in ({"metrics": ["expected_loss"]},
                        {"metrics": ["net_order_value"], "group_by": "product_id"},
                        {"metrics": ["net_order_value"], "sql": "SELECT 1"}):
            note(f"{json.dumps(request)}")
            note(f"  -> {refused(lambda: execute_plan(con, request, ANALYST))}")


if __name__ == "__main__":
    main()
