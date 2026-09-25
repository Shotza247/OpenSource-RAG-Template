"""Exact public-FAQ answer cache with catalog-derived invalidation."""

import hashlib
import json
import logging
import sqlite3
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from faq_agent.config import PROJECT_ROOT
from faq_agent.prompts.templates import SYSTEM_PROMPT

logger = logging.getLogger("faq_agent")


class CachedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(min_length=1)
    title: str
    section: str
    vector_score: float = Field(allow_inf_nan=False)
    rerank_score: float | None = None
    filename: str | None = None
    page: int | None = None
    document_id: str = Field(min_length=1)


class CachedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=6000)
    status: Literal["answered"]
    sources: list[CachedSource] = Field(min_length=1)


class AnswerCache(Protocol):
    def get(self, key: str) -> dict | None: ...
    def put(self, key: str, answer: dict) -> None: ...
    def close(self) -> None: ...


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def cache_key(settings, question, collection_id, document_id=None):
    """Only managed public collections are eligible; never trust cache as catalog."""
    if not collection_id:
        return None
    path = Path(settings.catalog_path or PROJECT_ROOT / ".local/library.sqlite3").resolve()
    try:
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.25)
        try:
            db.execute("BEGIN")
            collection = db.execute(
                "SELECT physical,profile,created FROM collections WHERE id=?", (collection_id,)
            ).fetchone()
            documents = db.execute(
                "SELECT id,chunks,created FROM documents WHERE collection_id=? ORDER BY id",
                (collection_id,),
            ).fetchall()
        finally:
            db.close()
        if not collection or not documents:
            return None
        profile = json.loads(collection[1])
        if not isinstance(profile, dict):
            return None
        if any(getattr(settings, field, None) != value for field, value in profile.items()):
            return None
        if document_id and document_id not in {row[0] for row in documents}:
            return None
    except (sqlite3.Error, ValueError, TypeError):
        return None
    scope = {
        "pipeline": "exact-v1-temperature0-max700",
        "environment": settings.app_env,
        "question": question.strip(),  # Preserve case, punctuation and internal whitespace.
        "catalog": str(path),
        "collection_id": collection_id,
        "document_id": document_id,
        "collection": collection,
        "documents": documents,
        "vector_store": settings.vector_store,
        "vector_url": settings.vector_url,
        "index_profile": settings.index_name,
        "embedding_url": settings.embedding_url,
        "corpus_version": settings.corpus_version,
        "context_k": settings.context_k,
        "llm": [settings.llm_provider, settings.llm_base_url, settings.llm_model],
        "prompt": SYSTEM_PROMPT,
    }
    return settings.answer_cache_namespace + ":" + digest(scope)


class RedisAnswerCache:
    def __init__(self, settings):
        from redis import Redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        self.client = Redis.from_url(
            settings.redis_url,
            socket_timeout=0.3,
            socket_connect_timeout=0.3,
            retry=Retry(NoBackoff(), 0),
            decode_responses=True,
        )
        self.ttl = settings.answer_cache_ttl
        self.failed = False

    def get(self, key):
        from redis.exceptions import RedisError

        try:
            raw = self.client.get(key)
            if raw is None or len(raw) > 100_000:
                return None
            return CachedAnswer.model_validate_json(raw).model_dump(exclude_unset=True)
        except (RedisError, ValidationError, UnicodeError):
            self.failed = True
            logger.warning("answer_cache_read_unavailable")
            return None

    def put(self, key, answer):
        from redis.exceptions import RedisError

        if self.failed:
            return
        try:
            valid = CachedAnswer.model_validate(answer)
            self.client.set(key, valid.model_dump_json(exclude_unset=True), ex=self.ttl)
        except ValidationError:
            return  # Abstentions and malformed responses are not reusable answers.
        except RedisError:
            logger.warning("answer_cache_write_unavailable")

    def close(self):
        from redis.exceptions import RedisError

        try:
            self.client.close()
        except RedisError:
            logger.warning("answer_cache_close_unavailable")


def build_answer_cache(settings) -> AnswerCache | None:
    if settings.answer_cache_mode != "exact":
        return None
    try:
        return RedisAnswerCache(settings)
    except (ImportError, ValueError):
        logger.warning("answer_cache_not_configured")
        return None
