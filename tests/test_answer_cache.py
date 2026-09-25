import json
import os
import sqlite3
from dataclasses import replace
from uuid import uuid4

import pytest

from faq_agent.cache.answers import RedisAnswerCache, build_answer_cache, cache_key
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
