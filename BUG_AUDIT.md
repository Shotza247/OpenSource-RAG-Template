# Setup and Verification Audit

## 2026-09-10 - First real hosted embedding and retrieval

- Status: fixed for embedding/search; chat model setup remains pending.
- Initial state: private HF_TOKEN present, EMBEDDING_URL missing, dimensions incorrectly
  set to 484, and new Qdrant collections empty.
- Public HF model metadata confirmed BAAI/bge-small-en-v1.5 live for feature-extraction.
  One synthetic sentence returned HTTP 200 and shape [1, 384] from the shared HF router.
- Updated only embedding URL/model/dimensions and demo collection/version in ignored .env.
  Preserved credentials and unrelated configuration. No dedicated endpoint or purchase.
- examples/embedding-demo/sample.md: fictional public-safe data; ingestion produced
  three chunks in embedding_demo-bd228c87eb28, corpus demo-001. Private career text untouched.
- Live candidate retrieval ranked Project Atlas first for a rainfall question, then
  demo-001 was activated. Exact Qdrant count API returned 3; vector size 384, Cosine.
- src/profile_agent/api.py: added POST /search, query embedding plus vector retrieval,
  no LLM/reranker, allowlisted response fields, generic provider-error responses.
- Restarted only new API 8767. Initial HTTP probe preceded startup and was refused;
  after startup, OpenAPI listed /health, /search, /ask. Live /search returned Atlas first
  with score 0.74186003 and a request ID. Original 8766/6333 services unchanged.
- Tests: initial run 44 passed, 4 fixture errors due to Windows shared-temp permissions.
  Rerun with a fresh project-local --basetemp: 48 passed, 2 existing upstream warnings.
  Ruff check passed. Automated simulated-provider tests are separate from live evidence.
- docs/embedding-demo.md documents configuration, costs, ingestion, inspection and search.
- Follow-up: choose chat model for /ask, curate public career corpus, evaluate broader
  retrieval quality, then add Streamlit. One synthetic query is not a quality benchmark.
- Security: token not printed or committed; keep API local pending access/rate controls.
  Shared HF inference consumes limited included credits; free usage is not unlimited.

## 2026-09-10 - Separate clean baseline

- Direction: user requested a separate repository while keeping the original intact.
- Scope: active backend, tests, settings template, locked dependencies, focused documentation.
- Excluded: old Git history, legacy notebook/template scaffolding, Box placeholder,
  MongoDB reference material, editor-generated index and migration artifacts.
- Configuration: .env.example declares keys; .env is local and ignored.
  setup_env.py syncs known keys with a local backup and accepts HF_TOKEN through hidden input.
  The original project's .env is never copied into the new repository.
- Document verification: the copied private master profile loaded successfully:
  38,341 normalized characters, 118 chunks, largest chunk 998 characters.
  Dry run used 384 dimensions, zero model calls and zero database writes.
- The private document is excluded from Git and deployment. Public publication requires review.
- Initial checks: 11 focused setup/chunk/embedding tests passed before the additional
  dry-run regression test was added.
- Final verification: 42 tests passed; Ruff passed. Upstream Starlette/AnyIO deprecation
  and Qdrant in-memory payload-index warnings remain; no test failed.
- Pending: real embedding and chat model setup, public corpus ingestion, Google Drive sync
  and GitHub remote/publication. No paid endpoint was provisioned.

## Independent runtime verification

- Installed the locked dependencies into this repository's own .venv. One uncached package
  required a download; no hosted inference was used.
- Re-ran the full suite in that environment: 42 passed, two upstream warnings; Ruff passed.
- Initialized the new local .env with all template keys, blank model credentials and
  separate database ports. VECTOR_DIMENSIONS is 384 for the BGE-small default.
- New Qdrant: localhost 6334, own opensource-rag-template_qdrant_data volume.
  Readiness passed; collections are empty. Original Qdrant 6333 was unchanged.
- New API: localhost 8767, own Python environment; GET /health passed.
  Original API 8766 was unchanged.
- Git ignores the private .env, private master document, local logs and runtime files.
  A separate initial-baseline branch is prepared; no GitHub remote or push is configured.
