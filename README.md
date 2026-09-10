# Open-source RAG Template

Start here. This repository is a clean, separate baseline for learning and reusing
the portfolio RAG pipeline. The original project and its Git history are unchanged.
The example Python package remains named profile_agent; replace its profile-specific
prompt when adapting the template to another domain.

## What is where?

| Path | Purpose |
| --- | --- |
| src/profile_agent/ | Backend: configuration, loading, chunking, embeddings, retrieval, agent, API |
| scripts/ | Setup, local ingestion preview, ingestion, retrieval evaluation |
| tests/ | Automated behaviour checks using simulated providers; not proof of real embedding |
| data/private/ | Master career source, local only, excluded from Git and deployment |
| data/public/ | Reviewed corpus approved for public answers, also excluded from Git |
| docs/ | Setup, architecture, roadmap, evaluation and stack decision |
| .env.example | Committed list of settings and safe defaults; contains no credentials |
| .env | Your actual local settings; never committed; loaded by the backend |
| pyproject.toml + uv.lock | Package requirements and reproducible resolved versions |
| docker-compose.yml | Persistent local vector services |
| Dockerfile | Optional container runtime for the API |
| app.py | Vercel-compatible API entry point; cloud deployment is not complete |
| .venv/ | Generated local Python environment, ignored by Git |
| .local/ | Local configuration backups and preview logs, ignored by Git |

## Start in this order

1. Follow [setup](docs/setup.md) to create the environment and inspect configuration.
2. Preview the master document locally. This loads and chunks text without sending it anywhere.
3. Review which material belongs in data/public.
4. Configure a free-access embedding service and chat model; provider availability is still pending.
5. Ingest a new corpus version, evaluate it, then activate it and test POST /ask.

No paid endpoint is part of this template. The current embedding adapter expects the TEI
/embed contract; an HF token alone does not provision that endpoint or make inference unlimited.
Free shared-provider support may require another adapter. Do not enter a paid endpoint just
to get past a configuration check.

## Current state

- Qdrant is the default; Chroma is optional.
- One LangChain agent, hosted-model clients, citations and versioned retrieval are implemented.
- The private master document is available for local preview, not automatically published.
- Actual hosted embedding, answer-quality evaluation and GitHub publication are pending.
- Google Drive sync comes next, then caching and monitoring when needed.

Read [architecture](docs/architecture.md) for how the parts connect,
[roadmap](docs/roadmap.md) for the next milestones, and [BUG_AUDIT.md](BUG_AUDIT.md)
for verification evidence.
