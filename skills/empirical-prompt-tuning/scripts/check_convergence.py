#!/usr/bin/env python3
"""
Check whether iterations have converged per the SKILL.md criteria.

Usage:
    python check_convergence.py <iterations.json>

Input format:
    {
      "iterations": [
        {
          "iter": 1,
          "scenarios": [
            {
              "scenario": "A",
              "accuracy": 0.60,
              "tool_uses": 5,
              "duration_ms": 20000,
              "new_unclear_points": 3
            },
            {"scenario": "B", ...}
          ]
        },
        {"iter": 2, ...}
      ],
      "thresholds": {
        "accuracy_delta_pp": 3,
        "tool_uses_delta_pct": 10,
        "duration_delta_pct": 15,
        "consecutive_passes_required": 2
      }
    }

Thresholds default to SKILL.md recommended values if omitted.

Exit codes:
    0 = converged (stop iterating)
    1 = not converged (keep iterating)
    2 = insufficient data (need more iterations)
    3 = invalid input
"""

import json
import sys
from typing import Any

DEFAULT_THRESHOLDS = {
    "accuracy_delta_pp": 3,            # +3pp以下なら飽和
    "tool_uses_delta_pct": 10,         # ±10%以内
    "duration_delta_pct": 15,          # ±15%以内
    "consecutive_passes_required": 2,  # 連続2回クリアで収束
}


def aggregate_iteration(iteration: dict[str, Any]) -> dict[str, float]:
    """Collapse multiple scenarios in an iteration to a single summary."""
    scens = iteration.get("scenarios", [])
    if not scens:
        return {}
    n = len(scens)
    return {
        "accuracy": sum(s.get("accuracy", 0) for s in scens) / n,
        "tool_uses": sum(s.get("tool_uses", 0) for s in scens) / n,
        "duration_ms": sum(s.get("duration_ms", 0) for s in scens) / n,
        "new_unclear_points": sum(s.get("new_unclear_points", 0) for s in scens),
    }


def check_iteration_pair(
    prev: dict[str, float], curr: dict[str, float], thresholds: dict[str, float]
) -> tuple[bool, list[str]]:
    """Check if curr iteration satisfies convergence criteria vs prev."""
    reasons = []
    ok = True

    # New unclear points must be 0
    if curr["new_unclear_points"] > 0:
        ok = False
        reasons.append(
            f"new unclear points = {curr['new_unclear_points']} (required: 0)"
        )

    # Accuracy delta (in percentage points)
    acc_delta_pp = (curr["accuracy"] - prev["accuracy"]) * 100
    if acc_delta_pp > thresholds["accuracy_delta_pp"]:
        ok = False
        reasons.append(
            f"accuracy still improving: +{acc_delta_pp:.1f}pp "
            f"(threshold: +{thresholds['accuracy_delta_pp']}pp)"
        )

    # Tool uses delta (percent change)
    if prev["tool_uses"] > 0:
        tu_delta_pct = abs((curr["tool_uses"] - prev["tool_uses"]) / prev["tool_uses"]) * 100
        if tu_delta_pct > thresholds["tool_uses_delta_pct"]:
            ok = False
            reasons.append(
                f"tool_uses volatile: ±{tu_delta_pct:.1f}% "
                f"(threshold: ±{thresholds['tool_uses_delta_pct']}%)"
            )

    # Duration delta (percent change)
    if prev["duration_ms"] > 0:
        dur_delta_pct = abs((curr["duration_ms"] - prev["duration_ms"]) / prev["duration_ms"]) * 100
        if dur_delta_pct > thresholds["duration_delta_pct"]:
            ok = False
            reasons.append(
                f"duration volatile: ±{dur_delta_pct:.1f}% "
                f"(threshold: ±{thresholds['duration_delta_pct']}%)"
            )

    if ok:
        reasons.append("all convergence criteria met")
    return ok, reasons


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(3)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    iters = data.get("iterations", [])
    thresholds = {**DEFAULT_THRESHOLDS, **data.get("thresholds", {})}
    required = thresholds["consecutive_passes_required"]

    if len(iters) < required + 1:
        print(
            f"INSUFFICIENT DATA: have {len(iters)} iteration(s), "
            f"need at least {required + 1} to check {required} consecutive passes.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Aggregate each iteration
    aggregated = [(it["iter"], aggregate_iteration(it)) for it in iters]

    # Scan from oldest to newest, tracking consecutive passes
    passes_in_a_row = 0
    history = []
    for i in range(1, len(aggregated)):
        iter_num, curr = aggregated[i]
        _, prev = aggregated[i - 1]
        ok, reasons = check_iteration_pair(prev, curr, thresholds)
        history.append({"iter": iter_num, "pass": ok, "reasons": reasons})
        if ok:
            passes_in_a_row += 1
        else:
            passes_in_a_row = 0

    # Print history
    print("=" * 60)
    print("Convergence Check")
    print("=" * 60)
    for h in history:
        status = "✓ PASS" if h["pass"] else "✗ FAIL"
        print(f"Iter {h['iter']}: {status}")
        for r in h["reasons"]:
            print(f"   - {r}")
    print()

    # Verdict
    if passes_in_a_row >= required:
        print(f"CONVERGED: {passes_in_a_row} consecutive pass(es). "
              f"Stop iterating (run hold-out check for over-fitting).")
        # Emit machine-readable summary
        print(json.dumps({
            "converged": True,
            "consecutive_passes": passes_in_a_row,
            "required": required,
        }))
        sys.exit(0)
    else:
        remaining = required - passes_in_a_row
        print(f"NOT CONVERGED: {passes_in_a_row}/{required} consecutive passes. "
              f"{remaining} more needed.")
        print(json.dumps({
            "converged": False,
            "consecutive_passes": passes_in_a_row,
            "required": required,
            "remaining": remaining,
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
