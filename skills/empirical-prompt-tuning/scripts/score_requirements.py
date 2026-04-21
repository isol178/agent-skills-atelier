#!/usr/bin/env python3
"""
Score requirements from a judgment JSON file.

Usage:
    python score_requirements.py <judgment.json>
    cat judgment.json | python score_requirements.py -

Input format (single scenario):
    {
      "scenario": "A",
      "requirements": [
        {"id": 1, "critical": true, "text": "...", "judgment": "pass"},
        {"id": 2, "critical": false, "text": "...", "judgment": "partial"},
        {"id": 3, "critical": false, "text": "...", "judgment": "fail"}
      ]
    }

Input format (multiple scenarios):
    {
      "scenarios": [
        {"scenario": "A", "requirements": [...]},
        {"scenario": "B", "requirements": [...]}
      ]
    }

Judgment values: "pass" (1.0) | "partial" (0.5) | "fail" (0.0)

Outcome rules:
    - PASS: all [critical] items have judgment="pass" (partial counts as fail for critical)
    - FAIL: otherwise
"""

import json
import sys
from typing import Any

SCORE_MAP = {"pass": 1.0, "partial": 0.5, "fail": 0.0}


def score_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Score a single scenario's requirements."""
    reqs = scenario.get("requirements", [])
    if not reqs:
        return {
            "scenario": scenario.get("scenario", "?"),
            "error": "no requirements provided",
        }

    # Validate judgments
    for r in reqs:
        j = r.get("judgment")
        if j not in SCORE_MAP:
            return {
                "scenario": scenario.get("scenario", "?"),
                "error": f"invalid judgment '{j}' on item {r.get('id', '?')}"
                f" (must be one of: pass, partial, fail)",
            }

    # Validate at least one critical item
    critical_items = [r for r in reqs if r.get("critical", False)]
    if not critical_items:
        return {
            "scenario": scenario.get("scenario", "?"),
            "error": "no [critical] items found (at least one required)",
        }

    # Compute accuracy
    total_score = sum(SCORE_MAP[r["judgment"]] for r in reqs)
    accuracy = total_score / len(reqs)

    # Compute outcome: all critical items must be "pass" (not partial, not fail)
    outcome_pass = all(r["judgment"] == "pass" for r in critical_items)

    # Identify failing critical items for diagnostics
    critical_failures = [
        {"id": r.get("id"), "text": r.get("text", ""), "judgment": r["judgment"]}
        for r in critical_items
        if r["judgment"] != "pass"
    ]

    return {
        "scenario": scenario.get("scenario", "?"),
        "outcome": "PASS" if outcome_pass else "FAIL",
        "accuracy": round(accuracy, 3),
        "accuracy_percent": f"{accuracy * 100:.1f}%",
        "score_sum": total_score,
        "item_count": len(reqs),
        "critical_count": len(critical_items),
        "critical_failures": critical_failures,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    if path == "-":
        data = json.load(sys.stdin)
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

    # Handle both single-scenario and multi-scenario formats
    if "scenarios" in data:
        results = [score_scenario(s) for s in data["scenarios"]]
    else:
        results = [score_scenario(data)]

    # Print human-readable summary
    print("=" * 60)
    for r in results:
        if "error" in r:
            print(f"Scenario {r['scenario']}: ERROR — {r['error']}")
            continue
        print(f"Scenario {r['scenario']}:")
        print(f"  Outcome:  {r['outcome']}")
        print(f"  Accuracy: {r['accuracy_percent']} "
              f"({r['score_sum']}/{r['item_count']})")
        if r["critical_failures"]:
            print(f"  Critical failures ({len(r['critical_failures'])}):")
            for cf in r["critical_failures"]:
                print(f"    - [id {cf['id']}] ({cf['judgment']}) {cf['text']}")
        print()
    print("=" * 60)

    # Also emit machine-readable JSON on stdout
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))

    # Exit non-zero if any scenario failed (useful for CI)
    if any(r.get("outcome") == "FAIL" or "error" in r for r in results):
        sys.exit(2)


if __name__ == "__main__":
    main()
