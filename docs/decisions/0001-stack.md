# Stack Decision

Qdrant is the default dedicated vector service; Chroma remains an optional adapter.
Milvus is an alternative with Lite, standalone and distributed deployment choices.
pgvector fits applications centered on PostgreSQL and relational queries.
No MongoDB dependency is retained in this clean repository.

The backend uses Python, FastAPI and one LangChain agent.
langchain-openai is used as an open-source client for an OpenAI-compatible HF endpoint;
it does not require an OpenAI account or an OpenAI-hosted model.
The embedding adapter currently implements Hugging Face TEI /embed; the optional reranker
implements TEI /rerank. A free shared-provider route must be checked and adapted as necessary.

Sources:
- https://qdrant.tech/documentation/quickstart/
- https://docs.trychroma.com/deployment
- https://milvus.io/docs/milvus_lite.md
- https://github.com/pgvector/pgvector
- https://huggingface.co/docs/text-embeddings-inference/quick_tour
- https://huggingface.co/docs/inference-providers/pricing

The earlier project and its historic decisions are retained in their original repository.
This repository starts a new history; it does not rewrite that history or publish to GitHub.
