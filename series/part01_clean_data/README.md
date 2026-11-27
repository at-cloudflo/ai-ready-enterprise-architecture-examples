# Part 1 — Clean Data Is Not Business Understanding

Companion code for [*Clean Data Is Not Business Understanding*](https://medium.com/@alitlili/clean-data-is-not-business-understanding-324dd43847ea), Part 1 of *Beyond the Data Platform: Engineering the AI-Ready Enterprise*. One question about the delayed impeller CMP-9 produces four totals from one clean warehouse.

```bash
python3 -m series.part01_clean_data
```

Run it from the repository's top folder. Python 3.10 or later, no packages, no network. ForgeWorks Manufacturing is fictional; every figure comes from [`data/`](../../data/).

## What the script shows

- every order and line, with the products that use CMP-9
- the four totals: USD 7,400 / 6,200 / 4,550 / 3,950, and why each differs
- the join that runs without error and reports USD 535 of shipping fees instead of 415
- what the data can and cannot say about the delay

## Files

- [`run.py`](run.py) — the article's examples, in the order the article tells them
- [`expected_output.txt`](expected_output.txt) — what the script prints; `tests/test_parts.py` fails if it changes

## Built on

- `forgeworks.semantics.execute`
- `forgeworks.pitfalls`
- `forgeworks.graph`

The shared code lives in [`forgeworks/`](../../forgeworks/), the data in [`data/`](../../data/) and the definitions in [`models/`](../../models/). The script writes nothing, calls no model and reaches no network.
