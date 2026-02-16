#!/usr/bin/env bash
#
# DSL Token Compression Experiment — one-command runner
#
# Usage:
#   ./run.sh                    # full experiment (1,968 API calls)
#   ./run.sh --dry-run          # verify prompts without API calls
#   ./run.sh --tasks HumanEval/0 HumanEval/1  # subset
#
# Prerequisites:
#   - Python 3.10+
#   - .env file with DEEPSEEK_API_KEY set
#
# The experiment checkpoints after every API call, so you can safely
# Ctrl-C and re-run to resume from where you left off.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Check .env ──────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example and set your API key:"
    echo "  cp .env.example .env"
    echo "  # edit .env → DEEPSEEK_API_KEY=sk-..."
    exit 1
fi

if ! grep -q "DEEPSEEK_API_KEY=sk-" .env; then
    echo "ERROR: DEEPSEEK_API_KEY not set in .env"
    exit 1
fi

# ── Install deps ────────────────────────────────────────────────────
echo "==> Installing dependencies..."
pip install -q -r requirements.txt

# ── Step 1: Run experiment ──────────────────────────────────────────
echo ""
echo "==> Step 1/3: Running experiment harness..."
echo "    (Checkpoints to results/checkpoint.csv — safe to interrupt and resume)"
echo ""
python harness.py "$@"

# If --dry-run was passed, stop here
if [[ "${*}" == *"--dry-run"* ]]; then
    echo ""
    echo "Dry run complete. No API calls made."
    exit 0
fi

# ── Step 2: Evaluate completions ────────────────────────────────────
echo ""
echo "==> Step 2/3: Evaluating completions with EvalPlus..."
echo ""
python evaluate.py

# ── Step 3: Analyze results ─────────────────────────────────────────
echo ""
echo "==> Step 3/3: Computing summary statistics..."
echo ""
python analyze.py

echo ""
echo "==> Done! Results:"
echo "    results/raw_results.csv   — per-task, per-group, per-run data"
echo "    results/summary.json      — aggregated stats + variant comparison"
