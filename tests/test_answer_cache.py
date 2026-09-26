import json
import os
import sqlite3
from dataclasses import replace
from uuid import uuid4

import pytest

from faq_agent.cache.answers import (
    RedisAnswerCache,
    build_answer_cache,
    cache_key,
    cache_scope,
    cosine_similarity,
    intent_signature,
)
from faq_agent.config import Settings
from faq_agent.retrieval import retriever


@pytest.fixture
def settings(tmp_path):
    path = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE collections(id TEXT, physical TEXT, profile TEXT, created REAL)")
        db.execute("CREATE TABLE documents(collection_id TEXT, id TEXT, chunks INT, created REAL)")
        db.execute("INSERT INTO collections VALUES ('faq','faq-vector','{}',1)")
        db.execute("INSERT INTO documents VALUES ('faq','doc',1,1)")
    return Settings(catalog_path=str(path), answer_cache_mode="exact")


@pytest.fixture
def answer():
    return {
        "answer": "Admins can view the public dashboard.",
        "status": "answered",
        "sources": [
            {
                "chunk_id": "chunk1",
                "title": "FAQ",
                "section": "Admin",
                "vector_score": 0.8,
                "document_id": "doc",
            }
        ],
    }


def test_key_scopes_and_invalidation(settings):
    key = cache_key(settings, "Question?", "faq")
    assert key and key == cache_key(settings, " Question? ", "faq")
    assert key != cache_key(settings, "question?", "faq")
    assert key != cache_key(settings, "Question?", "faq", "doc")
    for changes in (
        {"llm_model": "other"},
        {"vector_url": "http://other"},
        {"context_k": 2},
        {"corpus_version": "v2"},
    ):
        assert key != cache_key(replace(settings, **changes), "Question?", "faq")
    assert cache_key(settings, "Question?", None) is None
    assert cache_key(settings, "Question?", "unknown") is None
    assert cache_key(settings, "Question?", "faq", "unknown") is None
    with sqlite3.connect(settings.catalog_path) as db:
        db.execute("INSERT INTO documents VALUES ('faq','new',2,2)")
    assert key != cache_key(settings, "Question?", "faq")


def test_catalog_unavailable_or_wrong_profile(settings):
    assert cache_key(replace(settings, catalog_path="missing.sqlite3"), "q", "faq") is None
    with sqlite3.connect(settings.catalog_path) as db:
        db.execute("UPDATE collections SET profile=?", (json.dumps({"vector_url": "other"}),))
    assert cache_key(settings, "q", "faq") is None


class MemoryCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def put(self, key, value):
        self.values[key] = value

    def semantic_get(self, scope, question, vector, matches):
        return None

    def semantic_put(self, scope, question, vector, answer):
        pass

    def close(self):
        pass


def wire(monkeypatch, settings, answer, cache):
    counts = {"search": 0, "generation": 0}
    monkeypatch.setattr(retriever, "get_settings", lambda: settings)
    monkeypatch.setattr(retriever, "build_answer_cache", lambda _: cache)

    def search(*args):
        counts["search"] += 1
        return answer["sources"]

    def synthesize(*args):
        counts["generation"] += 1
        return answer

    monkeypatch.setattr(retriever, "search_question", search)
    monkeypatch.setattr(retriever, "synthesize", synthesize)
    return counts


def test_exact_hit_skips_retrieval_and_generation(monkeypatch, settings, answer):
    counts = wire(monkeypatch, settings, answer, MemoryCache())
    first = retriever.answer_question("Admin access?", "faq")
    second = retriever.answer_question("Admin access?", "faq")
    assert first["answer_generation_called"] and not first["cache_hit"]
    assert second["cache_hit"] and not second["answer_generation_called"]
    assert counts == {"search": 1, "generation": 1}
    retriever.answer_question("What can admins access?", "faq")
    assert counts["generation"] == 2  # Paraphrases deliberately miss in phase one.


