"""Environment configuration; credentials never appear in public responses."""

import hashlib
import json
import os
from dataclasses import dataclass, fields
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5500"
    vector_store: str = "qdrant"
    vector_url: str = "http://localhost:6333"
    vector_api_key: str = ""
    collection: str = "profile_v1"
    corpus_version: str = "v1"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str = "main"
    vector_dimensions: int = 384
    hf_token: str = ""
    embedding_url: str = ""
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    embedding_document_prefix: str = ""
    rerank_url: str = ""
    rerank_min_score: float = 0.0
    llm_base_url: str = "https://router.huggingface.co/v1"
    llm_model: str = ""
    request_timeout: int = 30
    candidate_k: int = 12
    context_k: int = 4
    chunk_chars: int = 1000
    chunk_overlap: int = 150
    max_tool_calls: int = 2

    def __post_init__(self):
        if self.vector_store not in {"qdrant", "chroma"}:
            raise ValueError("VECTOR_STORE must be qdrant or chroma")
        if not 0 <= self.chunk_overlap < self.chunk_chars:
            raise ValueError("Require 0 <= CHUNK_OVERLAP < CHUNK_CHARS")
        if not 1 <= self.context_k <= self.candidate_k <= 50:
            raise ValueError("Require 1 <= CONTEXT_K <= CANDIDATE_K <= 50")
        if self.vector_dimensions < 1 or self.request_timeout < 1:
            raise ValueError("Dimensions and timeout must be positive")
        if not 0 <= self.rerank_min_score <= 1 or not 1 <= self.max_tool_calls <= 3:
            raise ValueError("Invalid rerank threshold or tool budget")
        if not self.collection or not self.corpus_version:
            raise ValueError("Collection and corpus version are required")
        if self.app_env != "local":
            urls = [self.vector_url, self.embedding_url, self.llm_base_url]
            if self.rerank_url:
                urls.append(self.rerank_url)
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

    def require_models(self):
        if not self.embedding_url or not self.hf_token or not self.llm_model:
            raise ValueError("Configure EMBEDDING_URL, HF_TOKEN and LLM_MODEL")


@lru_cache
def get_settings():
    load_dotenv()
    values = {}
    for field in fields(Settings):
        raw = os.getenv(field.name.upper())
        if raw is not None:
            values[field.name] = field.type(raw) if field.type in (int, float) else raw
    return Settings(**values)
