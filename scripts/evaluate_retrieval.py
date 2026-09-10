"""Retrieval metrics on reviewed JSONL: question and expected_source_ids."""

import argparse
import json

from profile_agent.config import get_settings
from profile_agent.embeddings import build_embedding_client
from profile_agent.reranking import HFReranker
from profile_agent.retriever import ProfileRetriever
from profile_agent.vector_store import build_vector_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    args = parser.parse_args()
    with open(args.dataset, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows:
        parser.error("Dataset is empty")
    settings = get_settings()
    store = build_vector_store(settings)
    scores = []
    try:
        retriever = ProfileRetriever(
            build_embedding_client(settings), store, HFReranker(settings), settings
        )
        for row in rows:
            expected = set(row["expected_source_ids"])
            if not expected:
                continue
            hits = retriever.retrieve(row["question"])
            sources = [hit.metadata["source_id"] for hit in hits]
            recall = len(expected.intersection(sources)) / len(expected)
            rank = next((1 / i for i, source in enumerate(sources, 1) if source in expected), 0)
            scores.append((recall, rank))
    finally:
        store.close()
    if not scores:
        parser.error("No questions with relevant source labels")
    print(
        json.dumps(
            {
                "questions": len(scores),
                "context_k": settings.context_k,
                "recall_at_k": sum(x[0] for x in scores) / len(scores),
                "mrr": sum(x[1] for x in scores) / len(scores),
                "corpus_version": settings.corpus_version,
                "index": settings.index_name,
            }
        )
    )


if __name__ == "__main__":
    main()