def test_disabled_path(monkeypatch, settings, answer):
    assert build_answer_cache(replace(settings, answer_cache_mode="off")) is None
    counts = wire(monkeypatch, settings, answer, None)
    for _ in range(2):
        assert not retriever.answer_question("q", "faq")["cache_hit"]
    assert counts["generation"] == 2


class SemanticMemoryCache(MemoryCache):
    def __init__(self):
        super().__init__()
        self.entries = []

    def semantic_get(self, scope, question, vector, matches):
        current_ids = {match["chunk_id"] for match in matches}
        for saved_scope, saved_intent, saved_vector, saved_answer in self.entries:
            source_ids = {source["chunk_id"] for source in saved_answer["sources"]}
            overlap = len(source_ids & current_ids) / len(source_ids)
            if (
                saved_scope == scope
                and saved_intent == intent_signature(question)
                and cosine_similarity(vector, saved_vector) >= 0.85
                and overlap >= 0.67
            ):
                return saved_answer
        return None

    def semantic_put(self, scope, question, vector, answer):
        self.entries.append((scope, intent_signature(question), vector, answer))


def test_semantic_paraphrases_reuse_one_generation(monkeypatch, settings, answer):
    settings = replace(settings, answer_cache_mode="semantic")
    cache = SemanticMemoryCache()
    counts = wire(monkeypatch, settings, answer, cache)
    vectors = {
        "What can a System Admin access?": [1.0, 0.0],
        "What can a System Admin see?": [0.99, 0.01],
        "As the system admin what can i see?": [0.98, 0.02],
        "What can a manager see?": [0.99, 0.01],
        "What can a System Admin not see?": [0.99, 0.01],
    }

    def semantic_search(question, *args):
        counts["search"] += 1
        return vectors[question], answer["sources"]

    monkeypatch.setattr(retriever, "search_question_with_vector", semantic_search)
    first = retriever.answer_question("What can a System Admin access?", "faq")
    second = retriever.answer_question("What can a System Admin see?", "faq")
    third = retriever.answer_question("As the system admin what can i see?", "faq")
    assert not first["cache_hit"]
    assert second["cache_type"] == third["cache_type"] == "semantic"
    assert not second["answer_generation_called"] and not third["answer_generation_called"]
    assert counts["generation"] == 1

    manager = retriever.answer_question("What can a manager see?", "faq")
    negated = retriever.answer_question("What can a System Admin not see?", "faq")
    assert not manager["cache_hit"] and not negated["cache_hit"]
    assert counts["generation"] == 3


def test_semantic_reuse_requires_current_evidence(monkeypatch, settings, answer):
    settings = replace(settings, answer_cache_mode="semantic")
    cache = SemanticMemoryCache()
    counts = wire(monkeypatch, settings, answer, cache)
    calls = iter(
        [
            ([1.0, 0.0], answer["sources"]),
            ([0.99, 0.01], [{**answer["sources"][0], "chunk_id": "different"}]),
        ]
    )
    monkeypatch.setattr(retriever, "search_question_with_vector", lambda *args: next(calls))
    retriever.answer_question("What can a System Admin access?", "faq")
    result = retriever.answer_question("What can a System Admin see?", "faq")
    assert not result["cache_hit"] and result["answer_generation_called"]
    assert counts["generation"] == 2


def test_semantic_configuration_and_intent_guards(settings):
    assert cache_scope(settings, "faq")
    assert intent_signature("What can a System Admin see?") == intent_signature(
        "As the system administrator, what can I access?"
    )
    assert intent_signature("What can a manager see?") != intent_signature(
        "What can a System Admin see?"
    )
    assert intent_signature("What can a System Admin not see?") != intent_signature(
        "What can a System Admin see?"
    )
    with pytest.raises(ValueError, match="ANSWER_CACHE_MODE"):
        replace(settings, answer_cache_mode="unknown")
    with pytest.raises(ValueError, match="SEMANTIC_CACHE_THRESHOLD"):
        replace(settings, semantic_cache_threshold=1.1)
    with pytest.raises(ValueError, match="REDIS_TIMEOUT"):
        replace(settings, redis_timeout=0)


