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

- Benchmarking multiple models (DeepSeek only for V1; the harness should be model-swappable but only one model is tested).
- Prompt engineering beyond the DSL translation (no chain-of-thought or other prompting tricks — few-shot examples are limited to 1–2 in the schema preamble).
- Production deployment of the DSL.

---

## 3. Experimental Design

### 3.1 Groups

| Group | Prompt Format | Description |
|-------|--------------|-------------|
| **A (Baseline)** | HumanEval natural language | Original docstring prompts exactly as shipped in OpenAI's HumanEval dataset |
| **B1 (Minimal DSL)** | DSL — minimal variant | Bare-bones DSL: function signature + terse one-line spec + examples only |
| **B2 (Standard DSL)** | DSL — standard variant | Full `FUNC/IN/OUT/RULE/EDGE/EX` schema as designed in §4 |
| **B3 (Verbose DSL)** | DSL — verbose variant | Standard schema + additional `HINT` and `CONTEXT` fields for harder tasks |

Each DSL variant has its own schema preamble (with 1–2 few-shot examples) whose token cost is amortized per §3.5.

### 3.2 Independent Variables

- Prompt format (Group A vs. Group B1 vs. B2 vs. B3)

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
- **Max tokens:** Consistent limit across all groups
- **System prompt:** None (or identical if required by the model)
- **Output format:** All groups produce raw Python functions (no structured output instructions)

### 3.5 DSL Schema Preamble Accounting

Each DSL variant's schema preamble (including 1–2 few-shot examples) is sent once per session in a real-world scenario but must be included in the experiment for fairness. Cost accounting per variant:

```
amortized_preamble_tokens = preamble_tokens / num_tasks  (164)
group_bN_input_tokens = raw_input_tokens + amortized_preamble_tokens
```

Both the raw and amortized figures will be recorded for each variant (B1, B2, B3).

---

## 4. DSL Schema Design

### 4.1 Principles

- **Terse:** Eliminate articles, filler words, and verbose type descriptions.
- **Structured:** Use a fixed grammar so the model can parse intent without ambiguity.
- **Self-contained:** The schema preamble defines all syntax so no external docs are needed.

### 4.2 DSL Variants

Three DSL variants will be tested, each with increasing verbosity:

#### Variant B1 — Minimal

Bare-bones: signature, one-line spec, examples only. Smallest preamble.

```
FUNC <name>(<params>) -> <return_type>: <one-line spec>
  EX: <input> => <output>
```

#### Variant B2 — Standard

Full structured schema with typed inputs, rules, and edge cases.

```
FUNC <name>(<params>) -> <return_type>
  IN: <param_name>: <type> [constraints]
  OUT: <type> [description]
  RULE: <compact logic rule>
  EDGE: <edge case handling>
  EX: <input> => <output>
```

#### Variant B3 — Verbose

Standard schema plus `HINT` (implementation guidance) and `CONTEXT` (domain background) fields for harder tasks.

```
FUNC <name>(<params>) -> <return_type>
  IN: <param_name>: <type> [constraints]
  OUT: <type> [description]
  RULE: <compact logic rule>
  EDGE: <edge case handling>
  HINT: <implementation suggestion>
  CONTEXT: <domain background>
  EX: <input> => <output>
```

Each variant's preamble includes 1–2 worked few-shot examples demonstrating the syntax. Preamble tokens are measured and amortized per §3.5.

### 4.3 Example Translation (`has_close_elements`)

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

**Group B1 (Minimal DSL):**
```
FUNC has_close_elements(numbers, threshold) -> bool: any pair closer than threshold
  EX: ([1.0,2.0,3.9,4.0,5.0,2.2], 0.3) => True
  EX: ([1.0,2.0,3.9,4.0,5.0,2.2], 0.05) => False
```

