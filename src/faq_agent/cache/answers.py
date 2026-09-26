"""Exact and guarded semantic answer caching for managed public FAQ collections."""

import hashlib
import json
import logging
import math
import re
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


class SemanticEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vector: list[float] = Field(min_length=1)
    intent: str
    answer: CachedAnswer


class AnswerCache(Protocol):
    def get(self, key: str) -> dict | None: ...
    def put(self, key: str, answer: dict) -> None: ...
    def semantic_get(
        self, scope: str, question: str, vector: list[float], matches: list[dict]
    ) -> dict | None: ...
    def semantic_put(
        self, scope: str, question: str, vector: list[float], answer: dict
    ) -> None: ...
    def close(self) -> None: ...


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def cache_scope(settings, collection_id, document_id=None):
    """Return an invalidation-aware scope for an application-managed collection."""
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
    return digest(
        {
            "pipeline": "semantic-v1-temperature0-max700",
            "environment": settings.app_env,
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
    )


def cache_key(settings, question, collection_id, document_id=None):
    scope = cache_scope(settings, collection_id, document_id)
    if not scope:
        return None
    return f"{settings.answer_cache_namespace}:exact:{scope}:{digest(question.strip())}"


def intent_signature(question):
    """Conservative role and polarity guard; semantic score handles wording."""
    text = re.sub(r"[^a-z0-9']+", " ", question.lower()).strip()
    words = set(text.split())
    negated = bool(words & {"no", "not", "never", "cannot", "can't", "without", "exclude"})
    roles = []
    for role, pattern in {
        "system_admin": r"\b(system admin(?:istrator)?s?|sysadmin(?:s)?)\b",
        "admin": r"\badmin(?:istrator)?s?\b",
        "manager": r"\bmanagers?\b",
        "employee": r"\bemployees?\b",
        "reviewer": r"\breviewers?\b",
        "reviewee": r"\breviewees?\b",
    }.items():
        if re.search(pattern, text):
            roles.append(role)
    if "system_admin" in roles and "admin" in roles:
        roles.remove("admin")
    return json.dumps({"negated": negated, "roles": roles}, sort_keys=True)


def cosine_similarity(left, right):
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return -1.0
    return dot / (left_norm * right_norm)


class RedisAnswerCache:
    def __init__(self, settings):
        from redis import Redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        self.client = Redis.from_url(
            settings.redis_url,
            socket_timeout=settings.redis_timeout,
            socket_connect_timeout=settings.redis_timeout,
            retry=Retry(NoBackoff(), 0),
            decode_responses=True,
        )
        self.ttl = settings.answer_cache_ttl
        self.namespace = settings.answer_cache_namespace
        self.mode = settings.answer_cache_mode
        self.threshold = settings.semantic_cache_threshold
        self.evidence_overlap = settings.semantic_cache_evidence_overlap
        self.max_candidates = settings.semantic_cache_max_candidates
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
            return
        except RedisError:
            logger.warning("answer_cache_write_unavailable")

    def semantic_get(self, scope, question, vector, matches):
        from redis.exceptions import RedisError

        if self.mode != "semantic" or self.failed or not scope:
            return None
        index_key = f"{self.namespace}:semantic-index:{scope}"
        try:
            keys = sorted(self.client.smembers(index_key))[: self.max_candidates]
            if not keys:
                return None
            raw_entries = self.client.mget(keys)
            missing = [key for key, raw in zip(keys, raw_entries, strict=True) if raw is None]
            if missing:
                self.client.srem(index_key, *missing)
            current_ids = {match["chunk_id"] for match in matches}
            intent = intent_signature(question)
            best = None
            best_score = self.threshold
            for raw in raw_entries:
                if raw is None or len(raw) > 200_000:
                    continue
                try:
                    entry = SemanticEntry.model_validate_json(raw)
                except (ValidationError, UnicodeError):
                    continue
                source_ids = {source.chunk_id for source in entry.answer.sources}
                overlap = len(source_ids & current_ids) / len(source_ids)
                score = cosine_similarity(vector, entry.vector)
                if (
                    entry.intent == intent
                    and overlap >= self.evidence_overlap
                    and score >= best_score
                ):
                    best, best_score = entry.answer.model_dump(exclude_unset=True), score
            return best
        except RedisError:
            self.failed = True
            logger.warning("semantic_cache_read_unavailable")
            return None

    def semantic_put(self, scope, question, vector, answer):
        from redis.exceptions import RedisError

        if self.mode != "semantic" or self.failed or not scope:
            return
        try:
            entry = SemanticEntry(
                vector=vector,
                intent=intent_signature(question),
                answer=CachedAnswer.model_validate(answer),
            )
            key = f"{self.namespace}:semantic:{scope}:{digest(vector)}"
            index_key = f"{self.namespace}:semantic-index:{scope}"
            pipe = self.client.pipeline(transaction=True)
            pipe.set(key, entry.model_dump_json(exclude_unset=True), ex=self.ttl)
            pipe.sadd(index_key, key)
            pipe.expire(index_key, self.ttl)
            pipe.execute()
        except ValidationError:
            return
        except RedisError:
            logger.warning("semantic_cache_write_unavailable")

    def close(self):
        from redis.exceptions import RedisError

        try:
            self.client.close()
        except RedisError:
            logger.warning("answer_cache_close_unavailable")


def build_answer_cache(settings) -> AnswerCache | None:
    if settings.answer_cache_mode == "off":
        return None
    try:
        return RedisAnswerCache(settings)
    except (ImportError, ValueError):
        logger.warning("answer_cache_not_configured")
        return None
