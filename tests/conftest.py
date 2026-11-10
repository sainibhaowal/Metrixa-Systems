"""Keep the entire test session isolated from a developer's database and credentials."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


_TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="metrixa-pytest-")
_TEST_ROOT = Path(_TEST_RUNTIME.name).resolve()

# These values are present before test modules import the app and its global Database.
os.environ["DATABASE_PATH"] = str(_TEST_ROOT / "metrixa_test.db")
os.environ["EXPORT_DIR"] = str(_TEST_ROOT / "exports")
os.environ["METRIXA_ENV_PATH"] = str(_TEST_ROOT / "settings.env")
os.environ["DEFAULT_LLM_PROVIDER"] = "deterministic"
os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://127.0.0.1:3000"
os.environ["ALLOW_PRIVATE_CRAWLER_TARGETS"] = "false"

# Tests must never contact live accounts or incur provider/search costs.
for _key in (
    "GOOGLE_SHEET_ID",
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_SHEETS_WEBHOOK_URL",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "NVIDIA_NIM_API_KEY",
    "TAVILY_API_KEY",
    "GOOGLE_CSE_API_KEY",
    "BRAVE_SEARCH_API_KEY",
):
    os.environ[_key] = ""


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Remove only the isolated temporary test runtime after the suite exits."""
    _TEST_RUNTIME.cleanup()
