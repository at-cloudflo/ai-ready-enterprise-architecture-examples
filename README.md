# Beyond the Data Platform — companion code

Runnable code for the article series **Beyond the Data Platform: Engineering the AI-Ready Enterprise**.

The series follows one fictional company, **ForgeWorks Manufacturing**, a maker of industrial pumps and valves, through a single question:

> A supplier delays a critical component. Which open customer commitments are structurally connected, which are genuinely at risk, what recovery action is best, who may approve it, and did it help?

Each article answers part of that question. This repository lets you run what the article shows and check every number yourself.

**Everything here is fictional.** The company, customers, suppliers, orders, figures and outcomes were invented for the series.

## Quick start

You need Python 3.10 or later. Nothing to install, no cloud account, no network.

```bash
git clone https://github.com/at-cloudflo/ai-ready-enterprise-architecture-examples.git
cd ai-ready-enterprise-architecture-examples
python3 -m series.part01_clean_data
```

## The parts

| Part | Article | Code | Run |
|---|---|---|---|
| 1 | [Clean Data Is Not Business Understanding](https://medium.com/@alitlili/clean-data-is-not-business-understanding-324dd43847ea) | [`series/part01_clean_data`](series/part01_clean_data/) | `python3 -m series.part01_clean_data` |
| 2 | ELTM and the Governed Semantic Gold Layer | [`series/part02_semantic_gold`](series/part02_semantic_gold/) | `python3 -m series.part02_semantic_gold` |
| 3 | Ontology Is Not a Graph Database | coming with the article | |
| 4 | Can AI Discover an Enterprise Ontology? | coming with the article | |
| 5 | When Do You Actually Need a Knowledge Graph? | coming with the article | |
| 6 | Designing the Enterprise Semantic Intelligence Layer | coming with the article | |
| 7 | Trustworthy Enterprise AI Is Not Text-to-SQL | coming with the article | |
| 8 | From Prediction to Decision Intelligence | coming with the article | |
| 9 | Agents Need Policies, Not Just Prompts | coming with the article | |
| 10 | The AI-Ready Enterprise: A Three-Wave Blueprint | coming with the article | |

Code for each part is added here when its article is published.

## Other things you can run

```bash
python3 -m forgeworks.demo
python3 -m unittest discover -s tests -v
python3 -m series --check
```

The first prints the whole scenario end to end as JSON. The second runs the tests behind every number. The third checks each part's script against the output it should print.

## Numbers you should see

| Quantity | Value |
|---|---|
| Net order value, all orders | USD 7,400 |
| Open order value | USD 6,200 |
| Shipping fees, summed per shipment | USD 415 |
| The same fees after joining orders, lines and shipments (wrong on purpose) | USD 535 |
| Open orders containing a product that uses component CMP-9 (wrong grain) | USD 4,550 |
| Open order **lines** that use CMP-9 | USD 3,950 |

If you get a different number, the tests will tell you which assumption changed.

## What is in this repository

```
series/            one folder per published part: run.py and its expected output
forgeworks/        the small library every part uses
data/              ten fictional CSV tables (see data/README.md)
models/            the ontology, semantic model and glossary as JSON
tests/             tests for the library and for each part's output
scripts/           a synthetic-data generator and a traversal comparison harness
```

## What this code is, and is not

It is a teaching companion. Data is loaded into an in-memory SQLite database; nothing is written anywhere.

It is **not** a production semantic layer, a graph database, a trained model, an optimizer or an agent. Where an article discusses those, the code shows the shape of the idea and says plainly what is missing. Nothing here calls a language model or any external service.

## License

Apache License 2.0. See [LICENSE](LICENSE).
