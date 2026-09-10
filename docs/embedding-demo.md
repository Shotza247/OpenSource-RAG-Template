---
noteId: "d95ba030ad2211f1b75c0f8b74e6ab3c"
tags: []

---

# First Live Embedding Demo

## What runs where

Python loads and chunks the local sample. Hugging Face shared inference converts text
to vectors remotely. Qdrant in Docker stores and searches them on this machine.
FastAPI exposes retrieval on port 8767. No LLM is required for POST /search.

The fictional sample is examples/embedding-demo/sample.md. It is NOT a career claim.
The private career source has not been sent to Hugging Face or indexed.

## Configuration

Keep HF_TOKEN in the ignored .env, never in browser code or Git. Its permissions must
allow Inference Providers. The verified configuration on 2026-09-10 is:

```dotenv
EMBEDDING_URL=https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_REVISION=main
VECTOR_DIMENSIONS=384
EMBEDDING_QUERY_PREFIX="Represent this sentence for searching relevant passages: "
EMBEDDING_DOCUMENT_PREFIX=
VECTOR_STORE=qdrant
VECTOR_URL=http://127.0.0.1:6334
COLLECTION=embedding_demo
```

The embedding revision is a local index fingerprint, not a remotely enforced model pin.
Shared providers may change availability or model revision. Re-evaluate and reindex
after model changes; this demo is not an immutable hosted deployment.

[HF pricing](https://huggingface.co/docs/inference-providers/pricing) currently describes
$0.10 monthly credits for free users, subject to change. Open-source models do not mean
unlimited free hosted compute. These calls can consume credits; no paid endpoint or
credit purchase was provisioned here. Stop if credits are exhausted.

## Reproduce ingestion

Activate the project virtual environment. Keep CORPUS_VERSION on the old version until
the new version is verified. The initial run used demo-001; use a fresh version on reruns:

```powershell
python scripts/ingest_profile.py --source examples/embedding-demo --version demo-002 --dry-run
python scripts/ingest_profile.py --source examples/embedding-demo --version demo-002 --approved-public
```

Inspect the candidate in Qdrant and evaluate retrieval before setting
CORPUS_VERSION=demo-002 in .env and restarting the API. Do not reimport demo-001.
The initial sample produces three chunks and 384-dimensional vectors. The collection
name includes a fingerprint of the model and chunking settings.

The initial live run passed both direct retrieval and POST /search, with Atlas ranked
first (cosine score 0.74186003). The separate automated suite passed 48 tests.
Qdrant's exact count API returned 3 points. Its indexed_vectors_count can still be zero:
small collections can be searched without building an HNSW index. See
[Qdrant collection counts](https://qdrant.tech/documentation/manage-data/collections/).

## Inspect and query

1. Open http://127.0.0.1:6334/dashboard#/collections and select embedding_demo-bd228c87eb28.
2. Inspect its points and payloads: text, section, title and corpus_version=demo-001.
3. Open http://127.0.0.1:8767/docs and expand POST /search. Choose Try it out.
4. Submit the request below. Project Atlas should be the first match.

```json
{"question":"Which project displays rainfall?"}
```

Or use PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8767/search -ContentType application/json -Body '{"question":"Which project displays rainfall?"}'
```

Each search makes one hosted query-embedding call. Responses contain ranked source text,
cosine similarity scores and a request ID, not generated answers. Scores are not confidence
probabilities. Empty matches are not proof of a broken endpoint: check the active corpus.

GET /health is liveness only. POST /ask still needs LLM_MODEL and an accessible chat model.
Automated tests use simulated providers; the live demo is separate evidence.
Keep this API local until authentication/rate limits and deployment controls are added.
Streamlit can later call /search for inspection and /ask for grounded chat.
