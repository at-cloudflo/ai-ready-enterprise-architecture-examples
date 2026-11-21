from forgeworks import graph, pitfalls
from forgeworks.semantics import execute

from series._common import fixtures, note, section, table, title, usd


def main() -> None:
    title(1, "Clean Data Is Not Business Understanding")
    with fixtures() as con:
        section("Every order: four orders, five order lines")
        rows = con.execute("""
            SELECT l.order_id, l.line_id, l.product_id, c.customer_name,
                   l.quantity * l.unit_price_usd - l.discount_usd, o.order_status
            FROM order_lines l JOIN orders o USING (order_id) JOIN customers c USING (customer_id)
            ORDER BY l.order_id, l.line_id""").fetchall()
        table(["order", "line", "product", "customer", "net value", "status"],
              [(r[0], r[1], r[2], r[3], f"{r[4]:,}", r[5]) for r in rows])
        uses = con.execute("SELECT GROUP_CONCAT(product_id, ', ') FROM bom WHERE component_id = 'CMP-9'").fetchone()[0]
        note(f"CMP-9 (the delayed impeller) is used in: {uses}. Not in VAL-2.")

        section("One question, four answers: how much business is exposed to CMP-9?")
        answers = [
            ("every order line", execute(con, "net_order_value")[0]["value"], "includes fulfilled SO-106"),
            ("open orders only", execute(con, "open_order_value")[0]["value"], "includes valve order SO-107"),
            ("open orders containing a CMP-9 product", pitfalls.whole_order_exposure(con, "CMP-9"),
             "counts SO-104's valve line"),
            ("open order lines that use CMP-9", graph.connected_exposure(con, "CMP-9"), "structural exposure"),
        ]
        table(["what was summed", "total", "why it differs"], [(a, usd(v), w) for a, v, w in answers])
        note("Each step down applies one piece of meaning: a definition, a relationship, a grain.")

        section("The join that runs and lies: shipping fees")
        certified = execute(con, "shipping_fees")[0]["value"]
        naive = pitfalls.naive_shipping_fees(con)
        table(["method", "total fees"],
              [("summed at shipment grain (certified)", usd(certified)),
               ("orders JOIN lines JOIN shipments", usd(naive))])
        note(f"Difference {usd(naive - certified)}: SO-104 has two lines, so its USD 120 fee is counted twice.")
        table(["customer", "net value", "fees (joined)", "orders (joined)"],
              [(r["customer_id"], f"{r['net_order_value']:,}", r["shipping_fees_wrong"], r["orders_count_wrong"])
               for r in pitfalls.naive_fanout_by_customer(con)])
        note("Net value is right in every row, which is why the query passes a spot check.")

        section("What the data can and cannot say at 10:00 on Monday")
        lines = graph.connected_open_lines(con, "CMP-9")
        for line in lines:
            note(f"known:    {line['order_id']} line {line['line_id']} ({line['product_id']}) depends on CMP-9, "
                 f"{usd(line['connected_line_value'])}")
        note("not known from the dependency alone: which line will be late (Part 8 screens stock and dates)")
        note("undefined: expected loss; no approved model exists")


if __name__ == "__main__":
    main()
