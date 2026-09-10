import json
from dataclasses import replace
from unittest.mock import Mock

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from profile_agent.agent import ProfileAgent, validate_answer
from profile_agent.chunking import chunk_document
from profile_agent.config import Settings
from profile_agent.document_loader import load_documents
from profile_agent.reranking import HFReranker
from profile_agent.schemas import RetrievedChunk, SourceDocument


def chunk(identifier="a"):
    return RetrievedChunk(
        identifier,
        "Built a dashboard",
        0.9,
        {
            "source_id": "public",
            "title": "Profile",
            "section": "Projects",
            "source_path": "PRIVATE",
        },
    )


@pytest.mark.parametrize("size,overlap", [(0, 0), (5, 5), (5, -1)])
def test_chunk_configuration_rejected(size, overlap):
    with pytest.raises(ValueError):
        chunk_document(SourceDocument("a", "p", "t", "text"), max_chars=size, overlap_chars=overlap)


def test_chunk_bounds_ids_and_source_paths():
    doc = SourceDocument("a", "PRIVATE", "Profile", "# Projects\n" + "dashboard detail " * 100)
    chunks = chunk_document(doc, max_chars=80, overlap_chars=20)
    assert all(0 < len(c.text) <= 80 for c in chunks)
    assert all("source_path" not in c.metadata for c in chunks)
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert chunks == chunk_document(doc, max_chars=80, overlap_chars=20)


def test_source_names_do_not_collide(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "resume.txt").write_text("One")
    (tmp_path / "b" / "resume.txt").write_text("Two")
    docs = load_documents(tmp_path)
    assert len({d.source_id for d in docs}) == 2


def test_embedding_configuration_changes_index():
    s = Settings()
    assert replace(s, embedding_model="different").index_name != s.index_name
    assert replace(s, embedding_query_prefix="query: ").index_name != s.index_name
    assert replace(s, corpus_version="v2").index_name == s.index_name


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"answer":"invented","citation_ids":["unknown"]}',
        '{"answer":"invented","citation_ids":[]}',
        '{"answer":3,"citation_ids":["a"]}',
    ],
)
def test_invalid_citations_abstain(raw):
    assert validate_answer(raw, {"a": chunk()})["status"] == "insufficient_evidence"


def test_valid_citation_does_not_expose_private_metadata():
    result = validate_answer(
        '{"answer":"Built a dashboard","citation_ids":["a","a"]}', {"a": chunk()}
    )
    assert len(result["sources"]) == 1
    assert "PRIVATE" not in json.dumps(result)


def test_reranker_reorders_and_thresholds(monkeypatch):
    monkeypatch.setattr(
        "profile_agent.reranking.requests.post",
        lambda *a, **k: Mock(json=lambda: [{"index": 1, "score": 0.9}, {"index": 0, "score": 0.1}]),
    )
    s = replace(Settings(), rerank_url="https://test/rerank", rerank_min_score=0.5)
    assert HFReranker(s).rerank("question", [chunk("a"), chunk("b")]) == [chunk("b")]


def test_reranker_rejects_duplicate_indices(monkeypatch):
    monkeypatch.setattr(
        "profile_agent.reranking.requests.post",
        lambda *a, **k: Mock(json=lambda: [{"index": 0, "score": 0.9}, {"index": 0, "score": 0.1}]),
    )
    with pytest.raises(ValueError):
        HFReranker(replace(Settings(), rerank_url="https://test/rerank")).rerank(
            "question", [chunk("a"), chunk("b")]
        )


class FakeModel(BaseChatModel):
    calls: int = 0
    loop: bool = False

    @property
    def _llm_type(self):
        return "test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        if self.calls == 1 or self.loop:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_profile",
                        "args": {"query": "projects"},
                        "id": str(self.calls),
                        "type": "tool_call",
                    }
                ],
            )
        else:
            message = AIMessage(content='{"answer":"Built a dashboard","citation_ids":["a"]}')
        return ChatResult(generations=[ChatGeneration(message=message)])


def test_real_langchain_graph_with_mock_model():
    retriever = Mock()
    retriever.retrieve.return_value = [chunk()]
    model = FakeModel()
    result = ProfileAgent(retriever, Settings(), model).ask("projects")
    assert result["status"] == "answered"
    assert retriever.retrieve.call_count == 2
    assert model.calls == 2


def test_empty_retrieval_never_calls_model():
    retriever = Mock()
    retriever.retrieve.return_value = []
    model = FakeModel()
    result = ProfileAgent(retriever, Settings(), model).ask("unknown")
    assert result["status"] == "insufficient_evidence"
    assert model.calls == 0


def test_tool_loop_has_bounded_retrieval():
    from langgraph.errors import GraphRecursionError

    retriever = Mock()
    retriever.retrieve.return_value = [chunk()]
    with pytest.raises(GraphRecursionError):
        ProfileAgent(retriever, Settings(), FakeModel(loop=True)).ask("projects")
    assert retriever.retrieve.call_count == 2
