# Themis Machina — Build Progress

## Current phase: 0 — Master one-time setup  |  Status: done (awaiting Phase 1 prompt)

## Environment
- OS: Windows 11 Pro. Shell: PowerShell (primary) + Bash tool.
- Project root: `C:\Users\daksh\OneDrive\Desktop\Themis_Machina`
  - NOTE: master prompt recommended a clean root outside OneDrive (e.g. `C:\dev\Themis_Machina`).
    Currently INSIDE OneDrive. Left as-is per invocation dir; flag to user if sync causes lock issues.
- Python venv: `.venv` (Python 3.13.14). Managed with pip + requirements.txt.
- Key deps installed: pydantic 2.13.4, pydantic-settings 2.14.2, httpx 0.28.1, litellm 1.90.2,
  qdrant-client 1.18.0, pymupdf 1.27.2.3, rank-bm25 0.2.2, python-dotenv 1.2.2, tenacity 9.1.4,
  tqdm 4.68.3, pytest 9.1.1, pytest-asyncio 1.4.0, openai 2.44.0, datasets 5.0.0.
- Accounts configured: NVIDIA NIM [pending key], Qdrant [n], Neo4j [n], Neon [n], Upstash [n]

## Completed phases
- Phase 0 (master setup): env scaffolding + corpus verification + dep install. No app code yet.

## Files created (by module)
- .gitignore, .env.example, requirements.txt, PROGRESS.md, SPEC_DIGEST.md — root scaffolding
- .env — gitignored, awaiting real keys from user

## Corpus verification (raw, read-only)
- corpus/raw/statutes: 48 PDFs (master expected ~49 — within tolerance)
- corpus/raw/cases/sc: 511 PDFs recursive (includes landmark/ = 17 PDFs)
- corpus/raw/cases/hc: 245 PDFs (HC present — larger than master's implied unknown)
- corpus/raw/datasets/cuad: present
- corpus/datasets/scicite: present (also corpus/raw/datasets/scicite listed)
- Documents/MD: 12 design docs present (01–12). NOTE: master referenced up to 13-README-Portfolio.md
  and doc 13 is NOT present. Docs 01-PRD through 12-Project-Roadmap exist.

## Key decisions
- Reused existing .venv rather than recreating (already had ~all deps).
- Did not relocate project out of OneDrive (would require user consent + path rewrites).

## Known issues / TODO
- NVIDIA NIM smoke test: BLOCKED — no API key in .env yet. User must paste keys (see below).
- Missing design doc 13-README-Portfolio.md — confirm whether it exists elsewhere.
- Statute count 48 vs expected ~49 — verify no PDF missing before ingestion (Phase 1).

## Deferred (do not build unless a later phase requires)
- (none yet)

## What I've already read (don't re-read)
- (design docs not yet read — will digest into SPEC_DIGEST.md on first need in Phase 1)
