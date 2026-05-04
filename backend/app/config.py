from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    openrouter_app_name: str = Field(default="Hyperwrite", alias="OPENROUTER_APP_NAME")
    openrouter_referer: str = Field(
        default="http://localhost:5173", alias="OPENROUTER_REFERER"
    )
    writer_model: str = Field(default="openai/gpt-5", alias="WRITER_MODEL")
    reviewer_model: str = Field(
        default="anthropic/claude-sonnet-4.5", alias="REVIEWER_MODEL"
    )
    research_model: str = Field(default="perplexity/sonar-pro-search", alias="RESEARCH_MODEL")
    pieces_dir: Path = Field(default=Path("data/pieces"), alias="PIECES_DIR")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
