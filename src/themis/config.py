"""Central configuration. All settings come from environment / .env via pydantic-settings.

No URL, key, or model name may be hardcoded in business logic — read it from here.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (src/themis/config.py -> project root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # NVIDIA NIM
    nvidia_nim_api_key: str = Field(default="", alias="NVIDIA_NIM_API_KEY")
    nvidia_nim_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1", alias="NVIDIA_NIM_BASE_URL"
    )
    # Reranking endpoint may differ from the chat/embeddings base; override if needed.
    rerank_url: str = Field(default="", alias="RERANK_URL")

    # Qdrant
    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    # Models (pinned)
    llm_model: str = Field(default="meta/llama-3.3-70b-instruct", alias="LLM_MODEL")
    fast_llm_model: str = Field(default="meta/llama-3.1-8b-instruct", alias="FAST_LLM_MODEL")
    embed_model: str = Field(default="nvidia/nv-embedqa-e5-v5", alias="EMBED_MODEL")
    rerank_model: str = Field(
        default="nvidia/nv-rerankqa-mistral-4b-v3", alias="RERANK_MODEL"
    )
    embed_dim: int = Field(default=1024, alias="EMBED_DIM")

    # Ingestion tuning
    embed_batch_size: int = Field(default=32, alias="EMBED_BATCH_SIZE")
    nim_max_concurrent: int = Field(default=4, alias="NIM_MAX_CONCURRENT")

    # Collections
    statutes_collection: str = "corpus_statutes"

    # Paths
    corpus_statutes_dir: Path = PROJECT_ROOT / "corpus" / "raw" / "statutes"
    cache_dir: Path = PROJECT_ROOT / ".cache"

    @property
    def embed_cache_dir(self) -> Path:
        return self.cache_dir / "embeddings"


@lru_cache
def get_settings() -> Settings:
    return Settings()
