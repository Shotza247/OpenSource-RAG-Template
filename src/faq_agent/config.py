"""Environment configuration; credentials never appear in public responses."""

import hashlib
import json
import os
from dataclasses import dataclass, fields
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5500"
    vector_store: str = "qdrant"
    vector_url: str = "http://localhost:6333"
    vector_api_key: str = ""
    collection: str = "faq_documents"
    corpus_version: str = "v1"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str = "main"
    vector_dimensions: int = 384
    hf_token: str = ""
    embedding_url: str = ""
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    embedding_document_prefix: str = ""
    llm_base_url: str = "https://router.huggingface.co/v1"
    llm_provider: str = "huggingface"
    llm_model: str = ""
    request_timeout: int = 30
    context_k: int = 4
    chunk_chars: int = 1000
    chunk_overlap: int = 150
    catalog_path: str = ""
    answer_cache_mode: str = "off"
    redis_url: str = "redis://127.0.0.1:6380/0"
    redis_timeout: float = 1.0
    answer_cache_ttl: int = 3600
    answer_cache_namespace: str = "faq-answer-v1"
    semantic_cache_threshold: float = 0.85
    semantic_cache_evidence_overlap: float = 0.67
    semantic_cache_max_candidates: int = 100

    def __post_init__(self):
        if self.answer_cache_mode not in {"off", "exact", "semantic"}:
            raise ValueError("ANSWER_CACHE_MODE must be off, exact or semantic")
        if self.answer_cache_ttl < 1 or not self.answer_cache_namespace:
            raise ValueError("Cache TTL must be positive and namespace nonempty")
        if not 0.1 <= self.redis_timeout <= 10:
            raise ValueError("REDIS_TIMEOUT must be between 0.1 and 10 seconds")
        if not 0 <= self.semantic_cache_threshold <= 1:
            raise ValueError("SEMANTIC_CACHE_THRESHOLD must be between 0 and 1")
        if not 0 <= self.semantic_cache_evidence_overlap <= 1:
            raise ValueError("SEMANTIC_CACHE_EVIDENCE_OVERLAP must be between 0 and 1")
        if not 1 <= self.semantic_cache_max_candidates <= 1000:
            raise ValueError("SEMANTIC_CACHE_MAX_CANDIDATES must be between 1 and 1000")
        if self.llm_provider != "huggingface":
            raise ValueError("Only hosted Hugging Face synthesis is currently supported")
        if self.vector_store not in {"qdrant", "chroma"}:
            raise ValueError("VECTOR_STORE must be qdrant or chroma")
        if not 0 <= self.chunk_overlap < self.chunk_chars:
            raise ValueError("Require 0 <= CHUNK_OVERLAP < CHUNK_CHARS")
        if not 1 <= self.context_k <= 50:
            raise ValueError("Require 1 <= CONTEXT_K <= 50")
        if self.vector_dimensions < 1 or self.request_timeout < 1:
            raise ValueError("Dimensions and timeout must be positive")
        if not self.collection or not self.corpus_version:
            raise ValueError("Collection and corpus version are required")
        if self.app_env != "local":
            urls = [self.vector_url, self.embedding_url, self.llm_base_url]
            if any(not url.startswith("https://") for url in urls):
                raise ValueError("Production services require HTTPS")

    @property
    def origins(self):
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

    @property
    def index_name(self):
        spec = [
            self.embedding_model,
            self.embedding_revision,
            self.vector_dimensions,
            self.embedding_query_prefix,
            self.embedding_document_prefix,
            self.chunk_chars,
            self.chunk_overlap,
            "chunk-v2",
        ]
        digest = hashlib.sha256(json.dumps(spec).encode()).hexdigest()[:12]
        return f"{self.collection}-{digest}"


@lru_cache
def get_settings():
    load_dotenv(PROJECT_ROOT / ".env")
    values = {}
    for field in fields(Settings):
        raw = os.getenv(field.name.upper())
        if raw is not None:
            values[field.name] = field.type(raw) if field.type in (int, float) else raw
    target = os.getenv("RAG_TARGET", "local")
    if target not in {"local", "cloud"}:
        raise ValueError("RAG_TARGET must be local or cloud")
    if target == "cloud":
        cloud = dotenv_values(PROJECT_ROOT / ".env.qdrant-cloud")
        url = (os.getenv("QDRANT_CLOUD_URL") or cloud.get("QDRANT_CLOUD_URL") or "").rstrip("/")
        key = os.getenv("QDRANT_CLOUD_API_KEY") or cloud.get("QDRANT_CLOUD_API_KEY")
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".cloud.qdrant.io")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path
            or not key
        ):
            raise ValueError("Cloud target requires a valid Qdrant Cloud HTTPS origin and key")
        values.update(
            vector_store="qdrant",
            vector_url=url,
            vector_api_key=key,
            catalog_path=str(PROJECT_ROOT / ".local" / "cloud" / "library.sqlite3"),
        )
    return Settings(**values)
