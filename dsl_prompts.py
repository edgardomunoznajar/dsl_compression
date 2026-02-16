"""Translate HumanEval tasks into DSL prompts for variants B1, B2, B3.

Strategy: Rather than manually translating 164 × 3 = 492 prompts, we use a
*programmatic translator* that parses the structured parts of each HumanEval
prompt (function signature, docstring, examples) and reformats them into the
three DSL grammars.  For fields that require semantic compression (RULE, EDGE,
HINT, CONTEXT), we extract what we can from the docstring and keep the rest
terse.  This is deterministic and reproducible.

At experiment time the harness can also optionally use a one-time LLM call to
produce higher-quality DSL translations, but the default path is pure Python
parsing — no LLM in the loop for prompt construction.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Parsed representation of a HumanEval task
# ---------------------------------------------------------------------------

@dataclass
class ParsedTask:
    task_id: str
    func_name: str
    params: str          # e.g. "numbers: List[float], threshold: float"
    return_type: str     # e.g. "bool"
    docstring: str       # full docstring text
    description: str     # first sentence / paragraph of docstring
    examples: list[str] = field(default_factory=list)  # ">>> ..." lines
    prompt: str = ""     # original full prompt text


# ---------------------------------------------------------------------------
# Parser: HumanEval prompt -> ParsedTask
# ---------------------------------------------------------------------------

_SIG_RE = re.compile(
    r"def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^:]+))?\s*:"
)

_EXAMPLE_RE = re.compile(r">>>.*")


def parse_humaneval_prompt(task_id: str, prompt: str) -> ParsedTask:
    """Parse a HumanEval prompt string into structured fields."""
    # Extract function signature
    sig_match = _SIG_RE.search(prompt)
    if not sig_match:
        # Fallback: return minimal parsed task
        return ParsedTask(
            task_id=task_id,
            func_name="unknown",
            params="",
            return_type="Any",
            docstring=prompt,
            description=prompt.strip(),
            prompt=prompt,
        )

    func_name = sig_match.group(1)
    params = sig_match.group(2).strip()
    return_type = (sig_match.group(3) or "Any").strip()

    # Extract docstring
    docstring = ""
    doc_match = re.search(r'"""(.*?)"""', prompt, re.DOTALL)
    if not doc_match:
        doc_match = re.search(r"'''(.*?)'''", prompt, re.DOTALL)
    if doc_match:
        docstring = doc_match.group(1).strip()

    # Split docstring into description vs examples
    lines = docstring.split("\n")
    desc_lines = []
    examples = []
    in_examples = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">>>") or (in_examples and stripped and not stripped.startswith(">>>")):
            in_examples = True
            examples.append(stripped)
        elif not in_examples:
            desc_lines.append(stripped)

    description = " ".join(l for l in desc_lines if l).strip()

    return ParsedTask(
        task_id=task_id,
        func_name=func_name,
        params=params,
        return_type=return_type,
        docstring=docstring,
        description=description,
        examples=examples,
        prompt=prompt,
    )


# ---------------------------------------------------------------------------
# DSL formatters
# ---------------------------------------------------------------------------

def _compress_description(desc: str, max_chars: int = 80) -> str:
    """Shorten a natural language description to fit on one line."""
    # Remove common filler
    desc = desc.replace("Return ", "").replace("return ", "")
    desc = desc.replace("Check if ", "").replace("check if ", "")
    desc = desc.replace("Write a function that ", "")
    desc = desc.replace("Given ", "given ")
    if len(desc) <= max_chars:
        return desc
    return desc[:max_chars].rsplit(" ", 1)[0] + "..."


def _format_examples_dsl(examples: list[str]) -> str:
    """Convert >>> example lines into DSL EX: lines."""
    ex_lines = []
    i = 0
    while i < len(examples):
        line = examples[i]
        if line.startswith(">>>"):
            call = line.lstrip("> ").strip()
            # Next line (if exists and isn't >>>) is the expected output
            if i + 1 < len(examples) and not examples[i + 1].startswith(">>>"):
                expected = examples[i + 1].strip()
                ex_lines.append(f"  EX: {call} => {expected}")
                i += 2
            else:
                ex_lines.append(f"  EX: {call}")
                i += 1
        else:
            i += 1
    return "\n".join(ex_lines)


def _strip_param_types(params: str) -> str:
    """Remove type annotations from param string: 'a: int, b: str' -> 'a, b'."""
    parts = []
    for p in params.split(","):
        p = p.strip()
        name = p.split(":")[0].strip().split("=")[0].strip()
        if name:
            parts.append(name)
    return ", ".join(parts)


def to_b1(task: ParsedTask) -> str:
    """Minimal DSL: signature + one-line spec + examples."""
    short_desc = _compress_description(task.description)
    bare_params = _strip_param_types(task.params)
    result = f"FUNC {task.func_name}({bare_params}) -> {task.return_type}: {short_desc}"
    ex = _format_examples_dsl(task.examples)
    if ex:
        result += "\n" + ex
    return result


def to_b2(task: ParsedTask) -> str:
    """Standard DSL: typed inputs, output, rule, edge cases, examples."""
    bare_params = _strip_param_types(task.params)
    short_desc = _compress_description(task.description)
    lines = [
        f"FUNC {task.func_name}({bare_params}) -> {task.return_type}",
        f"  IN: {task.params}" if task.params else None,
        f"  OUT: {task.return_type} — {short_desc}",
        f"  RULE: {short_desc}",
    ]
    # Filter None
    lines = [l for l in lines if l is not None]

    ex = _format_examples_dsl(task.examples)
    if ex:
        lines.append(ex)
    return "\n".join(lines)


def to_b3(task: ParsedTask) -> str:
    """Verbose DSL: standard + HINT + CONTEXT."""
    bare_params = _strip_param_types(task.params)
    short_desc = _compress_description(task.description)
    lines = [
        f"FUNC {task.func_name}({bare_params}) -> {task.return_type}",
        f"  IN: {task.params}" if task.params else None,
        f"  OUT: {task.return_type} — {short_desc}",
        f"  RULE: {short_desc}",
        f"  EDGE: handle empty input gracefully",
        f"  HINT: straightforward implementation",
        f"  CONTEXT: general-purpose utility",
    ]
    lines = [l for l in lines if l is not None]

    ex = _format_examples_dsl(task.examples)
    if ex:
        lines.append(ex)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DSL_FORMATTERS = {
    "B1": to_b1,
    "B2": to_b2,
    "B3": to_b3,
}


def build_prompt(task: ParsedTask, group: str) -> str:
    """Build the user-message prompt for a given group.

    For Group A, returns the original HumanEval prompt.
    For B1/B2/B3, returns the DSL-formatted prompt.
    """
    if group == "A":
        return task.prompt
    formatter = DSL_FORMATTERS[group]
    return formatter(task)


def load_humaneval_tasks() -> list[ParsedTask]:
    """Load HumanEval tasks from the evalplus package and parse them."""
    from evalplus.data import get_human_eval_plus

    dataset = get_human_eval_plus()
    tasks = []
    for task_id, data in sorted(dataset.items()):
        prompt = data["prompt"]
        parsed = parse_humaneval_prompt(task_id, prompt)
        tasks.append(parsed)
    return tasks
