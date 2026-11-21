from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from typing import Iterable, Iterator

from forgeworks.data import connect

WIDTH = 72


@contextmanager
def fixtures() -> Iterator[sqlite3.Connection]:
    with closing(connect()) as con:
        yield con


def title(part: int, name: str) -> None:
    print("=" * WIDTH)
    print(f"Part {part} of 10 · {name}")
    print("ForgeWorks Manufacturing is fictional; every figure comes from data/.")
    print("=" * WIDTH)


def section(text: str) -> None:
    print()
    print((f"-- {text} " + "-" * max(0, WIDTH - len(text) - 4)).rstrip())


def note(text: str) -> None:
    print(f"   {text}")


def usd(value) -> str:
    return "—" if value is None else f"USD {value:,}"


def table(headers: list[str], rows: Iterable[Iterable]) -> None:
    rows = [["—" if cell is None else str(cell) for cell in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
              for i, h in enumerate(headers)]
    print(("   " + "  ".join(h.ljust(w) for h, w in zip(headers, widths))).rstrip())
    print("   " + "  ".join("-" * w for w in widths))
    for row in rows:
        print(("   " + "  ".join(cell.ljust(w) for cell, w in zip(row, widths))).rstrip())


def show_json(value) -> None:
    for line in json.dumps(value, indent=2).splitlines():
        print(f"   {line}")


def refused(call) -> str:
    try:
        call()
    except Exception as error:
        return f"{type(error).__name__}: {error}"
    return "NOT REFUSED"
