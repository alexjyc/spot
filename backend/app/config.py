from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-nano", validation_alias="OPENAI_MODEL")
    openai_timeout: int = Field(default=60, validation_alias="OPENAI_TIMEOUT")
    tavily_api_key: str = Field(default="", validation_alias="TAVILY_API_KEY")
    tavily_search_timeout: int = Field(default=10, validation_alias="TAVILY_SEARCH_TIMEOUT")
    tavily_extract_timeout: int = Field(default=30, validation_alias="TAVILY_EXTRACT_TIMEOUT")
    mongodb_uri: str = Field(default="", validation_alias="MONGODB_URI")
    db_name: str = Field(default="travel_planner", validation_alias="DB_NAME")
    cors_origins: str = Field(
        default="http://localhost:3000", validation_alias="CORS_ORIGINS"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def parsed_cors_origins(self) -> list[str]:
        parts = [p.strip() for p in self.cors_origins.split(",")]
        return [p for p in parts if p]


def get_settings() -> Settings:
    return Settings()
