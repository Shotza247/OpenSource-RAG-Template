"""Shared retrieval and answer workflow, independent of HTTP routes."""

from faq_agent.config import get_settings
from faq_agent.embeddings.embedder import build_embedding_client
from faq_agent.ingestion.service import Library
from faq_agent.llm.client import synthesize
from faq_agent.vectordb.vector_store import build_vector_store


def answer_question(question, collection_id=None, document_id=None):
    settings = get_settings()
    matches = (
        search_question(question, collection_id, document_id)
        if collection_id
        else search_question(question)
    )
    return synthesize(question, matches, settings)


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
