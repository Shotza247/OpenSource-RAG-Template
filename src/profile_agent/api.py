import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from profile_agent.agent import ProfileAgent
from profile_agent.config import get_settings
from profile_agent.embeddings import build_embedding_client
from profile_agent.reranking import HFReranker
from profile_agent.retriever import ProfileRetriever
from profile_agent.vector_store import build_vector_store

logger = logging.getLogger("profile_agent")


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=2, max_length=800)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Question must contain at least two characters")
        return value


class Citation(BaseModel):
    chunk_id: str
    title: str
    section: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Citation]
    status: str
    request_id: str


def answer_question(question):
    settings = get_settings()
    settings.require_models()
    store = build_vector_store(settings)
    try:
        retriever = ProfileRetriever(
            build_embedding_client(settings), store, HFReranker(settings), settings
        )
        return ProfileAgent(retriever, settings).ask(question)
    finally:
        store.close()


def create_app(answerer=None):
    app = FastAPI(title="Profile Agent RAG", version="0.2.0")
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "kind": "liveness"}

    @app.post("/ask", response_model=AskResponse)
    def ask(body: AskRequest):
        # Blocking provider calls run in FastAPI's thread pool.
        request_id, started = str(uuid4()), time.monotonic()
        try:
            result = (answerer or answer_question)(body.question)
            return {**result, "request_id": request_id}
        except Exception as exc:  # noqa: BLE001 - public boundary redacts upstream failures
            logger.warning("request_failed id=%s error_type=%s", request_id, type(exc).__name__)
            raise HTTPException(
                503,
                detail={
                    "message": "The assistant is temporarily unavailable.",
                    "request_id": request_id,
                },
            ) from None
        finally:
            logger.info(
                "request_finished id=%s duration_ms=%d",
                request_id,
                (time.monotonic() - started) * 1000,
            )

    return app


app = create_app()