**Group B2 (Standard DSL):**
```
FUNC has_close_elements(numbers, threshold) -> bool
  IN: numbers: List[float], threshold: float
  OUT: bool — any pair closer than threshold
  RULE: ∃ i≠j : |numbers[i]-numbers[j]| < threshold
  EX: ([1.0,2.0,3.9,4.0,5.0,2.2], 0.3) => True
  EX: ([1.0,2.0,3.9,4.0,5.0,2.2], 0.05) => False
```

**Group B3 (Verbose DSL):**
```
FUNC has_close_elements(numbers, threshold) -> bool
  IN: numbers: List[float], threshold: float
  OUT: bool — any pair closer than threshold
  RULE: ∃ i≠j : |numbers[i]-numbers[j]| < threshold
  EDGE: empty list → False; single element → False
  HINT: O(n²) pairwise comparison acceptable for HumanEval input sizes
  CONTEXT: proximity check, common in clustering/dedup
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
├── dsl_schema.py             # DSL schema definitions + preambles (B1, B2, B3)
├── dsl_prompts.py            # HumanEval tasks translated to DSL (all 3 variants)
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
   ├── Group A:  build natural language prompt
   ├── Group B1: build minimal DSL prompt + preamble
   ├── Group B2: build standard DSL prompt + preamble
   ├── Group B3: build verbose DSL prompt + preamble
   │
3. For each group × task × run (164 × 4 × 3 = 1,968 API calls):
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
| `group` | string | `A` (natural language), `B1` (minimal DSL), `B2` (standard DSL), or `B3` (verbose DSL) |
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
  "group_b1": {
    "mean_input_tokens": 0,
    "mean_output_tokens": 0,
    "mean_total_tokens": 0,
    "mean_input_tokens_amortized": 0,
    "pass_at_1": 0.0,
    "total_cost_usd": 0.0,
    "preamble_tokens": 0
  },
  "group_b2": { "...same structure as b1..." },
  "group_b3": { "...same structure as b1..." },
  "deltas": {
    "b1_vs_a": {
      "token_reduction_pct": 0.0,
      "pass_at_1_diff": 0.0,
      "cost_reduction_pct": 0.0
    },
    "b2_vs_a": { "...same..." },
    "b3_vs_a": { "...same..." }
  },
  "best_variant": "b1|b2|b3"
}
```

---

## 7. Success Criteria

| Criterion | Threshold | Priority |
|-----------|-----------|----------|
| Token reduction (any B variant vs A) | ≥ 15% reduction in mean total tokens for at least one variant | P0 |
| Correctness preservation | Best DSL variant pass@1 within 5 percentage points of Group A | P0 |
| Experiment completes | All 1,968 API calls succeed, all results recorded | P0 |
| Variant comparison | Identify which DSL variant (B1/B2/B3) offers the best token/accuracy tradeoff | P1 |
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
| 2 | DSL schemas + translations | `dsl_schema.py` (3 variants), `dsl_prompts.py` with all 164 tasks × 3 variants |
| 3 | Harness implementation | `harness.py` — runs both groups, logs tokens |
| 4 | Evaluation pipeline | `evaluate.py` — runs EvalPlus tests on completions |
| 5 | Analysis & reporting | `analyze.py` — generates CSV + summary stats |
| 6 | Experiment execution | Full run, raw data collected |
| 7 | Results writeup | Summary of findings, token deltas, pass@1 comparison |

---

## 10. Resolved Design Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | **DSL variants** | Test 2–3 variants in V1 (B1 minimal, B2 standard, B3 verbose) | Gives richer data in one pass — we learn which compression level works best without a follow-up experiment |
| 2 | **Model selection** | DeepSeek only for V1 | Keeps experiment focused and cheaper. Harness is model-agnostic; adding models is future work |
| 3 | **Few-shot in preamble** | Yes, 1–2 worked examples per schema variant | Grounds the model on the DSL syntax. Token cost included in preamble amortization |
| 4 | **Output format** | Same across all groups — raw Python functions | Only the input format varies. Output format is a controlled variable, not an independent one |
