"""Compute summary statistics from raw_results.csv and write summary.json.

Reads the evaluated results, computes per-group aggregates, deltas between
each DSL variant and the baseline, and identifies the best variant.
"""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import config
from dsl_schema import PREAMBLES


# ---------------------------------------------------------------------------
# Preamble token counting (estimated via whitespace-split approximation;
# the real count comes from the API at experiment time)
# ---------------------------------------------------------------------------

def _estimate_preamble_tokens(text: str) -> int:
    """Rough token estimate: ~1 token per 4 chars for English text."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(raw_csv: str | None = None) -> dict:
    """Analyze raw results and produce summary statistics.

    Returns the summary dict and writes it to summary.json.
    """
    raw_csv = raw_csv or config.RAW_RESULTS_CSV
    if not os.path.exists(raw_csv):
        print(f"No results file at {raw_csv}")
        return {}

    # Load rows
    rows: list[dict] = []
    with open(raw_csv, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    if not rows:
        print("No data rows found.")
        return {}

    # Group rows by group label
    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_group[row["group"]].append(row)

    num_tasks = 164  # HumanEval

    # Compute per-group stats
    def _group_stats(group_rows: list[dict], group: str) -> dict:
        n = len(group_rows)
        if n == 0:
            return {}

        input_tokens = [int(r["input_tokens"]) for r in group_rows]
        output_tokens = [int(r["output_tokens"]) for r in group_rows]
        total_tokens = [int(r["total_tokens"]) for r in group_rows]
        passed = [str(r["passed"]).lower() == "true" for r in group_rows]

        mean_in = sum(input_tokens) / n
        mean_out = sum(output_tokens) / n
        mean_total = sum(total_tokens) / n
        pass_at_1 = sum(passed) / n

        cost = (
            (sum(input_tokens) / 1_000_000) * config.INPUT_COST_PER_M
            + (sum(output_tokens) / 1_000_000) * config.OUTPUT_COST_PER_M
        )

        stats = {
            "n_results": n,
            "mean_input_tokens": round(mean_in, 2),
            "mean_output_tokens": round(mean_out, 2),
            "mean_total_tokens": round(mean_total, 2),
            "pass_at_1": round(pass_at_1, 4),
            "total_cost_usd": round(cost, 6),
        }

        # For DSL groups, add preamble amortization
        if group in PREAMBLES:
            preamble_est = _estimate_preamble_tokens(PREAMBLES[group])
            amortized = preamble_est / num_tasks
            stats["preamble_tokens"] = preamble_est
            stats["amortized_preamble_per_task"] = round(amortized, 2)
            stats["mean_input_tokens_amortized"] = round(
                mean_in + amortized, 2
            )

        return stats

    summary: dict = {}
    for group in ["A", "B1", "B2", "B3"]:
        key = f"group_{group.lower()}"
        summary[key] = _group_stats(by_group.get(group, []), group)

    # Compute deltas
    a_stats = summary.get("group_a", {})
    a_total = a_stats.get("mean_total_tokens", 0)
    a_pass = a_stats.get("pass_at_1", 0)
    a_cost = a_stats.get("total_cost_usd", 0)

    deltas = {}
    best_variant = None
    best_reduction = -float("inf")

    for variant in ["B1", "B2", "B3"]:
        v_key = f"group_{variant.lower()}"
        v_stats = summary.get(v_key, {})
        v_total = v_stats.get("mean_total_tokens", 0)
        v_pass = v_stats.get("pass_at_1", 0)
        v_cost = v_stats.get("total_cost_usd", 0)

        token_reduction = (
            ((a_total - v_total) / a_total * 100) if a_total else 0
        )
        pass_diff = v_pass - a_pass
        cost_reduction = (
            ((a_cost - v_cost) / a_cost * 100) if a_cost else 0
        )

        delta_key = f"{variant.lower()}_vs_a"
        deltas[delta_key] = {
            "token_reduction_pct": round(token_reduction, 2),
            "pass_at_1_diff": round(pass_diff, 4),
            "cost_reduction_pct": round(cost_reduction, 2),
        }

        # Best variant = most token reduction with pass@1 drop ≤ 5pp
        if pass_diff >= -0.05 and token_reduction > best_reduction:
            best_reduction = token_reduction
            best_variant = variant.lower()

    summary["deltas"] = deltas
    summary["best_variant"] = best_variant

    # Write summary
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(config.SUMMARY_JSON, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary written to {config.SUMMARY_JSON}")

    # Print human-readable summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    for group in ["A", "B1", "B2", "B3"]:
        key = f"group_{group.lower()}"
        s = summary.get(key, {})
        if not s:
            continue
        print(f"\nGroup {group}:")
        print(f"  Mean tokens: {s.get('mean_total_tokens', 'N/A')} "
              f"(in: {s.get('mean_input_tokens', 'N/A')}, "
              f"out: {s.get('mean_output_tokens', 'N/A')})")
        print(f"  pass@1:      {s.get('pass_at_1', 'N/A')}")
        print(f"  Cost:        ${s.get('total_cost_usd', 'N/A')}")
        if "preamble_tokens" in s:
            print(f"  Preamble:    ~{s['preamble_tokens']} tokens "
                  f"(amortized: {s['amortized_preamble_per_task']}/task)")

    print(f"\n{'─' * 60}")
    for delta_key, d in deltas.items():
        print(f"  {delta_key}: "
              f"token reduction = {d['token_reduction_pct']}%, "
              f"pass@1 diff = {d['pass_at_1_diff']:+.4f}, "
              f"cost reduction = {d['cost_reduction_pct']}%")

    if best_variant:
        print(f"\n  Best variant: {best_variant.upper()}")
    else:
        print("\n  No variant meets the ≤5pp pass@1 drop threshold.")
    print("=" * 60)

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze experiment results"
    )
    parser.add_argument(
        "--raw-csv", default=None,
        help=f"Path to raw results CSV (default: {config.RAW_RESULTS_CSV})",
    )
    args = parser.parse_args()
    analyze(args.raw_csv)
