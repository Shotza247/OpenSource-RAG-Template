class ProfileRetriever:
    def __init__(self, embedding_client, vector_store, reranker, settings):
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.reranker = reranker
        self.settings = settings

    def retrieve(self, question):
        vector = self.embedding_client.embed_query(question)
        chunks = self.vector_store.search(vector, self.settings.candidate_k)
        return self.reranker.rerank(question, chunks)
