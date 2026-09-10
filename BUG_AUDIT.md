# Setup and Verification Audit

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
