"""
Configuration & Environment Loader for Metrixa Engine.
Supports Multi-Provider LLM Routing (llama.cpp, LM Studio, NVIDIA NIM, DeepSeek, Gemini)
and Hybrid Search Routing (Local SearXNG, Native Meta-Search, Tavily API).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlsplit
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env from project root if present
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _project_path(name: str, default: Path) -> Path:
    """Resolve configured paths predictably, with relative values rooted at the project."""
    value = os.getenv(name)
    candidate = Path(value).expanduser() if value else default
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def _cors_origins() -> List[str]:
    value = os.getenv("CORS_ORIGINS")
    if value is None:
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    origins = [
        origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()
    ]
    for origin in origins:
        parsed = urlsplit(origin)
        if origin == "*":
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' while credentialed CORS is enabled."
            )
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                f"Invalid CORS origin {origin!r}; provide an http(s) scheme and host only."
            )
    return origins


class Settings(BaseModel):
    """Central runtime configuration for Metrixa Engine."""

    project_root: Path = Field(default=PROJECT_ROOT)
    database_path: Path = Field(
        default_factory=lambda: _project_path(
            "DATABASE_PATH", Path("data") / "metrixa_leads.db"
        )
    )
    export_dir: Path = Field(
        default_factory=lambda: _project_path("EXPORT_DIR", Path("data") / "exports")
    )
    cors_origins: List[str] = Field(default_factory=_cors_origins)
    api_host: str = Field(default_factory=lambda: os.getenv("API_HOST", "127.0.0.1"))
    api_port: int = Field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
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
        default_factory=lambda: os.getenv(
            "LLAMACPP_BASE_URL", "http://127.0.0.1:8080/v1"
        )
    )
    llamacpp_model: str = Field(
        default_factory=lambda: os.getenv("LLAMACPP_MODEL", "").strip()
    )
    llamacpp_api_key: str = Field(
        default_factory=lambda: os.getenv("LLAMACPP_API_KEY", "local-no-key")
    )

    lmstudio_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"
        )
    )
    lmstudio_model: str = Field(
        default_factory=lambda: os.getenv("LMSTUDIO_MODEL", "").strip()
    )
    lmstudio_api_key: str = Field(
        default_factory=lambda: os.getenv("LMSTUDIO_API_KEY", "lm-studio")
    )

    # 2. Cloud LLM APIs (DeepSeek, NVIDIA NIM, Gemini)
    deepseek_api_key: str = Field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "").strip()
    )
    deepseek_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        )
    )
    deepseek_model: str = Field(
        default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "").strip()
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
        default_factory=lambda: os.getenv("NVIDIA_NIM_MODEL", "").strip()
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
        default_factory=lambda: os.getenv("GEMINI_MODEL", "").strip()
    )

    # 3. OpenAI & Ollama
    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip()
    )
    openai_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
    )
    openai_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "").strip()
    )

    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434/v1"
        )
    )
    ollama_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "").strip()
    )

    # 3. Search Harness (Local SearXNG + Native Meta-Search + Tavily Fallback)
    default_search_provider: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_SEARCH_PROVIDER", "searxng")
    )
    searxng_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "SEARXNG_BASE_URL", "http://127.0.0.1:8888"
        ).rstrip("/")
    )
    enable_native_metasearch: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_NATIVE_METASEARCH", "true").lower()
        == "true"
    )
    tavily_api_key: str = Field(
        default_factory=lambda: os.getenv("TAVILY_API_KEY", "").strip()
    )
    tavily_max_calls_per_run: int = Field(
        default_factory=lambda: int(os.getenv("TAVILY_MAX_CALLS_PER_RUN", "400"))
    )
    google_cse_api_key: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CSE_API_KEY", "").strip()
    )
    google_cse_id: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CSE_ID", "").strip()
    )
    brave_search_api_key: str = Field(
        default_factory=lambda: os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
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
        default_factory=lambda: os.getenv("ENABLE_DNS_MX_CHECK", "true").lower()
        == "true"
    )
    allow_private_crawler_targets: bool = Field(
        default_factory=lambda: os.getenv(
            "ALLOW_PRIVATE_CRAWLER_TARGETS", "false"
        ).lower()
        == "true"
    )

    # 5. Real-Time Google Sheets API & Deliverables Settings
    google_sheet_id: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_SHEET_ID", "").strip()
    )
    google_service_account_file: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    )
    google_service_account_json: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    )
    google_sheets_webhook_url: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_SHEETS_WEBHOOK_URL", "").strip()
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


def map_berlin_plz_to_district(
    plz: Optional[str], fallback_district: Optional[str] = None
) -> str:
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
