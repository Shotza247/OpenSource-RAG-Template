# Evaluation

Tests validate software contracts using synthetic data and simulated model calls.
They do not show that the user's master document has been embedded or answered correctly.

First preview chunk counts and section boundaries locally. Then, on approved public text:

1. Label questions with relevant source IDs and expected abstentions.
2. Measure retrieval recall and reciprocal rank with scripts/evaluate_retrieval.py.
3. Compare reranking enabled and disabled with the same questions.
4. Review whether every answer claim is supported by its cited passage.
5. Test unknown facts, conflicting dates and document prompt injection.
6. Record latency, errors, model revision, corpus version and hosting-credit usage.

The ingestion CLI prints source IDs after import. Use question and expected_source_ids
fields in a reviewed JSONL evaluation file. Keep private reference answers out of Git.
