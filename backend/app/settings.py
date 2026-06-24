from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_fallback_models: str = Field(
        default="gemini-2.5-flash-lite",
        alias="GEMINI_FALLBACK_MODELS",
    )
    use_vertex_ai: bool = Field(default=False, alias="USE_VERTEX_AI")
    gcp_project_id: str | None = Field(default=None, alias="GCP_PROJECT_ID")
    gcp_location: str = Field(default="us-central1", alias="GCP_LOCATION")
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    top_k_default: int = Field(default=5, alias="TOP_K_DEFAULT")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    db_pool_min_size: int = Field(default=1, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=3, alias="DB_POOL_MAX_SIZE")

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gemini_model_candidates(self) -> list[str]:
        models = [self.gemini_model]
        models.extend(
            model.strip()
            for model in self.gemini_fallback_models.split(",")
            if model.strip()
        )
        return list(dict.fromkeys(models))

    @field_validator("top_k_default")
    @classmethod
    def validate_top_k_default(cls, value: int) -> int:
        if not 1 <= value <= 20:
            raise ValueError("TOP_K_DEFAULT must be between 1 and 20")
        return value

    @field_validator("db_pool_min_size", "db_pool_max_size")
    @classmethod
    def validate_db_pool_size(cls, value: int) -> int:
        if not 1 <= value <= 15:
            raise ValueError("DB pool size must be between 1 and 15")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
