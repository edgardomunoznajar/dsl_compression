"""Unit tests for the DSL compression experiment modules.

Tests cover:
- DSL prompt parsing and translation
- Code extraction from completions
- Analysis computations
- Config sanity checks
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest

# Adjust path so imports work when running from repo root
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dsl_prompts import (
    ParsedTask,
    _compress_description,
    _format_examples_dsl,
    _strip_param_types,
    build_prompt,
    parse_humaneval_prompt,
    to_b1,
    to_b2,
    to_b3,
)
from dsl_schema import B1_PREAMBLE, B2_PREAMBLE, B3_PREAMBLE, PREAMBLES, SYSTEM_PROMPTS
from evaluate import extract_function_code
import config


# ---------------------------------------------------------------------------
# Sample HumanEval-like prompt for testing
# ---------------------------------------------------------------------------

SAMPLE_PROMPT = '''\
def has_close_elements(numbers: List[float], threshold: float) -> bool:
    """Check if in given list of numbers, are any two numbers
    closer to each other than given threshold.
    >>> has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3)
    True
    >>> has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05)
    False
    """
'''


class TestParseHumanEvalPrompt(unittest.TestCase):

    def test_parses_function_name(self):
        task = parse_humaneval_prompt("HumanEval/0", SAMPLE_PROMPT)
        self.assertEqual(task.func_name, "has_close_elements")

    def test_parses_params(self):
        task = parse_humaneval_prompt("HumanEval/0", SAMPLE_PROMPT)
        self.assertIn("numbers", task.params)
        self.assertIn("threshold", task.params)

    def test_parses_return_type(self):
        task = parse_humaneval_prompt("HumanEval/0", SAMPLE_PROMPT)
        self.assertEqual(task.return_type, "bool")

    def test_parses_description(self):
        task = parse_humaneval_prompt("HumanEval/0", SAMPLE_PROMPT)
        self.assertIn("closer", task.description.lower())

    def test_parses_examples(self):
        task = parse_humaneval_prompt("HumanEval/0", SAMPLE_PROMPT)
        self.assertGreaterEqual(len(task.examples), 2)

    def test_handles_no_return_type(self):
        prompt = 'def foo(x):\n    """Do something.\n    >>> foo(1)\n    2\n    """\n'
        task = parse_humaneval_prompt("test/0", prompt)
        self.assertEqual(task.func_name, "foo")
        self.assertEqual(task.return_type, "Any")


class TestDSLFormatters(unittest.TestCase):

    def setUp(self):
        self.task = parse_humaneval_prompt("HumanEval/0", SAMPLE_PROMPT)

    def test_b1_starts_with_func(self):
        result = to_b1(self.task)
        self.assertTrue(result.startswith("FUNC has_close_elements"))

    def test_b1_has_examples(self):
        result = to_b1(self.task)
        self.assertIn("EX:", result)

    def test_b1_no_type_annotations_in_params(self):
        result = to_b1(self.task)
        first_line = result.split("\n")[0]
        self.assertNotIn("List[float]", first_line.split(":")[0])

    def test_b2_has_in_out_rule(self):
        result = to_b2(self.task)
        self.assertIn("IN:", result)
        self.assertIn("OUT:", result)
        self.assertIn("RULE:", result)

    def test_b3_has_hint_and_context(self):
        result = to_b3(self.task)
        self.assertIn("HINT:", result)
        self.assertIn("CONTEXT:", result)

    def test_b1_shorter_than_b2(self):
        b1 = to_b1(self.task)
        b2 = to_b2(self.task)
        self.assertLess(len(b1), len(b2))

    def test_b2_shorter_than_b3(self):
        b2 = to_b2(self.task)
        b3 = to_b3(self.task)
        self.assertLess(len(b2), len(b3))


class TestBuildPrompt(unittest.TestCase):

    def setUp(self):
        self.task = parse_humaneval_prompt("HumanEval/0", SAMPLE_PROMPT)

    def test_group_a_returns_original(self):
        result = build_prompt(self.task, "A")
        self.assertEqual(result, SAMPLE_PROMPT)

    def test_group_b1_returns_dsl(self):
        result = build_prompt(self.task, "B1")
        self.assertTrue(result.startswith("FUNC"))

    def test_group_b2_returns_dsl(self):
        result = build_prompt(self.task, "B2")
        self.assertIn("IN:", result)

    def test_group_b3_returns_dsl(self):
        result = build_prompt(self.task, "B3")
        self.assertIn("HINT:", result)


class TestHelpers(unittest.TestCase):

    def test_compress_description_short(self):
        desc = "sum of a and b"
        self.assertEqual(_compress_description(desc), "sum of a and b")

    def test_compress_description_long(self):
        desc = "a" * 200
        result = _compress_description(desc)
        self.assertLessEqual(len(result), 84)  # 80 + "..."

    def test_strip_param_types(self):
        self.assertEqual(
            _strip_param_types("a: int, b: str, c: List[float]"),
            "a, b, c",
        )

    def test_strip_param_types_no_types(self):
        self.assertEqual(_strip_param_types("x, y"), "x, y")

    def test_format_examples(self):
        examples = [
            ">>> foo(1)",
            "2",
            ">>> foo(3)",
            "4",
        ]
        result = _format_examples_dsl(examples)
        self.assertIn("EX: foo(1) => 2", result)
        self.assertIn("EX: foo(3) => 4", result)


class TestExtractFunctionCode(unittest.TestCase):

    def test_plain_def(self):
        code = "def foo(x):\n    return x + 1"
        self.assertEqual(extract_function_code(code, ""), code)

    def test_markdown_fenced(self):
        code = "```python\ndef foo(x):\n    return x + 1\n```"
        result = extract_function_code(code, "")
        self.assertTrue(result.startswith("def foo"))

    def test_body_only_with_prompt(self):
        prompt = "def foo(x):"
        completion = "return x + 1"
        result = extract_function_code(completion, prompt)
        self.assertIn("def foo(x):", result)
        self.assertIn("return x + 1", result)


class TestSchemas(unittest.TestCase):

    def test_all_preambles_defined(self):
        self.assertIn("B1", PREAMBLES)
        self.assertIn("B2", PREAMBLES)
        self.assertIn("B3", PREAMBLES)

    def test_all_system_prompts_defined(self):
        for group in ["A", "B1", "B2", "B3"]:
            self.assertIn(group, SYSTEM_PROMPTS)

    def test_preambles_contain_example(self):
        for variant, preamble in PREAMBLES.items():
            self.assertIn("def ", preamble, f"{variant} preamble missing example")

    def test_preambles_not_empty(self):
        for variant, preamble in PREAMBLES.items():
            self.assertGreater(len(preamble), 100, f"{variant} preamble too short")


class TestConfig(unittest.TestCase):

    def test_groups(self):
        self.assertEqual(config.GROUPS, ["A", "B1", "B2", "B3"])

    def test_temperature(self):
        self.assertEqual(config.TEMPERATURE, 0.0)

    def test_runs_per_task(self):
        self.assertEqual(config.RUNS_PER_TASK, 3)

    def test_paths_absolute(self):
        self.assertTrue(os.path.isabs(config.RAW_RESULTS_CSV))


if __name__ == "__main__":
    unittest.main()
