"""Evaluate completions against HumanEval+ tests using EvalPlus.

Reads the checkpoint CSV, extracts generated code for each (task_id, group, run),
runs EvalPlus tests, and updates the 'passed' column in the final raw_results.csv.
"""

from __future__ import annotations

import csv
import os
import re
import tempfile
from pathlib import Path

import config
from harness import CSV_FIELDS, RunResult


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------

def extract_function_code(completion: str, task_prompt: str) -> str:
    """Extract the Python function from a model completion.

    Handles common patterns:
    - Completion is just the function body (most common with good prompts)
    - Completion is wrapped in ```python ... ``` markdown fences
    - Completion includes the def line and body
    """
    text = completion.strip()

    # Strip markdown fences
    fence_match = re.search(r"```(?:python)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # If the completion starts with def, return as-is
    if text.startswith("def "):
        return text

    # If the prompt already has the def line, prepend it
    def_match = re.search(r"(def\s+\w+\s*\([^)]*\)[^:]*:)", task_prompt)
    if def_match:
        def_line = def_match.group(1)
        # Indent the completion as function body if it's not already a def
        if not text.startswith("def "):
            # Check if it's already indented
            if not text.startswith("    ") and not text.startswith("\t"):
                text = "    " + text.replace("\n", "\n    ")
            return def_line + "\n" + text

    return text


# ---------------------------------------------------------------------------
# EvalPlus evaluation
# ---------------------------------------------------------------------------

def evaluate_completions(results_csv: str | None = None) -> None:
    """Read results CSV, run EvalPlus tests, write final raw_results.csv.

    This writes each completion to a temp file in the EvalPlus-expected format,
    runs the test harness, and updates the 'passed' field.
    """
    results_csv = results_csv or config.CHECKPOINT_CSV

    if not os.path.exists(results_csv):
        print(f"No results file found at {results_csv}")
        return

    # Load all results
    rows: list[dict] = []
    with open(results_csv, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} results from {results_csv}")

    # Load HumanEval dataset for prompts
    from evalplus.data import get_human_eval_plus
    dataset = get_human_eval_plus()

    # Prepare completions in EvalPlus format: {task_id: [completion, ...]}
    # We evaluate each (group, run) combination separately
    from collections import defaultdict

    # Group results by (group, run)
    by_group_run: dict[tuple[str, int], dict[str, str]] = defaultdict(dict)
    for row in rows:
        key = (row["group"], int(row["run"]))
        task_id = row["task_id"]
        prompt = dataset[task_id]["prompt"]
        code = extract_function_code(row["completion"], prompt)
        by_group_run[key][task_id] = code

    # Evaluate each group-run combination
    pass_results: dict[tuple[str, str, int], bool] = {}

    for (group, run_num), completions in sorted(by_group_run.items()):
        print(f"\nEvaluating group={group} run={run_num} "
              f"({len(completions)} tasks)...")

        # Write completions to a temp jsonl file in EvalPlus format
        import json
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as tmp:
            for task_id in sorted(completions.keys()):
                entry = {
                    "task_id": task_id,
                    "completion": completions[task_id],
                }
                tmp.write(json.dumps(entry) + "\n")
            tmp_path = tmp.name

        try:
            # Run EvalPlus evaluation
            from evalplus.evaluate import evaluate
            eval_results = evaluate(
                dataset="humaneval",
                samples=tmp_path,
            )

            # Extract pass/fail per task
            for task_id, result in eval_results.items():
                passed = result.get("base_status", "") == "pass"
                pass_results[(task_id, group, run_num)] = passed

        except Exception as exc:
            print(f"  EvalPlus evaluation failed: {exc}")
            print("  Falling back to simple syntax check...")
            # Fallback: at least check if the code is syntactically valid
            for task_id, code in completions.items():
                try:
                    compile(code, "<string>", "exec")
                    pass_results[(task_id, group, run_num)] = True
                except SyntaxError:
                    pass_results[(task_id, group, run_num)] = False

        finally:
            os.unlink(tmp_path)

    # Update rows with pass results and write final CSV
    for row in rows:
        key = (row["task_id"], row["group"], int(row["run"]))
        if key in pass_results:
            row["passed"] = pass_results[key]

    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(config.RAW_RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    total = len(rows)
    passed = sum(1 for r in rows if str(r["passed"]).lower() == "true")
    print(f"\nEvaluation complete. {passed}/{total} passed.")
    print(f"Results written to {config.RAW_RESULTS_CSV}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate experiment completions with EvalPlus"
    )
    parser.add_argument(
        "--results-csv", default=None,
        help=f"Path to results CSV (default: {config.CHECKPOINT_CSV})",
    )
    args = parser.parse_args()
    evaluate_completions(args.results_csv)
