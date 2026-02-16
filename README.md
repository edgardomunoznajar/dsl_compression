# DSL Token Compression Experiment

Tests whether compact DSL prompts reduce LLM token usage without degrading code generation accuracy, measured against HumanEval (164 tasks) with DeepSeek.

## Setup

```bash
pip install -r requirements.txt
```

Copy the env template and add your API key:

```bash
cp .env.example .env
# edit .env and set DEEPSEEK_API_KEY
```

## Configuration

All settings live in `config.py` and are loaded from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | Your DeepSeek API key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API endpoint |
| `MODEL_NAME` | `deepseek-coder` | Model to use |

## Running the Experiment

```bash
# Dry run — verify prompt construction without API calls
python harness.py --dry-run

# Run a single task end-to-end
python harness.py --tasks HumanEval/0

# Run specific groups only
python harness.py --groups A B2

# Full experiment (164 tasks × 4 groups × 3 runs = 1,968 API calls)
python harness.py
```

The harness checkpoints to `results/checkpoint.csv` after every API call, so you can resume interrupted runs.

## Evaluation & Analysis

```bash
# Score completions with EvalPlus
python evaluate.py

# Generate summary statistics
python analyze.py
```

Outputs:
- `results/raw_results.csv` — per-task, per-group, per-run results
- `results/summary.json` — aggregated stats and variant comparison

## Experiment Groups

| Group | Format | Description |
|-------|--------|-------------|
| A | Natural language | Original HumanEval docstring prompts |
| B1 | Minimal DSL | Signature + one-line spec + examples |
| B2 | Standard DSL | Typed inputs, rules, edge cases, examples |
| B3 | Verbose DSL | Standard + HINT + CONTEXT fields |

## Tests

```bash
python -m unittest tests.test_harness -v
```
