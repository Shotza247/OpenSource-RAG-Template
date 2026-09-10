import math

import requests


class HFReranker:
    def __init__(self, settings):
        self.s = settings

    def rerank(self, query, chunks):
        if not chunks:
            return []
        if not self.s.rerank_url:
            return chunks[: self.s.context_k]
        response = requests.post(
            self.s.rerank_url,
            headers={"Authorization": f"Bearer {self.s.hf_token}"},
            json={"query": query, "texts": [c.text for c in chunks], "raw_scores": False},
            timeout=self.s.request_timeout,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or len(rows) != len(chunks):
            raise ValueError("Reranker count mismatch")
        seen = set()
        for row in rows:
            index, score = row.get("index"), row.get("score")
            if (
                type(index) is not int
                or index not in range(len(chunks))
                or index in seen
                or type(score) not in (int, float)
                or not math.isfinite(score)
                or not 0 <= score <= 1
            ):
                raise ValueError("Invalid reranker response")
            seen.add(index)
        rows.sort(key=lambda row: row["score"], reverse=True)
        return [chunks[row["index"]] for row in rows if row["score"] >= self.s.rerank_min_score][
            : self.s.context_k
        ]