def test_redis_adapter_errors_ttl_and_abstention(monkeypatch, settings, answer):
    redis = pytest.importorskip("redis")
    from unittest.mock import Mock

    client = Mock()
    monkeypatch.setattr(redis.Redis, "from_url", lambda *a, **kw: client)
    cache = RedisAnswerCache(settings)
    cache.put("key", answer)
    assert client.set.call_args.kwargs["ex"] == settings.answer_cache_ttl
    client.set.reset_mock()
    cache.put("key", {"answer": "Unknown", "sources": [], "status": "insufficient_evidence"})
    client.set.assert_not_called()
    client.get.return_value = "invalid-json"
    assert cache.get("key") is None
    client.get.side_effect = redis.exceptions.ConnectionError("private connection details")
    assert cache.get("key") is None
    cache.put("key", answer)
    client.set.assert_not_called()
    client.close.side_effect = redis.exceptions.ConnectionError()
    cache.close()


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="Opt-in real Redis smoke test")
def test_real_redis_api_hit(monkeypatch, settings, answer):
    from fastapi.testclient import TestClient

    from faq_agent.api.routes import create_app

    settings = replace(
        settings,
        redis_url=os.environ["TEST_REDIS_URL"],
        answer_cache_namespace="test-" + uuid4().hex,
    )
    cache = RedisAnswerCache(settings)
    counts = wire(monkeypatch, settings, answer, cache)
    key = cache_key(settings, "Admin access?", "faq")
    try:
        client = TestClient(create_app(retriever.answer_question))
        body = {"question": "Admin access?", "collection_id": "faq"}
        first = client.post("/ask", json=body)
        second = client.post("/ask", json=body)
        assert first.status_code == second.status_code == 200
        assert not first.json()["cache_hit"] and second.json()["cache_hit"]
        assert first.json()["request_id"] != second.json()["request_id"]
        assert counts == {"search": 1, "generation": 1}
        assert 0 < cache.client.ttl(key) <= settings.answer_cache_ttl
    finally:
        cache.client.delete(key)
        cache.close()


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="Opt-in real Redis smoke test")
def test_real_redis_semantic_paraphrase_reuse(monkeypatch, settings, answer):
    settings = replace(
        settings,
        answer_cache_mode="semantic",
        redis_url=os.environ["TEST_REDIS_URL"],
        answer_cache_namespace="test-semantic-" + uuid4().hex,
    )
    counts = {"search": 0, "generation": 0}
    monkeypatch.setattr(retriever, "get_settings", lambda: settings)
    monkeypatch.setattr(retriever, "build_answer_cache", lambda _: RedisAnswerCache(settings))
    vectors = iter(([1.0, 0.0], [0.99, 0.01], [0.98, 0.02]))

    def semantic_search(*args):
        counts["search"] += 1
        return next(vectors), answer["sources"]

    def synthesize(*args):
        counts["generation"] += 1
        return answer

    monkeypatch.setattr(retriever, "search_question_with_vector", semantic_search)
    monkeypatch.setattr(retriever, "synthesize", synthesize)
    questions = (
        "What can a System Admin access?",
        "What can a System Admin see?",
        "As the system admin what can i see?",
    )
    try:
        results = [retriever.answer_question(question, "faq") for question in questions]
        assert not results[0]["cache_hit"]
        assert [result["cache_type"] for result in results[1:]] == ["semantic", "semantic"]
        assert counts == {"search": 3, "generation": 1}
    finally:
        cache = RedisAnswerCache(settings)
        keys = list(cache.client.scan_iter(match=settings.answer_cache_namespace + ":*"))
        if keys:
            cache.client.delete(*keys)
        cache.close()
