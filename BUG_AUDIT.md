# Verification and recovery

## 2026-09-15 - Responsibility-based project cleanup

- Status: verified locally.
- Changes: grouped active modules by responsibility; removed retired orchestration
  and reranking experiments/dependencies; consolidated duplicate guides. Updated
  evaluation to call the current search API. Existing Chroma CLI adapter retained.
- Compatibility: stable Qdrant index fingerprint and SQLite path have regression
  tests. Private configuration and stored documents are not migrated or deleted.
- Recovery: the pre-refactor code/docs/tests are saved in an ignored timestamped
  `.local/refactor-backups/` directory before files are replaced. The old long-form
  investigation log is included there, not mixed into current setup instructions.
  This run's backup is `.local/refactor-backups/20260915-145959`.
- Baseline: before cleanup, 31 offline tests passed; live synthetic ingestion,
  search and cited synthesis succeeded.
- Post-refactor verification: all 55 remaining tests passed, Ruff passed, and uv
  sync removed 28 retired dependency packages plus rebuilt the project package.
  Warnings are limited to upstream test-client deprecations and the in-memory
  Qdrant payload-index warning; no test failed.
- Live API restarted via main:app on port 8767. Health and all six route paths
  remain available. pulse360_faq has 0 documents; ui_smoke_test has 1 document
  and 1 chunk, unchanged from before cleanup. Both profiles remain compatible.
- Live hosted smoke, included credits only: search returned vector_score 0.8309836;
  ask answered "Project Atlas displays rainfall." with one citation. Default demo
  search returned 3 matches. Streamlit health is OK on port 8502.
- No document ingestion, .env edits, Qdrant migration or Docker volume changes
  were performed by this refactor. Container deployment was not tested.

## Environment note

Windows Application Control rejects PyArrow's data-table binary in this environment.
The working UI uses native Streamlit text controls instead. Reranking and LangGraph
are not dependencies of the current workflow. No Windows policy was weakened.

API errors expose a request ID, not provider secrets. Inspect the corresponding
server stderr log under .local for the error type. Check service health, configured
endpoint URLs, model access and remaining hosted credits before retrying calls.
