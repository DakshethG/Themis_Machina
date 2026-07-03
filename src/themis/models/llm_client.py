"""NIM chat LLM via LiteLLM (provider-portable: NIM->Claude is a config change).

complete() returns text; complete_json() parses a JSON object from the model.
Streaming is exposed via complete_stream() for later phases.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

from themis.config import Settings, get_settings


class LLMClient:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()

    def _model(self, model: str | None) -> str:
        # LiteLLM routes NIM models under the "nvidia_nim/" provider prefix.
        name = model or self.s.llm_model
        return name if "/" not in name or name.startswith("nvidia_nim/") else f"nvidia_nim/{name}"

    def _kwargs(self, **kw: Any) -> dict[str, Any]:
        base = dict(
            api_key=self.s.nvidia_nim_api_key,
            api_base=self.s.nvidia_nim_base_url,
        )
        base.update(kw)
        return base

    @retry(stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=1, min=2, max=30), reraise=True)
    def complete(self, messages: list[dict[str, str]], model: str | None = None,
                 temperature: float = 0.1, max_tokens: int = 1024, **kw: Any) -> str:
        if not self.s.nvidia_nim_api_key:
            raise RuntimeError("NVIDIA_NIM_API_KEY is not set — cannot call LLM.")
        resp = litellm.completion(
            model=self._model(model), messages=messages,
            temperature=temperature, max_tokens=max_tokens,
            **self._kwargs(**kw),
        )
        return resp.choices[0].message.content or ""

    def complete_json(self, messages: list[dict[str, str]], model: str | None = None,
                      **kw: Any) -> dict[str, Any]:
        """Request JSON output and parse it, tolerating code-fence wrapping."""
        kw.setdefault("response_format", {"type": "json_object"})
        raw = self.complete(messages, model=model, **kw)
        return _parse_json(raw)

    def complete_stream(self, messages: list[dict[str, str]], model: str | None = None,
                        temperature: float = 0.1, max_tokens: int = 1024,
                        **kw: Any) -> Iterator[str]:
        resp = litellm.completion(
            model=self._model(model), messages=messages, temperature=temperature,
            max_tokens=max_tokens, stream=True, **self._kwargs(**kw),
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    return json.loads(raw)
