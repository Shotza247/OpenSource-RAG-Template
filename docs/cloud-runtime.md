# Local and Qdrant Cloud testing

The Streamlit sidebar's **Qdrant Cloud** toggle selects an API runtime, not a data
migration. Off routes to FAQ_API_URL (default http://127.0.0.1:8767); on routes to
FAQ_CLOUD_API_URL (default http://127.0.0.1:8768). Both URLs are server-side UI settings.
Switching clears previews, upload approvals, selected documents and question history.
It does not copy/delete collections, transfer documents or replace local data.

## Storage separation

| Runtime | Vector destination | Catalog |
| --- | --- | --- |
| Local API | VECTOR_URL in the original .env | .local/library.sqlite3 by default |
| Cloud-test API | QDRANT_CLOUD_URL in .env.qdrant-cloud | .local/cloud/library.sqlite3 |

Cloud credentials never travel to the browser. The cloud launcher sets RAG_TARGET=cloud
for its own process and fails closed on missing/invalid cloud configuration. Its
catalog location is forced to a separate path. A local runtime may override
CATALOG_PATH; the default remains backward compatible. Do not point it to the cloud catalog.
Cloud testing shares the original HF model settings, not its catalog or vector URL.

## Launch

Keep the existing local API and Streamlit running. In a separate terminal from the
project root, launch the cloud API:

```powershell
.\.venv\Scripts\python.exe scripts/run_cloud_api.py --port 8768
```

If ports are occupied, choose an unused cloud port and set FAQ_CLOUD_API_URL for
the Streamlit process accordingly. Restart the UI for environment-variable changes.
Refresh http://127.0.0.1:8502/ after source changes. The sidebar API docs link follows
the selected runtime. Never swap the configured URL destinations while requests run.

Create a new collection after selecting the destination, upload, preview, approve,
then embed/store. Search and Answer use the same selected destination. Existing raw
Qdrant collections are not automatically registered in a fresh application catalog.
Use a new collection name when recreating a local document in cloud. Moving existing
vectors and catalog mappings is an explicit separate migration operation.

All newly created managed collections receive a document_id keyword index, required
by Qdrant Cloud's document filters. Pre-existing collections lacking this index need
an explicit index repair; do not disable the committed-document filter.

## Verification on 2026-09-21

- Browser: switched to cloud, created cloud_upload_smoke_20260921, uploaded synthetic
  examples/faq/sample.md, previewed and approved storage through Streamlit.
- Stored 5 chunks, 384 dimensions; the sample includes note-taking front matter,
  which is currently treated as content. Front-matter exclusion remains a quality follow-up.
- Cloud /search returned 200 with the correct support-hours passage (score 0.7735939).
- Cloud /ask returned 200: support Monday-Friday, 09:00-17:00 UTC, with its citation.
- Initial search 503 was Qdrant's missing document_id keyword index; repaired the
  test collection and added automatic index creation for future collections.
- Offline suite: 58 passed; changed-file Ruff checks passed. Three upstream/local
  emulation warnings remain. No Supabase files were changed.

This verifies a synthetic cloud-storage workflow, not the full Pulse360 PDF. APIs,
Streamlit and both SQLite catalogs still run on this computer. Cloud vector storage
is NOT a deployed backend; durable hosted metadata, write authorization, quotas and
deployment verification remain required. No paid endpoint or new model was provisioned.
Redis answer caching has been verified locally. A hosted Redis deployment and its
network/authentication configuration are still pending.
