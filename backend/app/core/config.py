from functools import lru_cache
from typing import List, Optional, Union
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Weave RAG API"
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
    )
    database_url: str = Field(
        description="PostgreSQL / Supabase connection string with pgvector support",
    )
    
    # api
    gemini_api_key: SecretStr = Field(description="Google Gemini API key")
    gemini_model_name: str = Field(default="gemini-3.6-flash", description="Primary Gemini model name")
    groq_api_key: Optional[SecretStr] = Field(default=None, description="Groq API key for quota fallback")
    groq_model_name: str = Field(default="openai/gpt-oss-120b", description="Fallback Groq model name")

    # embedding model
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Local sentence-transformers embedding model name",
    )
    embedding_dimension: int = Field(
        default=384,
        description="Vector dimension matching the embedding model",
    )

    # chunks
    chunk_size: int = Field(default=1500, description="Approximate characters per chunk")
    chunk_overlap: int = Field(default=200, description="Character overlap between chunks")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError(f"cors_origins must be a string or list, got {type(v).__name__}")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton getter for cached settings."""
    return Settings()
