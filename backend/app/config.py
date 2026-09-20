from __future__ import annotations

import os
from functools import lru_cache


def _normalize_http_path(value: str, default: str = "") -> str:
    normalized = value.strip()
    if not normalized:
        return default
    return normalized if normalized.startswith("/") else f"/{normalized}"


class Settings:
    app_name = "Business Analysis API"
    api_v1_prefix = "/api/v1"
    database_url = os.getenv(
        "DATABASE_URL",
        "sqlite:///./demo.db",
    )
    fastgpt_base_url = os.getenv("FASTGPT_BASE_URL", "").rstrip("/")
    fastgpt_api_key = os.getenv("FASTGPT_API_KEY", "")
    fastgpt_dataset_id = os.getenv("FASTGPT_DATASET_ID", "")
    fastgpt_dataset_upsert_path = _normalize_http_path(
        os.getenv("FASTGPT_DATASET_UPSERT_PATH", "")
    )
    fastgpt_chat_path = _normalize_http_path(
        os.getenv("FASTGPT_CHAT_PATH", "/chat/completions"),
        default="/chat/completions",
    )
    qichacha_app_key = os.getenv("QICHACHA_APP_KEY", "")
    qichacha_secret_key = os.getenv("QICHACHA_SECRET_KEY", "")
    qichacha_enabled = os.getenv("QICHACHA_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
    }
    default_context_limit = int(os.getenv("RISK_CONTEXT_LIMIT", "12"))
    cors_origins = os.getenv("CORS_ORIGINS", "*")
    collection_api_key = os.getenv("COLLECTION_API_KEY", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
