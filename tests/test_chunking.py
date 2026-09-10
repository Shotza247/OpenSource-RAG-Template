from profile_agent.chunking import chunk_document
from profile_agent.schemas import SourceDocument


def test_chunk_document_keeps_section_metadata() -> None:
    doc = SourceDocument(
        source_id="profile",
        path="profile.md",
        title="Profile",
        text="# Experience\nBuilt AI systems.\n\n# Projects\nCreated Pulse360 and Fleet360.",
    )

    chunks = chunk_document(doc, max_chars=80, overlap_chars=10)

    assert chunks
    assert {chunk.metadata["section"] for chunk in chunks} == {"Experience", "Projects"}
    assert all(chunk.chunk_id for chunk in chunks)
