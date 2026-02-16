"""Configuration for the DSL Token Compression Experiment."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# --- API ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get(
    "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
)
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-coder")

# --- Experiment ---
TEMPERATURE = 0.0
MAX_TOKENS = 1024
RUNS_PER_TASK = 3
GROUPS = ["A", "B1", "B2", "B3"]

# --- Paths ---
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
RAW_RESULTS_CSV = os.path.join(RESULTS_DIR, "raw_results.csv")
SUMMARY_JSON = os.path.join(RESULTS_DIR, "summary.json")
CHECKPOINT_CSV = os.path.join(RESULTS_DIR, "checkpoint.csv")

# --- Retry ---
MAX_RETRIES = 4
RETRY_BASE_DELAY = 2  # seconds; exponential backoff: 2, 4, 8, 16

# --- Cost (DeepSeek pricing per 1M tokens, update as needed) ---
INPUT_COST_PER_M = 0.14   # USD per 1M input tokens
OUTPUT_COST_PER_M = 0.28  # USD per 1M output tokens
