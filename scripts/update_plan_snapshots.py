"""Explicitly regenerate audited plan baselines; never invoked by pytest."""

import argparse
import json
import runpy
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="replace fixtures after reviewing behavior changes")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    helpers = runpy.run_path(str(root / "tests/test_resource_optimization.py"))
    destination = root / "tests/fixtures/resource_plan_digests.json"
    previous = json.loads(destination.read_text(encoding="utf-8"))
    current = {}
    for key in previous:
        plan = helpers["capture_plan"](key)
        helpers["assert_plan_invariants"](plan)
        current[key] = helpers["plan_digest"](plan)
    print(f"{sum(previous[key] != value for key, value in current.items())}/{len(current)} baselines differ")
    if args.write:
        destination.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
