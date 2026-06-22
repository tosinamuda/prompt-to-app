from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into the process environment so LiteLLM (used by DSPy) can read
# provider keys like OPENROUTER_API_KEY directly.
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="P2A_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "prompt2app"
    public_base_url: str = "http://localhost:8000"
    # Origin the backend serves from; used to build absolute app/resource URLs.
    app_base_url: str = Field(default="http://127.0.0.1:8011", validation_alias="APP_BASE_URL")
    mcp_server_url: str | None = Field(default=None, validation_alias="MCP_SERVER_URL")

    # DSPy induction/run model. LiteLLM convention used by DSPy:
    #   openrouter/<provider>/<model>  → reads OPENROUTER_API_KEY
    lm_model: str = Field(default="openrouter/openai/gpt-oss-120b", validation_alias="LM_MODEL")
    lm_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")

    # Model for the A2A chat agent (needs tool-calling support). Defaults to LM_MODEL.
    a2a_model: str = Field(default="", validation_alias="A2A_MODEL")
    a2a_timeout_seconds: float = Field(default=45.0, validation_alias="A2A_TIMEOUT_SECONDS")
    site_name: str = "Prompt2App"

    # Where compiled apps + human corrections (training data) are persisted.
    data_dir: Path = ROOT_DIR / "data"

    @property
    def agent_model(self) -> str:
        model = self.a2a_model or self.lm_model
        return model if model.startswith("openrouter/") else f"openrouter/{model}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
