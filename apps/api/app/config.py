from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "localrag_documents"

    ollama_base_url: str = "http://ollama:11434"

    llm_provider: str = "ollama"
    llm_model: str = "llama3.2:3b"

    embedding_model: str = "nomic-embed-text"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()