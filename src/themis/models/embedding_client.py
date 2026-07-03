"""NIM embeddings via the OpenAI-compatible /embeddings endpoint.

- input_type='passage' at ingest, 'query' at search time (nv-embedqa-e5-v5 requirement).
- Batched (EMBED_BATCH_SIZE), tenacity retry, disk cache keyed by sha256(text)
  so an unchanged chunk is never re-embedded.
"""
from __future__ import annotations

from typing import Literal

import diskcache
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from themis.config import Settings, get_settings
from themis.schemas import content_hash

InputType = Literal["passage", "query"]


class EmbeddingClient:
    def __init__(self, settings: Settings | None = None, use_cache: bool = True):
        self.s = settings or get_settings()
        self._cache = None
        if use_cache:
            self.s.embed_cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache = diskcache.Cache(str(self.s.embed_cache_dir))

    def _cache_key(self, text: str, input_type: InputType) -> str:
        # Cache is keyed by (model, input_type, text-hash) so query/passage never collide.
        return f"{self.s.embed_model}:{input_type}:{content_hash(text)}"

    @retry(stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=1, min=2, max=30), reraise=True)
    def _embed_batch(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        if not self.s.nvidia_nim_api_key:
            raise RuntimeError("NVIDIA_NIM_API_KEY is not set — cannot embed.")
        resp = httpx.post(
            f"{self.s.nvidia_nim_base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.s.nvidia_nim_api_key}"},
            json={
                "model": self.s.embed_model,
                "input": texts,
                "input_type": input_type,
                "truncate": "END",
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        """Embed texts, serving cache hits first and batching the misses.

        Returns vectors aligned to the input order. Also exposes last-call stats
        via self.last_hits / self.last_misses.
        """
        results: list[list[float] | None] = [None] * len(texts)
        misses: list[int] = []
        for i, t in enumerate(texts):
            if self._cache is not None:
                cached = self._cache.get(self._cache_key(t, input_type))
                if cached is not None:
                    results[i] = cached
                    continue
            misses.append(i)

        self.last_hits = len(texts) - len(misses)
        self.last_misses = len(misses)

        for start in range(0, len(misses), self.s.embed_batch_size):
            batch_idx = misses[start:start + self.s.embed_batch_size]
            vectors = self._embed_batch([texts[i] for i in batch_idx], input_type)
            for i, vec in zip(batch_idx, vectors):
                results[i] = vec
                if self._cache is not None:
                    self._cache.set(self._cache_key(texts[i], input_type), vec)

        return [r for r in results if r is not None]

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text], "query")[0]
