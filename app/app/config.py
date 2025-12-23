import os
from functools import lru_cache
from pathlib import Path
from typing import Union
from pydantic import AnyHttpUrl


class Settings:
    """
    Lightweight settings container.

    We avoid pydantic-settings/BaseSettings here to keep compatibility
    with the installed pydantic version, and instead read directly from
    environment variables.
    """

    def __init__(self) -> None:
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").strip() or "INFO"
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_api_base: Union[AnyHttpUrl, str] = os.getenv(
            "OPENAI_API_BASE", "https://api.openai.com/v1"
        )
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        # Upstream path appended to OPENAI_API_BASE (which already includes /v1 by default).
        # For the OpenAI Responses API, this should be `responses` (=> /v1/responses).
        self.openai_chat_path: str = os.getenv("OPENAI_CHAT_PATH", "responses").strip()
        self.request_timeout_seconds: int = int(
            os.getenv("REQUEST_TIMEOUT_SECONDS", "60")
        )

        self.app_host: str = os.getenv("APP_HOST", "0.0.0.0")
        self.app_port: int = int(os.getenv("APP_PORT", "8333"))

        # MCP is optional and disabled by default.
        self.mcp_config_path: str = os.getenv("MCP_CONFIG_PATH", "").strip()

        # Constrain filesystem-like tools to this root (no auth, but path safety).
        default_root = Path(__file__).resolve().parents[2]
        self.workspace_root: str = os.getenv("WORKSPACE_ROOT", str(default_root)).strip()

        # RAG (Retrieval-Augmented Generation) configuration
        rag_enabled_str = os.getenv("RAG_ENABLED", "true").strip().lower()
        self.rag_enabled: bool = rag_enabled_str in {"1", "true", "yes", "y", "on"}
        self.rag_top_k: int = int(os.getenv("RAG_TOP_K", "5"))
        self.rag_max_context_chars: int = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "8000"))
        self.chunkenizer_api_url: str = os.getenv("CHUNKENIZER_API_URL", "http://localhost:8000").strip()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
