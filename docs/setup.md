# Local Setup

## Environment

Use Python 3.12 and uv. From this repository:

```powershell
uv sync --locked --python 3.12 --extra dev
.venv\Scripts\Activate.ps1
python scripts/setup_env.py --sync
python scripts/setup_env.py --token
```

The token prompt hides your input and writes HF_TOKEN to .env without printing it.
The sync command preserves current recognized settings and archives an existing .env
under .local/archive before rebuilding its key list. It does not fetch credentials from
the old project. Run without flags to see presence checks, never secret values.
Restart the API after changes because configuration is cached.

This local copy uses QDRANT_PORT=6334, VECTOR_URL=http://127.0.0.1:6334 and
CHROMA_PORT=8002 to avoid the original project's services. .env.example uses standard
template ports. Keep VECTOR_URL aligned with whichever service is selected.

## Database

```powershell
docker compose up -d qdrant
docker compose ps
docker compose stop qdrant
```

Qdrant runs in Docker, stores vectors in a named Docker volume mounted at /qdrant/storage,
and listens only on localhost. The new Compose project has its own volume. Container
restart/recreation retains vectors as long as the volume remains. The volume is not a
folder of committed documents. Google Drive will supply documents, not host this database.

## First real document: local preview

```powershell
python scripts/ingest_profile.py --source data/private --version preview-001 --dry-run
```

This reports document/chunk counts without contacting HF or Qdrant. It is not embedding.
The local file master-career-profile.txt was copied from the original project's
Jabulani_Ndlovu-Master _Career_Profile.txt. Its internal heading is
"Jabulani Ndlovu - Master Career & Portfolio Knowledge Base" (punctuation normalized here).
The original file is retained. Its introduction explicitly distinguishes a private master
inventory from public portfolio material, so curate data/public before publication.

## Models and publication

In .env, configure HF_TOKEN, EMBEDDING_URL and LLM_MODEL after confirming a no-charge
hosting option. RERANK_URL is optional. EMBEDDING_MODEL, its revision, prefixes and
VECTOR_DIMENSIONS must describe the model actually serving the endpoint.
The BGE-small default expects 384 dimensions. A populated token does not prove endpoint access.

Once hosting and public-source review are complete:

```powershell
python scripts/ingest_profile.py --source data/public --version release-001 --approved-public
```

Evaluate that candidate, then set CORPUS_VERSION=release-001 and restart the API.
Never reuse an active or partially written version for changed files.

## API and tests

```powershell
uvicorn profile_agent.api:app --host 127.0.0.1 --port 8767
python -m pytest
ruff check src scripts tests app.py
```

Open http://127.0.0.1:8767/docs. GET /health checks liveness only.
POST /ask accepts {"question":"Which projects are documented?"}.
It requires real model configuration and indexed evidence. A 503 currently reflects missing
configuration or an upstream error, not a successful embedding run.

The original API on 8766 and original Qdrant on 6333 belong to the old project.
This repository has no configured GitHub remote or cloud deployment.
