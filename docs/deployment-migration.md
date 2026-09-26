# Deployment migration status

## 2026-09-21 - Isolated cloud upload runtime

- Implemented two API runtimes and a Streamlit sidebar toggle; active .env and local data remain unchanged.
- Cloud API: localhost:8768, with a separate .local/cloud/library.sqlite3 catalog. Local API remains localhost:8767.
- Fresh synthetic sample uploaded/previewed/approved/stored through Streamlit: 5 cloud points in faq_ui_cloud_upload_smoke_20260921-bd228c87eb28.
- Cloud /search and /ask returned 200; support-hours answer grounded in the matching passage (score 0.7735939).
- Fixed the missing document_id keyword index required by cloud filtering; new managed collections create it automatically.
- 58 offline tests and changed-file lint passed. See [runtime guide](cloud-runtime.md) for launch instructions, limitations and remaining deployment gates.
- The earlier pending-status entries below are historical, not the current synthetic-test result.

## 2026-09-18 - Qdrant Cloud connection preparation

- Destination: Qdrant Cloud, AWS Frankfurt (eu-central-1).
- Local backups: `.local/backups/20260918T135810Z`; snapshots and SQLite integrity verified, restoration not tested.
- Migrate only `embedding_demo-bd228c87eb28` (3 points) and `faq_ui_ui_smoke_test-bd228c87eb28` (1 point).
- Preserve the local Pulse360 FAQ collection (30 points). Test fresh FAQ ingestion through Streamlit against cloud later.
- `.env.qdrant-cloud` is an isolated, Git-ignored profile. It is not loaded by the running application.
- `scripts/check_qdrant_cloud.py` performs an authenticated GET /collections only; no HF calls, writes, or migrations.
- Authenticated cloud read access passed; migration subsequently verified write access.
- Historical plan: Supabase PostgreSQL would replace this project's SQLite catalog. On 2026-09-20 the Pulse360 Supabase/pgvector work moved to a separate project; no catalog migration has been implemented here.
- Do not deploy with the local SQLite catalog or copy its local-Qdrant profiles unchanged into cloud configuration.
- Current next gate: isolated fresh Streamlit upload to Qdrant Cloud and API retrieval/synthesis verification. Durable hosted catalog selection and deployment remain pending for this independent template.
- Preserve the working local environment until cloud acceptance tests pass. No secrets belong in documentation or Git.

## 2026-09-18 - Two test collections migrated and verified

- Status: vector migration verified; application cutover and Supabase migration pending.
- Copied `embedding_demo-bd228c87eb28` (3 points) and `faq_ui_ui_smoke_test-bd228c87eb28` (1 point) only.
- Preserved point IDs, payloads, 384-dimensional cosine vectors and the demo's corpus_version keyword index.
- Checked all copied points against local originals; vector tolerance: relative 1e-6, absolute 1e-7.
- Compared exact vector queries using an existing stored vector per collection: result IDs matched and scores agreed within 1e-5 tolerance. This is database-level validation, not a hosted /ask or fresh embedding test.
- Reproducible script: `scripts/migrate_test_collections.py` performs read-only preflight by default; `--apply` creates and copies. It refuses existing destination collections, including on rerun, to prevent accidental overwrite.
- Evidence: `.local/migrations/20260918T145953Z/report.json`.
- No HF calls, re-embedding, local data deletions, active .env changes, or catalog changes.
- The local Pulse360 FAQ collection remains local. Cloud inventory contains only the two approved test collections.
- This was the proposed next step on 2026-09-18; see the project separation decision below for the current direction.

## 2026-09-20 - Separate Supabase template

- Created sibling `Supabas_pulse360_RAG` as a sanitized copy of reusable source, tests, dependency lock, scripts and synthetic examples. No secrets, private documents, catalog, vectors or Git history copied.
- Source revision at separation: `62d6d3af3811461c3f907b14363a2fd8bee26b03`; the copy manifest records the actual file hashes, including any working-tree differences.
- New project contains a README and HANDOFF specifying PostgreSQL catalog + pgvector as the target. Its inherited runtime is still Qdrant/SQLite; Supabase is not implemented.
- OpenSource runtime code, active configuration, local catalog and vector stores are unchanged by the split. Only documentation is updated here.
- Next acceptance gate: [fresh cloud upload, search and ask](cloud-upload-acceptance.md). These have NOT yet passed; only the two-test-collection migration and database query parity have passed.
- No new chat, cloud resource, Git commit or deployment was created by this split.
- Copy verification: 54 baseline files matched SHA-256; all 55 copied offline tests passed using the existing dependency environment and the new project's source paths. This does not verify Supabase or fresh cloud ingestion. See the new project's BUG_AUDIT.md for the resolved test-output directory setup error and warnings.
