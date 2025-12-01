import os
from functools import lru_cache
from pydantic import AnyHttpUrl


class Settings:
    """
    Lightweight settings container.

    We avoid pydantic-settings/BaseSettings here to keep compatibility
    with the installed pydantic version, and instead read directly from
    environment variables.
    """

    def __init__(self) -> None:
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_api_base: AnyHttpUrl | str = os.getenv(
            "OPENAI_API_BASE", "https://api.openai.com/v1"
        )
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.request_timeout_seconds: int = int(
            os.getenv("REQUEST_TIMEOUT_SECONDS", "60")
        )

        self.app_host: str = os.getenv("APP_HOST", "0.0.0.0")
        self.app_port: int = int(os.getenv("APP_PORT", "8333"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
