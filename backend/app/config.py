from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/crag_ai"
    jwt_secret: str = "change-this-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    open_router_api_key: str | None = None
    cohere_api_key: str | None = None
    web_search_enabled: bool = True
    tavily_api_key: str | None = None
    web_search_timeout_seconds: int = 8
    web_search_max_results: int = 8
    web_search_retry_attempts: int = 2
    web_search_search_depth: str = "basic"
    web_search_cache_ttl_seconds: int = 43200
    web_search_query_limit_per_eval: int = 2
    web_search_max_chunks_per_eval: int = 8


settings = Settings()
