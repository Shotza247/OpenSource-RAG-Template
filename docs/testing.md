---
noteId: "8ddceac0b10e11f183f7f156305e3c6d"
tags: []

---

# Testing and evaluation

## Offline tests

Install dev and UI extras, then run from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check src scripts tests main.py streamlit_app.py
```

Tests use simulated providers and in-memory Qdrant, not HF credits. They cover
request validation, error redaction, citation validation, chunk bounds, embedding
dimensions, corpus isolation, upload approval, duplicate handling, preview expiry,
partial commit recovery, UI controls and configuration compatibility.

The UI uses native text elements for document lists: this machine's Application
Control policy rejects PyArrow's data-table runtime. No security policy changes
are necessary for the current UI.

## Live checks

1. Confirm GET /health returns 200; it is liveness, not a provider readiness check.
2. Confirm GET /collections lists managed collections and that the selected
   collection's documents remain visible after a restart.
3. Select ui_smoke_test in Streamlit and ask "What does Project Atlas show?".
   Search should return the synthetic chunk; Answer should cite it. These calls
   consume hosted credits. Use included credits only.
4. For new documents, preview locally before approval. Verify filename, pages and
   chunk boundaries. Then approve and embed deliberately.
5. Test answerable, unanswerable and misleading questions against reviewed facts.

The earlier smoke fixture is one synthetic chunk, not an accuracy benchmark.
The Pulse360 PDF was locally previewed during UI setup (30 chunks over 10 pages);
its current ingestion status is shown by the UI, not assumed from this document.

## Retrieval metrics

Create a reviewed JSON array using chunk IDs returned by /search:

```json
[{"question":"Your FAQ question", "expected_chunk_ids":["a-real-chunk-id"]}]
```

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py labels.json --collection pulse360_faq
```

The evaluator calls the active /search endpoint and reports mean recall at the
configured CONTEXT_K and mean reciprocal rank. It makes embedding calls, not LLM
calls. Labels are collection-specific; re-chunking changes chunk IDs. Evaluate
answer correctness and source support separately from retrieval ranking.

## CLI corpus

For the separate versioned-corpus workflow, local inspection requires no approval:

```powershell
.\.venv\Scripts\python.exe scripts/ingest_faq.py --source examples/faq --version review-001 --dry-run
```

To actually ingest, use a new version and explicitly pass --approved-public only
after reviewing all files in the source folder. This CLI does not register UI
documents. Prefer the UI for individual collection-scoped uploads.

# Test Redis cache

- Inspect Saved Answers
From the OpenSource-RAG-Template terminal, list cached keys:

```
docker compose exec -T redis redis-cli --scan --pattern 'faq-answer-v1:*'
```

- Sample Output Key:
```
faq-answer-v1:d24ce5499d1ef7f0fa7662539e2fd016a993639055a61058f24ab6c1515712ef
```

- View the saved answer and citations
```
docker compose exec -T redis redis-cli GET "faq-answer-v1:d24ce5499d1ef7f0fa7662539e2fd016a993639055a61058f24ab6c1515712ef"
```
- Output:
```
{"answer":"As a System Admin, you can access aggregated audit data, platform adoption metrics, operational analytics, and AI-usage analytics. The System Admin dashboard is for monitoring platform health and behavior, such as adoption, operational throughput, aggregate workflow health, AI usage metadata, token totals, and recent governance events. System Admins should not see sensitive review comments, individual review scores, or a direct map of who nominated whom. Access is role-based and enforced on both the user interface and server-side APIs, with all sensitive queries and mutations verified for identity, role, organization scope, and permitted entity scope.",
"status":"answered",
"sources":
[{"chunk_id":"be0c944d2d21b98fbadd2d28","title":"Pulse360_Platform_FAQ","section":"FAQ","vector_score":0.73077905,"rerank_score":null,"filename":"Pulse360_Platform_FAQ.pdf","page":2,"document_id":"613801d9080c9036deea04733fe7758b60924d191d0222d12bca3ab10f89ddae"},{"chunk_id":"da82ed4be93097c5ecd76f93","title":"Pulse360_Platform_FAQ","section":"FAQ","vector_score":0.6994294,"rerank_score":null,"filename":"Pulse360_Platform_FAQ.pdf","page":2,"document_id":"613801d9080c9036deea04733fe7758b60924d191d0222d12bca3ab10f89ddae"},{"chunk_id":"f76cfc74eb31974854a06ac9","title":"Pulse360_Platform_FAQ","section":"FAQ","vector_score":0.6949256,"rerank_score":null,"filename":"Pulse360_Platform_FAQ.pdf","page":5,"document_id":"613801d9080c9036deea04733fe7758b60924d191d0222d12bca3ab10f89ddae"}]}
```

- Check remaining lifetime in seconds:
```
docker compose exec -T redis redis-cli TTL "faq-answer-v1:d24ce5499d1ef7f0fa7662539e2fd016a993639055a61058f24ab6c1515712ef"
```

- Output depending on the time:
```
2075
```