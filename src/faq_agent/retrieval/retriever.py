"""Shared retrieval and answer workflow, independent of HTTP routes."""

from faq_agent.cache.answers import build_answer_cache, cache_key, cache_scope
from faq_agent.config import get_settings
from faq_agent.embeddings.embedder import build_embedding_client
from faq_agent.ingestion.service import Library
from faq_agent.llm.client import synthesize
from faq_agent.vectordb.vector_store import build_vector_store


def answer_question(question, collection_id=None, document_id=None):
    settings = get_settings()
    cache = build_answer_cache(settings)
    key = cache_key(settings, question, collection_id, document_id) if cache else None
    scope = cache_scope(settings, collection_id, document_id) if cache else None
    try:
        if key:
            saved = cache.get(key)
            if saved is not None:
                return {
                    **saved,
                    "cache_hit": True,
                    "cache_type": "exact",
                    "answer_generation_called": False,
                }

        query_vector = None
        if cache and settings.answer_cache_mode == "semantic" and collection_id and scope:
            query_vector, matches = search_question_with_vector(
                question, collection_id, document_id, settings
            )
            saved = cache.semantic_get(scope, question, query_vector, matches)
            if saved is not None:
                cache.put(key, saved)
                return {
                    **saved,
                    "cache_hit": True,
                    "cache_type": "semantic",
                    "answer_generation_called": False,
                }
            result, generated = synthesize(question, matches, settings), bool(matches)
        else:
            result, generated = uncached_answer(question, collection_id, document_id, settings)

        current_scope = cache_scope(settings, collection_id, document_id) if cache else None
        if key and scope == current_scope:
            cache.put(key, result)
            if query_vector is not None:
                cache.semantic_put(scope, question, query_vector, result)
        return {
            **result,
            "cache_hit": False,
            "cache_type": "none",
            "answer_generation_called": generated,
        }
    finally:
        if cache:
            cache.close()


def uncached_answer(question, collection_id, document_id, settings):
    matches = (
        search_question(question, collection_id, document_id)
        if collection_id
        else search_question(question)
    )
    return synthesize(question, matches, settings), bool(matches)


def search_question_with_vector(question, collection_id, document_id, settings):
    vector = build_embedding_client(settings).embed_query(question)
    library = Library(settings)
    try:
        return vector, library.search(collection_id, question, document_id, query_vector=vector)
    finally:
        library.close()


def search_question(question, collection_id=None, document_id=None):
    settings = get_settings()
    if collection_id:
        library = Library(settings)
        try:
            return library.search(collection_id, question, document_id)
        finally:
            library.close()
    store = build_vector_store(settings)
    try:
        vector = build_embedding_client(settings).embed_query(question)
        ranked = store.search(vector, settings.context_k)
        return [
            {
                "chunk_id": chunk.chunk_id,
                "title": chunk.metadata.get("title", ""),
                "section": chunk.metadata.get("section", ""),
                "text": chunk.text,
                "score": chunk.score,
                "vector_score": chunk.vector_score,
                "rerank_score": None,
            }
            for chunk in ranked
        ]
    finally:
        store.close()
