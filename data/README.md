# ForgeWorks synthetic data

All records are invented for educational use. Amounts are USD; days are **relative integer days in a fictional planning horizon**, not dates. `expected_day=12` means relative day 12. There are no real customers, employees, emails or personal data.

| File | Grain | Identifier | Notes |
|---|---|---|---|
| suppliers.csv | supplier | supplier_id | One row each |
| components.csv | component | component_id | Primary supplier; delay_days is an illustrative upstream signal |
| products.csv | product | product_id | Finished goods |
| bom.csv | product/component | product_id + component_id | Units required per product |
| customers.csv | customer | customer_id | Fictional tiers |
| orders.csv | order | order_id | Open or fulfilled |
| order_lines.csv | order line | order_id + line_id | Net line = qty × unit price − discount |
| inventory.csv | component | component_id | Current on-hand snapshot, not allocation-aware |
| shipments.csv | shipment | shipment_id | Shipment fee **must not** be duplicated by joining through order lines |
| outcomes.csv | observed demo outcome | order_id | Synthetic retrospective observation; not causal evidence. Validated on load: known order, known action, yes/no flag |

## Canonical example

Supplier **SUP-A** supplies **CMP-9**, used in products **PMP-7** and **PMP-8**. Open orders **SO-104** and **SO-105** contain those products. A delivered order **SO-106** also uses PMP-7 but is not an *open* exposure. The graph traversal should report only open orders for its advertised scope.

Open-order value is **USD 6,200** across SO-104 (2,900), SO-105 (1,650) and SO-107 (1,650). Connected open order-**line** value for CMP-9 is **USD 3,950**: SO-104 contributes only its PMP-7 line (2,300), not the entire order (2,900), plus SO-105 line 1 (1,650). Counting all of SO-104 gives 4,550 and overstates the component-level exposure by the 600 of its VAL-2 line. Ignoring order status gives 5,150 by adding fulfilled SO-106.

Supplier delay is an **event**, not an allocation-aware late-shipment prediction. On-hand stock cannot be deducted naively without accounting for bill-of-material requirements, work order priority and supply commitments.

## Derived facts the code and articles use

These follow from the files above; none is stored. Each is asserted by a test in `tests/`.

- Shipping fees total **USD 415** at shipment grain. One join across orders, lines and shipments reports **USD 535**, because SO-104's 120 fee repeats on its two lines.
- CMP-9 is required by open lines in quantity 4 (SO-104 line 1: 2 × 1; SO-105 line 1: 1 × 2). One unit is on hand. Shortfall 3.
- CMP-9 was expected on day 12 and is 10 days late: revised arrival day 22. Slack against promised days 18 and 22 is −4 and 0.
- Six approved relationships produce 26 edges between 25 nodes.
- In `outcomes.csv`, only SO-104 and SO-105 were exposed to the CMP-9 delay. SO-107 contains only VAL-2, and SO-106 was fulfilled beforehand. The file records what was done, not what was recommended.

## What the fixtures deliberately lack

No dates (only relative day numbers), no lead times, no work orders or purchase orders, no margins or penalties, no multi-level bill of materials, no alternate suppliers, no cross-system identity conflicts. Articles say so wherever it limits a conclusion.

## Validation requirements

- All foreign keys must resolve to real rows.
- Order-line identity is compound; `line_id` alone is not unique across orders.
- No negative discounts, quantities, unit prices or freight fees.
- Discount must not exceed gross line value.
- No duplicate business keys at the declared grain.
- Tests should independently verify business totals and exposure scope.

## Reproduction

The code loads files into in-memory SQLite. Run `python3 -m forgeworks.demo` from repository root. No cloud credentials required.
