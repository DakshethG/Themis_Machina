"""NIM reranker (nv-rerankqa-mistral-4b-v3).

Input (query, list[passage]) -> ranked (index, score) pairs, best first.
Uses the NVIDIA reranking schema. The endpoint path can differ from the chat base;
override with RERANK_URL if needed.
"""
from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from themis.config import Settings, get_settings


class RerankerClient:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()

    @property
    def _url(self) -> str:
        return self.s.rerank_url or f"{self.s.nvidia_nim_base_url}/ranking"

    @retry(stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=1, min=2, max=30), reraise=True)
    def _rank(self, query: str, passages: list[str]) -> list[tuple[int, float]]:
        if not self.s.nvidia_nim_api_key:
            raise RuntimeError("NVIDIA_NIM_API_KEY is not set — cannot rerank.")
        resp = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self.s.nvidia_nim_api_key}"},
            json={
                "model": self.s.rerank_model,
                "query": {"text": query},
                "passages": [{"text": p} for p in passages],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        rankings = resp.json()["rankings"]  # [{"index": i, "logit": score}, ...]
        return [(r["index"], float(r.get("logit", r.get("score", 0.0)))) for r in rankings]

    def rerank(self, query: str, passages: list[str],
               top_k: int | None = None) -> list[tuple[int, float]]:
        """Return (original_index, score) sorted best-first, truncated to top_k."""
        if not passages:
            return []
        ranked = self._rank(query, passages)
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k] if top_k else ranked
