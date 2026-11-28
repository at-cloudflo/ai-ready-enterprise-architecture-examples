# Part 2 — ELTM and the Governed Semantic Gold Layer

Companion code for [*ELTM and the Governed Semantic Gold Layer*](https://medium.com/@alitlili/eltm-and-the-governed-semantic-gold-layer-cad73454461d), Part 2 of *Beyond the Data Platform: Engineering the AI-Ready Enterprise*. Fan-out, a certified model entry, a typed plan compiled one query per grain, and refusal.

```bash
python3 -m series.part02_semantic_gold
```

Run it from the repository's top folder. Python 3.10 or later, no packages, no network. ForgeWorks Manufacturing is fictional; every figure comes from [`data/`](../../data/).

## What the script shows

- the one-join query by customer, wrong in two columns for one customer
- the certified definition of shipping fees
- a three-measure plan answered without fan-out, with grains, filters and model version
- three refusals: undefined measure, unapproved dimension, raw SQL field

## Files

- [`run.py`](run.py) — the article's examples, in the order the article tells them
- [`expected_output.txt`](expected_output.txt) — what the script prints; `tests/test_parts.py` fails if it changes

## Built on

- `forgeworks.pitfalls`
- `forgeworks.semantics.execute_plan`
- `models/semantic_model.json`

The shared code lives in [`forgeworks/`](../../forgeworks/), the data in [`data/`](../../data/) and the definitions in [`models/`](../../models/). The script writes nothing, calls no model and reaches no network.
