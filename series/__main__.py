from __future__ import annotations

import argparse
import contextlib
import difflib
import importlib
import io
import sys
from pathlib import Path

from . import PARTS

HERE = Path(__file__).resolve().parent


def capture(module_name: str) -> str:
    module = importlib.import_module(f"series.{module_name}.run")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        module.main()
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python3 -m series",
                                     description="Run every part in order, or check or refresh the expected output.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare output with expected_output.txt")
    mode.add_argument("--refresh", action="store_true", help="rewrite expected_output.txt")
    args = parser.parse_args()
    failed = []
    for name, _article, _title in PARTS:
        output = capture(name)
        expected = HERE / name / "expected_output.txt"
        if args.refresh:
            expected.write_text(output, encoding="utf-8")
            print(f"wrote {expected.relative_to(HERE.parent)}")
        elif args.check:
            if expected.read_text(encoding="utf-8") != output:
                failed.append(name)
                sys.stdout.writelines(difflib.unified_diff(
                    expected.read_text(encoding="utf-8").splitlines(True), output.splitlines(True),
                    f"{name}/expected_output.txt", f"{name} (now)"))
            else:
                print(f"ok  {name}")
        else:
            print(output)
    if failed:
        raise SystemExit(f"Output changed for: {', '.join(failed)}")


if __name__ == "__main__":
    main()
