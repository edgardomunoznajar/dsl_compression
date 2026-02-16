"""DSL schema definitions and preambles for the three DSL variants (B1, B2, B3).

Each preamble includes the schema grammar plus 1-2 few-shot examples so the
model understands the format before receiving a task-specific DSL prompt.
"""

# ---------------------------------------------------------------------------
# Variant B1 — Minimal
# ---------------------------------------------------------------------------

B1_PREAMBLE = """\
You are a Python code generator. Below is a compact DSL that specifies a \
function to implement. Write ONLY the Python function (including the def line). \
No explanations.

DSL syntax:
  FUNC <name>(<params>) -> <return_type>: <one-line spec>
    EX: <input> => <expected_output>

Example DSL prompt and expected response:

DSL:
FUNC add(a, b) -> int: return sum of a and b
  EX: (2, 3) => 5

Response:
def add(a: int, b: int) -> int:
    return a + b

DSL:
FUNC is_even(n) -> bool: check if n is even
  EX: (4) => True
  EX: (3) => False

Response:
def is_even(n: int) -> bool:
    return n % 2 == 0
"""

# ---------------------------------------------------------------------------
# Variant B2 — Standard
# ---------------------------------------------------------------------------

B2_PREAMBLE = """\
You are a Python code generator. Below is a compact DSL that specifies a \
function to implement. Write ONLY the Python function (including the def line). \
No explanations.

DSL syntax:
  FUNC <name>(<params>) -> <return_type>
    IN: <param>: <type> [constraints]
    OUT: <type> [description]
    RULE: <compact logic rule>
    EDGE: <edge case handling>
    EX: <input> => <expected_output>

Example DSL prompt and expected response:

DSL:
FUNC add(a, b) -> int
  IN: a: int, b: int
  OUT: int — sum of a and b
  RULE: return a + b
  EDGE: negative numbers handled normally
  EX: (2, 3) => 5

Response:
def add(a: int, b: int) -> int:
    return a + b

DSL:
FUNC is_even(n) -> bool
  IN: n: int
  OUT: bool — True if n is even
  RULE: n mod 2 == 0
  EDGE: works for negative ints
  EX: (4) => True
  EX: (3) => False

Response:
def is_even(n: int) -> bool:
    return n % 2 == 0
"""

# ---------------------------------------------------------------------------
# Variant B3 — Verbose
# ---------------------------------------------------------------------------

B3_PREAMBLE = """\
You are a Python code generator. Below is a compact DSL that specifies a \
function to implement. Write ONLY the Python function (including the def line). \
No explanations.

DSL syntax:
  FUNC <name>(<params>) -> <return_type>
    IN: <param>: <type> [constraints]
    OUT: <type> [description]
    RULE: <compact logic rule>
    EDGE: <edge case handling>
    HINT: <implementation suggestion>
    CONTEXT: <domain background>
    EX: <input> => <expected_output>

Example DSL prompt and expected response:

DSL:
FUNC add(a, b) -> int
  IN: a: int, b: int
  OUT: int — sum of a and b
  RULE: return a + b
  EDGE: negative numbers handled normally
  HINT: single return statement
  CONTEXT: basic arithmetic
  EX: (2, 3) => 5

Response:
def add(a: int, b: int) -> int:
    return a + b
"""

# ---------------------------------------------------------------------------
# Group A — Baseline (natural language, no preamble needed by the harness,
# but we define the system prompt for consistency)
# ---------------------------------------------------------------------------

GROUP_A_SYSTEM = """\
You are a Python code generator. Write ONLY the Python function (including \
the def line). No explanations.\
"""

# ---------------------------------------------------------------------------
# Registry for programmatic access
# ---------------------------------------------------------------------------

PREAMBLES = {
    "B1": B1_PREAMBLE,
    "B2": B2_PREAMBLE,
    "B3": B3_PREAMBLE,
}

SYSTEM_PROMPTS = {
    "A": GROUP_A_SYSTEM,
    "B1": B1_PREAMBLE,
    "B2": B2_PREAMBLE,
    "B3": B3_PREAMBLE,
}
