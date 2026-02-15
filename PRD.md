# PRD: DSL Token Compression Experiment

## 1. Overview

**Project:** DSL Token Compression Experiment
**Author:** Edgardo Munoz Najar
**Status:** Draft
**Date:** 2026-02-15

### Problem Statement

LLM API costs scale with token usage. Natural language prompts are verbose by nature — they carry redundancy, filler words, and ambiguity that consume tokens without adding signal. If a structured, compressed Domain-Specific Language (DSL) can convey the same programming intent in fewer tokens while preserving code generation accuracy, it would reduce cost and latency for code-generation workloads.

### Hypothesis

A compact DSL syntax can reduce total token usage (input + output) by 20–40% compared to equivalent natural language prompts when generating Python code, without degrading pass@1 correctness rates.

---

## 2. Goals & Non-Goals

### Goals

- **G1:** Quantify the token reduction (input and output) achieved by DSL-compressed prompts vs. natural language prompts on a standardized benchmark (HumanEval, 164 tasks).
- **G2:** Measure whether DSL-compressed prompts maintain comparable pass@1 accuracy against HumanEval unit tests.
- **G3:** Produce a reproducible experimental harness that others can re-run with different models or DSL schemas.
- **G4:** Account for DSL schema preamble cost — amortize it fairly across all tasks so the comparison reflects real-world batch usage.

### Non-Goals

- Optimizing the DSL syntax itself (this experiment tests one fixed schema; iteration is future work).
- Benchmarking multiple models (DeepSeek only for V1; the harness should be model-swappable but only one model is tested).
- Prompt engineering beyond the DSL translation (no chain-of-thought, few-shot, or other prompting tricks).
- Production deployment of the DSL.

---

## 3. Experimental Design

### 3.1 Groups

| Group | Prompt Format | Description |
|-------|--------------|-------------|
| **A (Baseline)** | HumanEval natural language | Original docstring prompts exactly as shipped in OpenAI's HumanEval dataset |
| **B (Treatment)** | DSL-compressed | Same 164 tasks rewritten in a compact DSL, prefixed with a one-time schema preamble |

### 3.2 Independent Variables

- Prompt format (Group A vs. Group B)

### 3.3 Dependent Variables

| Metric | Source | Unit |
|--------|--------|------|
| `input_tokens` | API response `usage.prompt_tokens` | integer |
| `output_tokens` | API response `usage.completion_tokens` | integer |
| `total_tokens` | `input_tokens + output_tokens` | integer |
| `passed` | EvalPlus test harness | boolean |
| `pass@1` | Aggregated from `passed` across runs | float (0–1) |

### 3.4 Controls

- **Model:** DeepSeek (single model, fixed version)
- **Temperature:** 0 (deterministic generation)
- **Runs per task:** 3 (to capture any non-determinism despite temp=0)
- **Max tokens:** Consistent limit across both groups
- **System prompt:** None (or identical if required by the model)

### 3.5 DSL Schema Preamble Accounting

The DSL schema preamble is sent once per session in a real-world scenario but must be included in the experiment for fairness. Cost accounting:

```
amortized_preamble_tokens = preamble_tokens / num_tasks  (164)
group_b_input_tokens = raw_input_tokens + amortized_preamble_tokens
```

Both the raw and amortized figures will be recorded.

---

## 4. DSL Schema Design

### 4.1 Principles

- **Terse:** Eliminate articles, filler words, and verbose type descriptions.
- **Structured:** Use a fixed grammar so the model can parse intent without ambiguity.
- **Self-contained:** The schema preamble defines all syntax so no external docs are needed.

### 4.2 Draft Schema

```
DSL_SCHEMA = """
FUNC <name>(<params>) -> <return_type>
  IN: <param_name>: <type> [constraints]
  OUT: <type> [description]
  RULE: <compact logic rule>
  EDGE: <edge case handling>
  EX: <input> => <output>
"""
```

### 4.3 Example Translation

**Group A (Natural Language):**
```
def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """Check if in given list of numbers, are any two numbers
    closer to each other than given threshold.
    >>> has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3)
    True
    >>> has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05)
    False
    """
```

**Group B (DSL):**
```
FUNC has_close_elements(numbers, threshold) -> bool
  IN: numbers: List[float], threshold: float
  OUT: bool — any pair closer than threshold
  RULE: ∃ i≠j : |numbers[i]-numbers[j]| < threshold
  EX: ([1.0,2.0,3.9,4.0,5.0,2.2], 0.3) => True
  EX: ([1.0,2.0,3.9,4.0,5.0,2.2], 0.05) => False
```

---

## 5. Technical Architecture

### 5.1 Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| LLM API | DeepSeek (OpenAI-compatible endpoint via `openai` SDK) |
| Benchmark | HumanEval (164 tasks) via `evalplus` |
| Test Harness | EvalPlus (`evalplus.evaluate`) |
| Data Output | CSV + JSON |

### 5.2 Project Structure

