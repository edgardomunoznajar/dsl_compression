"""Main experiment runner for the DSL Token Compression Experiment.

Iterates over all groups × tasks × runs, calls the DeepSeek API, records
token usage and completions, and checkpoints results incrementally to CSV.
"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from openai import OpenAI

import config
from dsl_prompts import ParsedTask, build_prompt, load_humaneval_tasks
from dsl_schema import SYSTEM_PROMPTS


# ---------------------------------------------------------------------------
# Result record
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    task_id: str
    group: str
    run: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    passed: bool        # filled in by evaluate.py later; default False
    completion: str
    latency_ms: int


CSV_FIELDS = [
    "task_id", "group", "run", "input_tokens", "output_tokens",
    "total_tokens", "passed", "completion", "latency_ms",
]


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

def _make_client() -> OpenAI:
    return OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
    )


def _call_api(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, int, int, int]:
    """Call the LLM and return (completion_text, input_tokens, output_tokens, latency_ms).

    Retries on transient errors with exponential backoff.
    """
    last_exc: Exception | None = None
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            t0 = time.monotonic()
            response = client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=config.TEMPERATURE,
                max_tokens=config.MAX_TOKENS,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)

            usage = response.usage
            text = response.choices[0].message.content or ""
            return text, usage.prompt_tokens, usage.completion_tokens, latency_ms

        except Exception as exc:
            last_exc = exc
            if attempt < config.MAX_RETRIES:
                delay = config.RETRY_BASE_DELAY * (2 ** attempt)
                print(f"  [retry {attempt + 1}/{config.MAX_RETRIES}] "
                      f"{exc!r} — waiting {delay}s")
                time.sleep(delay)

    raise RuntimeError(
        f"API call failed after {config.MAX_RETRIES + 1} attempts"
    ) from last_exc


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _load_checkpoint() -> set[tuple[str, str, int]]:
    """Return set of (task_id, group, run) already completed."""
    done: set[tuple[str, str, int]] = set()
    if os.path.exists(config.CHECKPOINT_CSV):
        with open(config.CHECKPOINT_CSV, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                done.add((row["task_id"], row["group"], int(row["run"])))
    return done


def _append_result(result: RunResult, path: str) -> None:
    """Append a single result row to the CSV, creating headers if needed."""
    write_header = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(result))


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_experiment(
    groups: list[str] | None = None,
    task_ids: list[str] | None = None,
    dry_run: bool = False,
) -> list[RunResult]:
    """Run the full experiment (or a subset).

    Args:
        groups: Which groups to run. Defaults to config.GROUPS.
        task_ids: Subset of task IDs to run. Defaults to all 164.
        dry_run: If True, print what would be done without calling the API.

    Returns:
        List of RunResult objects for the current session.
    """
    groups = groups or config.GROUPS
    client = _make_client()
    tasks = load_humaneval_tasks()

    if task_ids is not None:
        id_set = set(task_ids)
        tasks = [t for t in tasks if t.task_id in id_set]

    checkpoint = _load_checkpoint()
    os.makedirs(config.RESULTS_DIR, exist_ok=True)

    total_calls = len(tasks) * len(groups) * config.RUNS_PER_TASK
    completed = 0
    results: list[RunResult] = []

    print(f"Experiment: {len(tasks)} tasks × {len(groups)} groups × "
          f"{config.RUNS_PER_TASK} runs = {total_calls} API calls")

    for task in tasks:
        for group in groups:
            system_prompt = SYSTEM_PROMPTS[group]
            user_prompt = build_prompt(task, group)

            for run_num in range(1, config.RUNS_PER_TASK + 1):
                key = (task.task_id, group, run_num)
                if key in checkpoint:
                    completed += 1
                    continue

                if dry_run:
                    print(f"  [DRY RUN] {task.task_id} | {group} | run {run_num}")
                    completed += 1
                    continue

                completion, inp_tok, out_tok, latency = _call_api(
                    client, system_prompt, user_prompt
                )
                result = RunResult(
                    task_id=task.task_id,
                    group=group,
                    run=run_num,
                    input_tokens=inp_tok,
                    output_tokens=out_tok,
                    total_tokens=inp_tok + out_tok,
                    passed=False,
                    completion=completion,
                    latency_ms=latency,
                )
                results.append(result)
                _append_result(result, config.CHECKPOINT_CSV)

                completed += 1
                if completed % 50 == 0 or completed == total_calls:
                    print(f"  [{completed}/{total_calls}] "
                          f"{task.task_id} | {group} | run {run_num} | "
                          f"{inp_tok}+{out_tok} tokens | {latency}ms")

    print(f"\nDone. {len(results)} new results written to {config.CHECKPOINT_CSV}")
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the DSL Token Compression Experiment"
    )
    parser.add_argument(
        "--groups", nargs="+", default=None,
        help="Groups to run (default: all). E.g. --groups A B2",
    )
    parser.add_argument(
        "--tasks", nargs="+", default=None,
        help="Specific task IDs to run. E.g. --tasks HumanEval/0 HumanEval/1",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be done without calling the API",
    )
    args = parser.parse_args()

    run_experiment(
        groups=args.groups,
        task_ids=args.tasks,
        dry_run=args.dry_run,
    )
