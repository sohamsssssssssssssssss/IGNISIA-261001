"""
Central application settings.
Keeps environment parsing in one place so API, storage, and deploy configs stay consistent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_api_tokens(value: str | None) -> Dict[str, str]:
    """
    Parse `role:token` pairs separated by commas.
    Example: `viewer:viewer-token,analyst:analyst-token,admin:admin-token`
    """
    default = {
        "viewer": "demo-viewer-token",
        "analyst": "demo-analyst-token",
        "admin": "demo-admin-token",
    }
    if not value:
        return default

    parsed: Dict[str, str] = {}
    for item in value.split(","):
        raw = item.strip()
        if not raw or ":" not in raw:
            continue
        role, token = raw.split(":", 1)
        role = role.strip()
        token = token.strip()
        if role and token:
            parsed[role] = token
    return parsed or default


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    debug: bool
    demo_mode: bool
    api_host: str
    api_port: int
    cors_origins: List[str]
    database_url: str
    database_path: str
    model_artifact_dir: str
    default_history_page_size: int
    max_history_page_size: int
    require_auth: bool
    api_tokens: Dict[str, str]
    enable_rate_limit: bool
    rate_limit_per_minute: int
    pipeline_interval_seconds: int
    pipeline_auto_start: bool
    auto_migrate_database: bool
    gst_amnesty_enabled: bool
    gst_amnesty_start: Optional[str]
    gst_amnesty_end: Optional[str]
    gst_amnesty_periods: List[str]
    chroma_persist_dir: str
    embedding_model_name: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[2]
    default_db = backend_root / "data" / "intellicredit.db"
    default_model_artifact_dir = backend_root / "artifacts"
    default_chroma_persist_dir = backend_root / "data" / "chroma_db"
    database_path = os.getenv("DATABASE_PATH", str(default_db))
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{database_path}")
    app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development"
    cors_value = os.getenv("CORS_ORIGINS") or os.getenv("ALLOWED_ORIGINS")
    demo_mode_value = os.getenv("DEMO_MODE") or os.getenv("MOCK_MODE")

    return Settings(
        app_name=os.getenv("APP_NAME", "Intelli-Credit API"),
        app_env=app_env,
        debug=_parse_bool(os.getenv("DEBUG"), default=False),
        demo_mode=_parse_bool(demo_mode_value, default=True),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        cors_origins=_parse_csv(cors_value, default=["*"]),
        database_url=database_url,
        database_path=database_path,
        model_artifact_dir=os.getenv("MODEL_ARTIFACT_DIR", str(default_model_artifact_dir)),
        default_history_page_size=int(os.getenv("DEFAULT_HISTORY_PAGE_SIZE", "20")),
        max_history_page_size=int(os.getenv("MAX_HISTORY_PAGE_SIZE", "100")),
        require_auth=_parse_bool(
            os.getenv("REQUIRE_AUTH"),
            default=app_env.lower() == "production",
        ),
        api_tokens=_parse_api_tokens(os.getenv("API_TOKENS")),
        enable_rate_limit=_parse_bool(os.getenv("ENABLE_RATE_LIMIT"), default=True),
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
        pipeline_interval_seconds=int(os.getenv("PIPELINE_INTERVAL_SECONDS", "900")),
        pipeline_auto_start=_parse_bool(os.getenv("PIPELINE_AUTO_START"), default=True),
        auto_migrate_database=_parse_bool(os.getenv("AUTO_MIGRATE_DATABASE"), default=False),
        gst_amnesty_enabled=_parse_bool(os.getenv("GST_AMNESTY_ENABLED"), default=False),
        gst_amnesty_start=os.getenv("GST_AMNESTY_START") or None,
        gst_amnesty_end=os.getenv("GST_AMNESTY_END") or None,
        gst_amnesty_periods=_parse_csv(os.getenv("GST_AMNESTY_PERIODS"), default=[]),
        chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", str(default_chroma_persist_dir)),
        embedding_model_name=os.getenv(
            "EMBEDDING_MODEL_NAME",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
    )