```
dsl_compression/
├── PRD.md                    # This document
├── README.md                 # Setup & run instructions
├── requirements.txt          # Python dependencies
├── config.py                 # API keys, model params, paths
├── dsl_schema.py             # DSL schema definition + preamble
├── dsl_prompts.py            # HumanEval tasks translated to DSL
├── harness.py                # Main experiment runner
├── evaluate.py               # Test runner using EvalPlus
├── analyze.py                # Stats + summary generation
├── results/
│   ├── raw_results.csv       # Per-task, per-group, per-run results
│   └── summary.json          # Aggregated stats
└── tests/
    └── test_harness.py       # Unit tests for the harness itself
```

### 5.3 Data Pipeline

```
1. Load HumanEval dataset (evalplus)
       │
2. For each task (164):
   ├── Group A: build natural language prompt
   ├── Group B: build DSL prompt + preamble
   │
3. For each group × task × run (164 × 2 × 3 = 984 API calls):
   ├── Send prompt to DeepSeek API
   ├── Record: task_id, group, run, input_tokens, output_tokens, completion
   │
4. Extract generated code from completions
       │
5. Run EvalPlus tests on each completion
   ├── Record: passed (bool)
       │
6. Write raw_results.csv
       │
7. Compute summary stats → summary.json
```

---

## 6. Output Schema

### 6.1 `raw_results.csv`

| Column | Type | Description |
|--------|------|-------------|
| `task_id` | string | HumanEval task ID (e.g., `HumanEval/0`) |
| `group` | string | `A` (natural language) or `B` (DSL) |
| `run` | int | Run number (1–3) |
| `input_tokens` | int | Prompt tokens (from API response) |
| `output_tokens` | int | Completion tokens (from API response) |
| `total_tokens` | int | `input_tokens + output_tokens` |
| `passed` | bool | Whether the generated code passed all EvalPlus tests |
| `completion` | string | Raw model output |
| `latency_ms` | int | Wall-clock time for the API call |

### 6.2 `summary.json`

```json
{
  "group_a": {
    "mean_input_tokens": 0,
    "mean_output_tokens": 0,
    "mean_total_tokens": 0,
    "pass_at_1": 0.0,
    "total_cost_usd": 0.0
  },
  "group_b": {
    "mean_input_tokens": 0,
    "mean_output_tokens": 0,
    "mean_total_tokens": 0,
    "mean_input_tokens_amortized": 0,
    "pass_at_1": 0.0,
    "total_cost_usd": 0.0,
    "preamble_tokens": 0
  },
  "delta": {
    "token_reduction_pct": 0.0,
    "pass_at_1_diff": 0.0,
    "cost_reduction_pct": 0.0
  }
}
```

---

## 7. Success Criteria

| Criterion | Threshold | Priority |
|-----------|-----------|----------|
| Token reduction (Group B vs A) | ≥ 15% reduction in mean total tokens | P0 |
| Correctness preservation | Group B pass@1 within 5 percentage points of Group A | P0 |
| Experiment completes | All 984 API calls succeed, all results recorded | P0 |
| Reproducibility | Harness can be re-run with identical results (temp=0) | P1 |
| Cost accounting | Preamble amortization correctly applied | P1 |

---

## 8. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| DSL confuses the model, tanking pass@1 | Experiment shows DSL is not viable | Medium | Accept as a valid negative result; log failures for analysis |
| DeepSeek API rate limits | Experiment takes too long or fails mid-run | Medium | Add retry logic with exponential backoff; checkpoint progress to CSV incrementally |
| Token counting discrepancy | Inaccurate measurements | Low | Use only API-reported `usage` fields, never local tokenizer estimates |
| Temperature 0 still produces variance | Noisy results | Low | 3 runs per task to detect and quantify variance |
| DSL preamble is too large, erasing savings | Group B shows no benefit | Medium | Measure preamble size upfront; if > 500 tokens, compress the schema |

---

## 9. Milestones

| # | Milestone | Deliverable |
|---|-----------|-------------|
| 1 | Repo scaffold | Project structure, dependencies, config |
| 2 | DSL schema + translations | `dsl_schema.py`, `dsl_prompts.py` with all 164 tasks |
| 3 | Harness implementation | `harness.py` — runs both groups, logs tokens |
| 4 | Evaluation pipeline | `evaluate.py` — runs EvalPlus tests on completions |
| 5 | Analysis & reporting | `analyze.py` — generates CSV + summary stats |
| 6 | Experiment execution | Full run, raw data collected |
| 7 | Results writeup | Summary of findings, token deltas, pass@1 comparison |

---

## 10. Open Questions

1. **DSL schema iteration:** Should we test multiple DSL variants in V1 or fix one and iterate later?
   - *Recommendation:* Fix one for V1. Test variants in V2.

2. **Model selection:** Should we also run against a second model (e.g., Claude, GPT-4) for comparison?
   - *Recommendation:* DeepSeek only for V1. Harness is model-agnostic by design.

3. **Few-shot examples in DSL preamble:** Should the schema include worked examples?
   - *Recommendation:* Yes, 1–2 minimal examples to ground the syntax. Count them in preamble tokens.

4. **Output format enforcement:** Should Group B also instruct the model to output in a specific format?
   - *Recommendation:* No. Both groups should produce raw Python functions. Controlling output format is a separate variable.
