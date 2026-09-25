---
noteId: "b48ef8e0b51711f19852c515e8cc9d2f"
tags: []

---

# Next milestone: fresh Qdrant Cloud ingestion

Update 2026-09-21: the synthetic FAQ upload, cloud search and answer milestone has
passed. See [cloud runtime and evidence](cloud-runtime.md). The checklist below
records the original plan; full Pulse360 PDF testing and deployment remain pending.

## Verified versus pending

Verified on 2026-09-18: local snapshots and SQLite integrity; authenticated cloud
read/write; migration of demo (3 points) and smoke test (1 point); complete copied
point comparison and stored-vector query parity. The FAQ (30 points) remains local.
Evidence: `.local/backups/20260918T135810Z` and
`.local/migrations/20260918T145953Z/report.json`.

At the time of the 2026-09-18 baseline, fresh ingestion/search/ask were not verified.
These passed for the synthetic sample on 2026-09-21. Vercel deployment is not verified.
Database-level query parity is not an end-to-end application test.

## Safe test procedure for the next step

1. Confirm explicit permission to send the selected FAQ to the existing HF provider
   and Qdrant Cloud using included credits only. Keep secrets private.
2. Prepare an isolated test runtime with the SAME model, dimensions, prefixes and
   chunk settings, the cloud URL/key, and a separate catalog. The current Library
   defaults to .local/library.sqlite3; run_cloud_api.py now forces the separate
   .local/cloud/library.sqlite3 catalog. This isolation is implemented and tested.
   Do not overwrite the original .env or silently reuse local collection profiles.
3. Start the isolated API and Streamlit test instance on unused ports; configure
   FAQ_API_URL to the test API. Validate health and the intended cloud destination.
4. Create a uniquely named fresh collection through the UI. Migration of the two
   test collections did not register them in a cloud application catalog, so they
   should not automatically appear as managed collections.
5. Upload the approved FAQ, review extracted pages/chunks and embedding profile.
   Preview must not call HF. Record the preview chunk count.
6. Approve embed/store once. Verify cloud point count matches the committed catalog
   and chunk count; inspect filename/page/source metadata without logging full text.
7. Test /search with the UI's logical collection ID and a document-specific question.
   Check passage relevance and vector scores. Test document scope and no-match cases.
8. Test /ask against that SAME collection. Verify grounded answer and valid citations;
   citation-ID validity alone is not proof of factual correctness.
9. Verify duplicate upload idempotence and persistence across a test API restart.
   Confirm original local collections/catalog still match the baseline.
10. Record request IDs, counts, model profile, outcomes and HF usage without secrets
    or raw personal questions. Stop if included credits are exhausted.

## Deployment boundary

A local API using Qdrant Cloud is a cloud-storage integration test, not a deployed
backend. Durable hosted catalog storage, authentication/write controls, quotas,
upload constraints and deployment verification still need work before Vercel.
Supabas_pulse360_RAG owns the Pulse360 PostgreSQL/pgvector implementation separately.
Do not replace this project's Qdrant workflow with pgvector as part of this test.
No cloud ingestion or paid service provisioning is authorized by this document alone.
