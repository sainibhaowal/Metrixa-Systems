"""
Configuration & Environment Loader for Heidi Engine.
Supports Multi-Provider LLM Routing (llama.cpp, LM Studio, NVIDIA NIM, DeepSeek, Gemini)
and Hybrid Search Routing (Local SearXNG, Native Meta-Search, Tavily API).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env from project root if present
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings(BaseModel):
    """Central runtime configuration for Heidi Engine."""

    project_root: Path = Field(default=PROJECT_ROOT)
    database_path: Path = Field(
        default_factory=lambda: PROJECT_ROOT / os.getenv("DATABASE_PATH", "data/heidi_leads.db")
    )
    export_dir: Path = Field(
        default_factory=lambda: PROJECT_ROOT / os.getenv("EXPORT_DIR", "data/exports")
    )
    gold_set_path: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data" / "gold_set_berlin_30.json"
    )

    # Primary LLM Provider Selection
    # Options: auto_fallback | deepseek | gemini | nvidia_nim | local_llamacpp | lm_studio | deterministic
    default_llm_provider: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_LLM_PROVIDER", "auto_fallback")
    )

    # 1. Local Models (llama.cpp & LM Studio)
    llamacpp_base_url: str = Field(
        default_factory=lambda: os.getenv("LLAMACPP_BASE_URL", "http://127.0.0.1:8080/v1")
    )
    llamacpp_model: str = Field(
        default_factory=lambda: os.getenv("LLAMACPP_MODEL", "qwen2.5-14b-instruct")
    )
    llamacpp_api_key: str = Field(
        default_factory=lambda: os.getenv("LLAMACPP_API_KEY", "local-no-key")
    )

    lmstudio_base_url: str = Field(
        default_factory=lambda: os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    )
    lmstudio_model: str = Field(
        default_factory=lambda: os.getenv("LMSTUDIO_MODEL", "local-model")
    )
    lmstudio_api_key: str = Field(
        default_factory=lambda: os.getenv("LMSTUDIO_API_KEY", "lm-studio")
    )

    # 2. Cloud LLM APIs (DeepSeek, NVIDIA NIM, Gemini)
    deepseek_api_key: str = Field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "").strip()
    )
    deepseek_base_url: str = Field(
        default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    )
    deepseek_model: str = Field(
        default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    )

    nvidia_nim_api_key: str = Field(
        default_factory=lambda: os.getenv("NVIDIA_NIM_API_KEY", "").strip()
    )
    nvidia_nim_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
    )
    nvidia_nim_model: str = Field(
        default_factory=lambda: os.getenv("NVIDIA_NIM_MODEL", "meta/llama-3.3-70b-instruct")
    )

    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip()
    )
    gemini_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
        )
    )
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    )

    # 3. OpenAI & Ollama
    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip()
    )
    openai_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    openai_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    )
    ollama_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2")
    )

    # 3. Search Harness (Local SearXNG + Native Meta-Search + Tavily Fallback)
    searxng_base_url: str = Field(
        default_factory=lambda: os.getenv("SEARXNG_BASE_URL", "http://127.0.0.1:8888").rstrip("/")
    )
    enable_native_metasearch: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_NATIVE_METASEARCH", "true").lower() == "true"
    )
    tavily_api_key: str = Field(
        default_factory=lambda: os.getenv("TAVILY_API_KEY", "").strip()
    )
    tavily_max_calls_per_run: int = Field(
        default_factory=lambda: int(os.getenv("TAVILY_MAX_CALLS_PER_RUN", "400"))
    )

    # 4. Concurrency & Network Settings
    max_concurrent_crawls: int = Field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_CRAWLS", "20"))
    )
    max_subpages_per_company: int = Field(
        default_factory=lambda: int(os.getenv("MAX_SUBPAGES_PER_COMPANY", "5"))
    )
    http_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_SECONDS", "15.0"))
    )
    enable_dns_mx_check: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_DNS_MX_CHECK", "true").lower() == "true"
    )

    def ensure_dirs(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)


# Singleton settings instance
settings = Settings()
settings.ensure_dirs()


# ============================================================================
# BERLIN POSTAL CODE (PLZ 10115 - 14199) TO OFFICIAL BEZIRK (DISTRICT) MAP
# ============================================================================

BERLIN_DISTRICTS: List[str] = [
    "Mitte",
    "Friedrichshain-Kreuzberg",
    "Pankow",
    "Charlottenburg-Wilmersdorf",
    "Spandau",
    "Steglitz-Zehlendorf",
    "Tempelhof-Schöneberg",
    "Neukölln",
    "Treptow-Köpenick",
    "Marzahn-Hellersdorf",
    "Lichtenberg",
    "Reinickendorf",
]


def is_valid_berlin_plz(plz: Optional[str]) -> bool:
    """Return True if postal_code is a valid 5-digit Berlin PLZ (10115 to 14199)."""
    if not plz:
        return False
    clean = "".join(ch for ch in str(plz) if ch.isdigit())
    if len(clean) != 5:
        return False
    num = int(clean)
    return 10115 <= num <= 14199


def map_berlin_plz_to_district(plz: Optional[str], fallback_district: Optional[str] = None) -> str:
    """
    Deterministically map a 5-digit Berlin postal code (10115-14199)
    to one of the 12 official Berlin Bezirke (districts).
    """
    if fallback_district:
        for d in BERLIN_DISTRICTS:
            if d.lower() in fallback_district.lower():
                return d

    if not plz:
        return fallback_district or "Berlin (Allgemein)"

    clean = "".join(ch for ch in str(plz) if ch.isdigit())
    if len(clean) != 5:
        return fallback_district or "Berlin (Allgemein)"

    num = int(clean)
    if not (10115 <= num <= 14199):
        return fallback_district or "Umland / Brandenburg"

    # Official Berlin PLZ range mapping to the 12 Bezirke
    if 10115 <= num <= 10179 or 10551 <= num <= 10559 or 13347 <= num <= 13359:
        return "Mitte"
    if 10243 <= num <= 10249 or 10961 <= num <= 10999:
        return "Friedrichshain-Kreuzberg"
    if 10405 <= num <= 10439 or 13086 <= num <= 13189:
        return "Pankow"
    if 10315 <= num <= 10369 or 13051 <= num <= 13059:
        return "Lichtenberg"
    if 10585 <= num <= 10719 or 14050 <= num <= 14059 or 14193 <= num <= 14199:
        return "Charlottenburg-Wilmersdorf"
    if 10777 <= num <= 10829 or 12099 <= num <= 12109 or 12277 <= num <= 12309:
        return "Tempelhof-Schöneberg"
    if 12043 <= num <= 12059 or 12347 <= num <= 12359:
        return "Neukölln"
    if 12157 <= num <= 12249 or 14109 <= num <= 14169:
        return "Steglitz-Zehlendorf"
    if 12435 <= num <= 12589:
        return "Treptow-Köpenick"
    if 12619 <= num <= 12689:
        return "Marzahn-Hellersdorf"
    if 13403 <= num <= 13509:
        return "Reinickendorf"
    if 13581 <= num <= 13599 or 14089 == num:
        return "Spandau"

    return "Mitte"

