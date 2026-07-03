"""One-shot NIM connectivity smoke test. Run after pasting NVIDIA_NIM_API_KEY into .env.

    .venv\\Scripts\\python.exe scripts\\nim_smoke.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

key = os.environ.get("NVIDIA_NIM_API_KEY", "").strip()
base = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").strip()
model = os.environ.get("EMBED_MODEL", "nvidia/nv-embedqa-e5-v5").strip()

if not key:
    sys.exit("FAIL: NVIDIA_NIM_API_KEY is empty in .env — paste your key and rerun.")

client = OpenAI(api_key=key, base_url=base)
resp = client.embeddings.create(
    model=model,
    input=["test"],
    extra_body={"input_type": "query", "truncate": "END"},
)
dim = len(resp.data[0].embedding)
print(f"OK: model={model} dim={dim} (expected 1024)")
if dim != 1024:
    sys.exit(f"WARN: unexpected embedding dim {dim}")
