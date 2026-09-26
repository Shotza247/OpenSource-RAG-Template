# Verification and recovery

## 2026-09-25 - Documentation and roadmap refresh

- Status: passed in staged documentation; repository copy requires the user's
  local write operation because this chat does not own that project workspace.
- Goal: align documentation with semantic cache verification, current commits and
  the planned durable-answer promotion tier.
- Changes: removed obsolete note metadata and raw cached-answer examples; refreshed
  diagrams; added a single feature/issue roadmap with explicit implemented versus
  planned status.
- Evidence: repository review found stale 55-test wording and old cache-only
  diagrams; the semantic baseline is 73 passed with two opt-in skips, plus real
  Redis and live hosted acceptance already recorded above.
- Follow-up: copy staged files into the repository, review Mermaid rendering, then
  create separate semantic-cache and documentation commits.

## 2026-09-25 - Paraphrase cache misses

- Status: fixed for the three target paraphrases; broader FAQ calibration remains monitoring.
- Symptom: three equivalent System Admin questions created separate exact keys;
  one wording missed despite substantially identical retrieval context.
- Cause: the first cache implementation intentionally hashed exact question text
  and performed no semantic comparison.
- Changes: added opt-in semantic mode using the existing hosted query embedding,
  current Qdrant evidence overlap, and conservative role/negation intent guards.
  Semantic hits skip answer generation and are promoted to exact keys.
- Calibration: hosted BGE embeddings scored 0.9028 between "access" and "see" and
  0.8630 between "access" and "As the system admin...see". All three retrieved
  the same three answer-supporting chunks. The default threshold is 0.85. A negated
  control scored 0.8418 against "access" and is independently rejected by polarity;
  a manager control scored 0.6436 and is rejected by role.
- Reliability fix: real Docker Redis exposed occasional read fallback at the former
  0.3-second socket timeout. `REDIS_TIMEOUT` now defaults to 1.0 second and remains
  bounded/configurable.
- Verification: 73 full-suite tests passed (2 opt-in skips). With real Docker Redis,
  10 cache tests passed, including one simulated generation and two semantic hits
  for the three target paraphrases. Repository lint passed for all changed files;
  one pre-existing style finding remains in scripts/migrate_test_collections.py.
- Live acceptance: an isolated semantic API on port 8770 with a fresh namespace
  returned one generated answer for "What can a System Admin access?", followed by
  semantic hits for "What can a System Admin see?" and "As the system admin what
  can i see?". Both hits reused the same three cited chunks and reported
  `answer_generation_called: false`. Request IDs were distinct.
- Follow-up: add cache decision monitoring. Broader FAQ evaluation is required
  before lowering thresholds.

## 2026-09-24 - Optional exact-answer Redis cache

- Added Docker Redis on loopback port 6380, optional redis-py dependency, catalog-scoped
  exact answer caching, TTL, failure fallback and cache telemetry on `/ask`.
- Existing `.env`, Qdrant collections, catalogs, `/search` and running API configuration
  were not changed. Caching remains off until explicitly enabled and the API restarted.
- Verification: 70 offline tests passed with one opt-in test skipped; then all 71
  passed with real Docker Redis, using simulated retrieval and synthesis. No HF calls.
- Real Redis test verified one generation across two identical API requests, TTL,
  fresh request IDs and cleanup of its own unique key.
- During the second suite Windows emitted 0x8007000e from platform._wmi_query while
  importing Streamlit. The suite nevertheless completed with all tests passing.
  Cause is not established; no security settings or Streamlit code were changed.
- Two import-order lint findings were corrected mechanically. Three existing
  dependency/local-Qdrant warnings remain. See docs/answer-cache.md for activation,
  invalidation limits and deferred semantic reuse/concurrent-miss locking.

## 2026-09-23 - Streamlit running without API processes

- Status: recovered. Streamlit port 8502 responded, but both API ports 8767 and 8768 had no listeners.
- Restarted only the missing local and cloud API runtimes using existing configuration and separate catalogs. No code, credentials, collections or documents changed.
- Verified HTTP 200 from /health AND /collections on both runtimes. No HF calls were made.
- Logs: .local/recovery-20260923-8767.*.log and .local/recovery-20260923-8768.*.log.
- The cause of the earlier process exits is unknown. These are locally running processes, not automatically managed deployed services. Starting Streamlit alone does not start either API.
- Recovery from the project directory: run `.venv\\Scripts\\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8767` for local, and `.venv\\Scripts\\python.exe scripts/run_cloud_api.py --port 8768` for cloud. Use separate terminals; do not launch duplicates on occupied ports.

## 2026-09-21 - Invalid collection input incorrectly reported as 503

- Request 92a95b95-72e0-47f7-9927-d8852484e77a mapped to RequestValidationError in the cloud API log, not a provider outage.
- Cause: the generator dependency's broad error-redaction context caught FastAPI request validation errors during dependency unwinding and converted them to 503.
- Fix: preserve RequestValidationError alongside HTTPException; retain redaction for real provider failures. Add explicit UI validation and readable collection naming guidance.
- Regression coverage exercises the real generator dependency (mocking only Library), invalid names/missing fields/types, successful creation, provider-error redaction, and UI rejection before a POST.
- Validation rules unchanged: 3-48 characters, initial lowercase letter, then lowercase letters/digits/underscore/hyphen. No collection renamed or deleted.
- Verification: all 65 offline tests passed, changed-file Ruff checks passed; both API processes reloaded and live invalid-name requests returned 422 rather than 503. No model calls or collection writes were required.

## 2026-09-21 - Cloud runtime and document filter index

- Status: fixed and verified for synthetic FAQ upload/search/answer.
- Added isolated cloud catalog and launcher plus UI destination toggle/state reset.
- Streamlit uploaded and stored 5 synthetic chunks in the new cloud test collection.
- Initial search returned 503; direct stored-vector diagnostic returned Qdrant 400:
  Index required but not found for document_id of type keyword.
- Repaired only the new test collection's index; new collection creation now adds it.
- Cloud search request d997c6aa-55a3-4484-9546-aa8a8ed9af4c returned 200.
- Cloud answer request a513631e-7c43-4ab1-bc4a-6da327518579 returned 200 with a correct cited support-hours answer.
- 58 offline tests passed and changed-file lint passed. An intermediate test run
  hit a Windows PermissionError replacing a fixture .env under the long project
  test path; a fresh system-temp base directory passed without application changes.
- Three warnings remain (Starlette/httpx, AnyIO, in-memory Qdrant payload indexes).
- No original .env, catalog or local vectors changed; Supabase sibling untouched.
- Remaining: full FAQ test, durable hosted catalog, authentication/rate limits and
  actual API deployment. Sample front matter is currently chunked as content.

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
