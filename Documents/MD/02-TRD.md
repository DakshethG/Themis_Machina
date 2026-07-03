# Technical Requirements Document (TRD)

**Project:** Themis Machina
**Assistant:** Themis GPT
**Document:** 2 of 13
**Version:** 1.1
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## Change log

- **v1.1** — Adopted dual-track architecture: **Phase A (Free Tier, ₹0/month)** as the build target during portfolio development; **Phase B (Production-Grade)** as the documented upgrade path. NVIDIA NIM and Apple Silicon Ollama form the LLM substrate during Phase A. Added Section 14 (Free-Tier vs Production Migration Guide).
- **v1.0** — Initial baseline.

---

## 1. Purpose and Scope

This document translates the **PRD (Document 1)** into a concrete technical specification: system architecture, technology stack, component design, data flows, deployment model, and engineering standards under which Themis Machina is built.

The TRD is intentionally opinionated. Where alternatives exist, choices are named and the reasoning given. Where decisions remain open, they are listed in Section 15.

A defining property of this TRD is its **dual-track structure**: every cost-relevant choice is specified twice — once for **Phase A (Free Tier)**, which is what the portfolio version actually runs on, and once for **Phase B (Production)**, which documents the upgrade path. Section 14 is a complete migration guide.

Detailed AI/ML design lives in **Document 3**. Data schemas in **Document 8**. API contracts in **Document 9**. This document covers the system-level engineering.

---

## 2. System Architecture Overview

Themis Machina is a multi-tier, multi-corpus, conversational RAG system. At the highest level it consists of seven concerns:

1. **Clients** — web frontend, future mobile, possible MCP integrations
2. **Edge** — CDN, TLS termination, WAF, rate limiting
3. **API gateway** — FastAPI service exposing all backend functionality
4. **Orchestration** — LangGraph stateful conversation agent
5. **Retrieval and ML services** — embedding, lexical, vector, reranker, NLI, classifiers, LLM gateway
6. **Data plane** — Postgres, Qdrant, Neo4j, Redis, object storage
7. **Cross-cutting concerns** — auth, observability, eval harness, cost governance, security controls

### 2.1 High-level architecture diagram

```
                            ┌───────────────────────────────┐
                            │      Clients                  │
                            │  Web (Next.js) · Mobile (TBD) │
                            └──────────────┬────────────────┘
                                           │ HTTPS / SSE
                            ┌──────────────▼────────────────┐
                            │  Cloudflare (CDN + WAF + TLS) │
                            └──────────────┬────────────────┘
                                           │
                            ┌──────────────▼────────────────┐
                            │  FastAPI Gateway              │
                            │  - Auth (Clerk JWT)           │
                            │  - Rate limiting (Redis)      │
                            │  - Request tracing            │
                            │  - Schema validation          │
                            └──────┬────────────────────┬───┘
                                   │                    │
                       ┌───────────▼─────────┐  ┌───────▼──────────┐
                       │  LangGraph          │  │  Document        │
                       │  Conversation Agent │  │  Ingestion       │
                       │  - State machine    │  │  Service         │
                       │  - Memory           │  │  - Parse / OCR   │
                       │  - Intent routing   │  │  - Chunk / embed │
                       │  - Tool calls       │  │  - Per-user      │
                       └──┬──────────────────┘  │    isolation     │
                          │                     └────────┬─────────┘
                          │                              │
        ┌─────────────────┼──────────────────────────────┼───────────────────────┐
        │                 │                              │                       │
┌───────▼─────┐  ┌────────▼──────┐  ┌────────────────────▼─┐  ┌─────────────────▼┐
│ Retrieval   │  │ Generation    │  │ Classifiers / NLI    │  │ Evaluation       │
│ Service     │  │ via LLM       │  │ - Intent (small LLM) │  │ Harness          │
│ - Hybrid    │  │ Gateway       │  │ - Treatment / stance │  │ - Golden set     │
│   (Qdrant + │  │ (LiteLLM →    │  │ - Clause (CUAD-FT)   │  │ - RAGAS metrics  │
│   BM25)     │  │  NIM /        │  │ - Citation verifier  │  │ - CI integration │
│ - Rerank    │  │  Ollama /     │  │   (LLM-as-judge)     │  │ - Active learn   │
│   (BGE-rrk) │  │  Claude       │  │                      │  │   queue          │
│ - GraphRAG  │  │  in Phase B)  │  │                      │  │                  │
│   (Neo4j)   │  │ - Caching     │  │                      │  │                  │
└──────┬──────┘  └───────┬───────┘  └──────────────────────┘  └──────────────────┘
       │                 │
       │                 │
┌──────▼─────────────────▼────────────────────────────────────────────────────┐
│                            Data Plane                                       │
│                                                                             │
│  Postgres   Qdrant     Neo4j     Redis      R2/S3                           │
│  (Neon)     (Cloud     (Aura     (Upstash)  (Cloudflare)                    │
│   state,     free      Free)      cache,    object store:                   │
│   users,     1 GB      citation   sessions, parsed docs,                    │
│   matters,   dense +   graph)     rate      uploaded docs                   │
│   audit,     BM25)                limits)                                   │
│   sessions                                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

  Cross-cutting (every service):
  - OpenTelemetry traces → Grafana Cloud (free tier)
  - Structured logs (JSON) → Grafana Loki (free tier)
  - LLM call traces → Langfuse Cloud (free tier)
  - Metrics → Grafana Cloud (free tier)
  - Secrets → Cloud KMS / 1Password / dotenv-vault (Phase A); Vault (Phase B)
  - CI/CD → GitHub Actions (public repo, unlimited free)
  - Errors → Sentry (free tier)
```

### 2.2 Architectural principles

1. **Citation-first.** Every fact must trace to a retrieved source. No path allows a generated claim without a verified citation.
2. **Tier-aware sources.** Different sources carry different authority. The system tracks the tier and enforces tier rules at generation.
3. **Stateless services, persistent state.** Every backend service is stateless; state lives in Postgres, Qdrant, Neo4j, or Redis. Horizontal scaling.
4. **Provider portability.** No code depends on a single LLM, embedding, or reranker provider. LiteLLM mediates LLM calls; embedding and reranker calls are interface-abstracted. **This is what allows the Phase A → Phase B swap with minimal code change.**
5. **Observability as a first-class concern.** Every meaningful event produces a trace, a log, and a metric.
6. **Eval-driven change control.** Any change to retrieval, prompts, models, or orchestration triggers the eval harness and is blocked on regression.

---

## 3. Technology Stack — Dual Track

### 3.1 Languages and primary runtimes (identical across phases)

| Layer | Language | Runtime |
|---|---|---|
| Backend services | Python 3.12 | FastAPI on Uvicorn |
| Ingestion workers | Python 3.12 | Celery on Redis broker |
| Frontend | TypeScript 5 | Next.js 14 (App Router) |
| Infrastructure | HCL / YAML | Terraform + Docker Compose (dev) |
| Local LLM runtime | — | Ollama on macOS (M1) with Metal/MLX acceleration |

### 3.2 Component matrix — Phase A vs Phase B

| Concern | Phase A — Free Tier | Phase B — Production |
|---|---|---|
| **Primary LLM (generation)** | NVIDIA NIM hosting Llama 3.3 70B / Llama 4 Maverick / DeepSeek V3 | Anthropic Claude Sonnet 4 |
| **Fast LLM (router, intent, verify)** | NVIDIA NIM hosting Llama 3.1 8B / Nemotron-mini | Claude Haiku 4.5 |
| **Local LLM fallback** | Ollama on M1: Qwen 2.5 14B / Llama 3.2 3B / Phi-4 | Same (used during outages) |
| **LLM gateway** | LiteLLM with NIM + Ollama providers | LiteLLM with Anthropic + OpenAI + NIM |
| **Embeddings** | NVIDIA NIM (NV-EmbedQA-E5-v5) **or** local BGE-M3 via FastEmbed | Voyage-3-large or Voyage-law-2 |
| **Reranker** | NVIDIA NIM (NV-RerankQA-Mistral4B-v3) **or** local BGE-reranker-v2-m3 | Cohere Rerank 3 |
| **Vector DB** | Qdrant Cloud free 1 GB **or** self-hosted Qdrant on Oracle Free | Qdrant Cloud paid or self-hosted Qdrant cluster |
| **Lexical (BM25)** | Qdrant native BM25 (single engine) | Same, or dedicated Elasticsearch at scale |
| **Graph DB** | Neo4j Aura Free (200K nodes, 400K relationships) | Neo4j Aura Professional or self-hosted Enterprise |
| **Relational DB** | Neon free tier (0.5 GB Postgres, scales to zero) | Neon Pro / Supabase Pro / RDS / Cloud SQL |
| **Cache & broker** | Upstash Redis free (256 MB, 10K cmd/day) | Upstash paid / self-hosted Redis |
| **Object storage** | Cloudflare R2 free (10 GB, 1M Class A ops/month) | R2 paid (pay-per-use) |
| **Auth** | Clerk free (10K MAU) | Clerk paid or WorkOS |
| **Web search (Tier 3/4)** | Tavily free (1K searches/month) + direct scraping for Tier 2 | Tavily paid + Exa + direct scraping |
| **Document parsing** | Unstructured.io OSS + PyMuPDF + LlamaParse free (1K pages/day) | LlamaParse paid + Reducto + Azure Document Intelligence |
| **OCR** | Tesseract local | AWS Textract or Azure Document Intelligence |
| **Frontend hosting** | Vercel free | Vercel Pro |
| **Backend hosting** | Google Cloud Run free + Oracle Cloud Free Forever ARM VM (4 cores, 24 GB RAM) | Kubernetes (GKE/EKS/AKS) or managed equivalents |
| **CI/CD** | GitHub Actions (public repo, unlimited) | Same |
| **LLM observability** | Langfuse Cloud free (50K observations/month) | Langfuse paid or self-hosted enterprise |
| **General observability** | Grafana Cloud free + Sentry free | Grafana Cloud Pro or DataDog |
| **Eval framework** | RAGAS + DeepEval + custom (all OSS) | Same |
| **Secrets** | dotenv-vault or 1Password CLI for local; Vercel/Cloud Run env vars in prod | HashiCorp Vault or AWS Secrets Manager / GCP Secret Manager |

### 3.3 Why these Phase A choices

**NVIDIA NIM as primary LLM provider.** NIM provides hosted, OpenAI-compatible endpoints for frontier-class open-weight models (Llama 3.3 70B, Llama 4, DeepSeek V3, Nemotron, Mixtral) at zero cost on its free developer tier. Quality is within 5–10% of Claude Sonnet on RAG tasks; the gap is closed by stricter verification (see Document 3). The OpenAI-compatible API means LiteLLM routing works unchanged when we switch providers in Phase B.

**Ollama on M1 as local fallback.** The M1 Mac runs Qwen 2.5 14B and similar models at acceptable speed via Metal acceleration. It serves three purposes: (1) dev iteration without API calls, (2) fallback when NIM is rate-limited or down, (3) running the eval harness at high concurrency overnight without burning provider quotas.

**Local BGE embeddings and reranker.** FastEmbed and sentence-transformers run BGE-M3 (embedding) and BGE-reranker-v2-m3 (reranker) on the M1 with acceptable throughput. This eliminates any cloud dependency for the highest-volume inference paths during ingest. Quality is ~90–95% of Voyage and Cohere paid offerings on legal text.

**Qdrant native BM25 (single engine).** Qdrant 1.10+ supports BM25 as a sparse index alongside dense vectors in one engine. This eliminates the need for a separate Elasticsearch deployment. At Phase A scale (under 1 GB of vectors), Qdrant Cloud's free tier comfortably holds the v1.0 corpus.

**LangGraph over LangChain alone.** Stateful, branching, durable checkpoints — necessary for multi-turn conversation with conditional retrieval paths. LangChain's basic chains lack the state model.

**LiteLLM as the LLM gateway.** This is what makes the Phase A → Phase B transition mechanical rather than architectural. LiteLLM presents a single interface; the underlying provider can be swapped in configuration. The system is built on this abstraction from day one.

**Neon Postgres free tier.** Scale-to-zero is the killer feature — when not in use, you pay nothing and consume nothing. Cold-start latency is acceptable for portfolio traffic.

**Vercel + Cloud Run + Oracle Free.** The deployment split:
- Vercel hosts the Next.js frontend (free, generous)
- Cloud Run hosts the stateless FastAPI backend (free tier: 2M requests/month, scales to zero)
- Oracle Cloud Free Forever ARM VM (4 cores, 24 GB RAM, free forever) hosts always-on services: self-hosted Qdrant if the cloud tier runs out, Ollama for fallback, scheduled scrapers and workers.

This split is intentional: each service runs where it costs nothing.

### 3.4 Where Phase B differs

The Phase B stack is documented in detail in **Section 14**. Briefly: paid Claude for higher generation quality and citation grounding; paid Voyage embeddings (domain-specialized for legal); Cohere Rerank for best-in-class reranking; paid managed databases for SLA-backed reliability; Kubernetes-class hosting for elasticity. Estimated mid-scale cost: $1,000–$3,500/month.

---

## 4. Service Architecture

### 4.1 Services

| Service | Responsibility | Stateful | Scaling (Phase A) | Scaling (Phase B) |
|---|---|---|---|---|
| **API Gateway** (FastAPI) | All external HTTP/SSE. Auth, rate limiting, routing. | No | Cloud Run scale-to-zero | Horizontal via load balancer |
| **Conversation Service** | LangGraph orchestrator. | Per-request | Co-deployed with API Gateway on Cloud Run | Separate deployment in Phase B |
| **Retrieval Service** | Hybrid retrieval, reranking, graph traversal. | No | Co-deployed with conversation | Separate deployment |
| **Ingestion Service** | Document parsing, OCR, chunking, embedding, indexing. | No | Celery on Oracle Free VM | Worker pool (KEDA-scaled) |
| **Eval Service** | Runs golden eval set, computes metrics. | No | Single worker, scheduled via GitHub Actions | Dedicated worker |
| **Background Workers** | Official-source scrapers, scheduled re-indexing. | No | Cron on Oracle Free VM | KEDA-scaled |

In Phase A, services are co-deployed as one FastAPI app to minimize hosting footprint and maximize cache locality. In Phase B, they can be split based on operational concerns (different scaling profiles, different deploy cadences).

### 4.2 Inter-service communication

- **Synchronous (within request):** REST/JSON via FastAPI dependency injection (co-deployed) or HTTP (separated)
- **Asynchronous (background):** Redis-backed Celery
- **Streaming (to client):** Server-Sent Events (SSE) from FastAPI

### 4.3 Conversation Service in detail

The Conversation Service owns the LangGraph state machine and is the only mutator of conversation state. It:

- Loads conversation state from the Postgres checkpointer keyed by `conversation_id`
- Runs the LangGraph state machine for the new user turn
- Streams the partial response to the client via SSE
- Persists new state at turn boundaries
- Emits Langfuse traces and OTel spans throughout

State schema (full definition in Document 3): messages, mode (Professional / Public / Patent), research-matter ID, retrieved sources for the current turn, sources accumulated this session, intent classification, jurisdiction filters, time-window filters, conversation summary, per-user metadata.

### 4.4 Retrieval Service in detail

Stateless library invoked by the conversation service. Public interface:

```python
async def retrieve(
    query: str,
    corpora: list[Corpus],        # statute, case_law, patent, user_doc, web_tier_2, web_tier_3
    filters: RetrievalFilters,    # jurisdiction, date_range, court, section, CPC, etc.
    strategy: RetrievalStrategy,  # naive, hybrid, hybrid+rerank, hyde, graph_expand, adaptive
    top_k: int,
    user_id: str | None,          # required for user_doc corpus
    tier_policy: TierPolicy,      # which tiers are allowed for this query
) -> list[RetrievedChunk]
```

Implementations:

- **Hybrid retrieval:** parallel Qdrant dense + Qdrant BM25, fused with Reciprocal Rank Fusion (RRF, k=60)
- **Reranker:** local BGE-reranker-v2-m3 in Phase A; Cohere Rerank 3 in Phase B
- **HyDE:** small LLM generates a hypothetical answer, embeds it, retrieves against the embedding
- **Graph expansion:** Cypher traversal in Neo4j to expand a seed set
- **Adaptive:** if reranker top score is below threshold, regenerate query and retry once

### 4.5 Ingestion Service in detail

Two distinct paths:

**Bulk ingestion** (corpus loading): source-specific crawler → parser → chunker → batch embedder → indexer (Qdrant + Neo4j). Idempotent by stable chunk ID derived from content hash.

**User document ingestion** (real-time): upload → R2 with user-scoped key → Celery task → parse (Unstructured / LlamaParse / OCR) → chunk → embed → index into **per-user Qdrant collection** named `user_{user_id}_session_{session_id}` → notify client.

The per-user collection model guarantees isolation at the storage layer. Cross-collection retrieval is forbidden at the application layer and verified by integration tests.

---

## 5. Data Architecture

Full schemas in **Document 8**. System-level shape:

### 5.1 Data store assignment

| Store | Data | Phase A capacity | Phase B capacity |
|---|---|---|---|
| **Postgres (Neon)** | Users, sessions, matters, conversations, audit log, eval data, prompt versions | 0.5 GB | Unlimited (paid tier) |
| **Qdrant (Cloud free)** | Dense vectors + BM25 + metadata for all corpora; per-user collections for uploaded docs | 1 GB | Unlimited (paid) |
| **Neo4j (Aura Free)** | Citation graphs (case treatment, patent citations); judges, courts, claim nodes | 200K nodes / 400K rels | Unlimited (paid) |
| **Redis (Upstash free)** | Session cache, rate limits, Celery broker, prompt cache | 256 MB / 10K cmd/day | Unlimited |
| **R2 (Cloudflare)** | Original docs, parsed JSON, evidence snapshots, user uploads (encrypted) | 10 GB | Unlimited (paid) |

### 5.2 Data flow — corpus ingestion (run once and on updates)

```
Source (India Code / SC e-SCR / USPTO / etc.)
         │ scrape / download
         ▼
Raw file → R2
         │
         ▼
Parser (Unstructured / PyMuPDF / custom) → Parsed JSON in R2
         │
         ▼
Chunker (legal-aware: per section / per case-component / per claim)
         │
         ▼
Per chunk:
  - Embed (local BGE-M3 batched, or NIM embedding API)
  - Write to Qdrant (dense + BM25 + metadata)
  - If case or patent: write nodes + edges to Neo4j
  - Write provenance row to Postgres
```

### 5.3 Data flow — user query

```
User query
   │
   ▼
API Gateway (auth, rate limit, audit log entry)
   │
   ▼
Conversation Service: load state from Postgres checkpointer
   │
   ▼
LangGraph turn:
   ├─ Guard / scope check (small LLM via NIM)
   ├─ Query rewrite (small LLM, conversation context)
   ├─ Intent classification
   ├─ Retrieval router → Retrieval Service
   │       ├─ Hybrid (Qdrant dense + Qdrant BM25)
   │       ├─ Rerank (local BGE-reranker on M1, or NIM rerank)
   │       ├─ Graph expand (Neo4j) — if treatment / prior-art query
   │       └─ Web tier (Tavily) — if recency / commentary needed
   ├─ Generation (Llama 3.3 70B via NIM) with structured output
   ├─ Citation verifier (small LLM, LLM-as-judge)
   └─ Memory update
   │
   ▼
Stream response via SSE
   │
   ▼
Persist state to Postgres
   │
   ▼
Emit Langfuse trace + OTel spans + cost metric
```

### 5.4 Data flow — user document upload

```
User uploads file
   │
   ▼
API Gateway: MIME validation, size check, optional virus scan
   │
   ▼
Write to R2 with user-scoped key: r2://docs/user_{id}/session_{id}/doc_{uuid}
   │
   ▼
Enqueue Celery task on Upstash Redis
   │
   ▼
Worker (Oracle Free VM):
   ├─ Parse (Unstructured → fall back to LlamaParse → fall back to OCR)
   ├─ Detect document type (contract / notice / judgment / other)
   ├─ Chunk (type-specific)
   ├─ Embed (local BGE-M3 or NIM)
   ├─ Index into user-scoped Qdrant collection
   ├─ Run CUAD clause classifier (if contract) → store labels
   └─ Mark ready in Postgres
   │
   ▼
Notify client via SSE: "document ready"
```

---

## 6. Security Architecture

Full detail in **Document 10**. Headline architecture (identical across phases):

### 6.1 Authentication

OAuth 2.1 with PKCE for browsers; JWT bearer tokens (Clerk-signed, verified at API Gateway via JWKS endpoint); anonymous sessions get short-lived signed tokens with limited scope; refresh tokens with rotation; logout invalidates server-side session record.

### 6.2 Authorization

Role-based: `anonymous`, `public_user`, `professional_user`, `admin`. Resource-scoped: every query carries `user_id` as a mandatory filter on user-scoped data. Defense in depth: Postgres row-level security as a backstop.

### 6.3 Per-user isolation

The highest-risk class of bug is cross-user data leakage. Mitigations:

- Each user's uploaded documents live in a dedicated Qdrant collection
- The retrieval service requires `user_id` as a typed parameter; cannot be defaulted
- Postgres RLS policies on user-scoped tables
- Audit log of every cross-collection access (none should exist normally)
- Integration tests explicitly try to query user A's docs as user B and assert empty results

### 6.4 Encryption

TLS 1.3 for all external connections; TLS for internal where supported by free-tier providers (mTLS deferred to Phase B); AES-256 at rest (provider-managed); application-level encryption of uploaded document contents with per-user key.

### 6.5 Secrets management

**Phase A:** dotenv-vault or 1Password CLI for local dev; Vercel and Cloud Run environment variables for deployed secrets; never in git.
**Phase B:** HashiCorp Vault or cloud-native secret manager; automatic rotation.

### 6.6 Adversarial input handling

All retrieved web content treated as data, never as instructions; sanitization pass strips known prompt-injection patterns; outputs containing tool-call patterns from web content are rejected; prompt-injection eval set (Document 6) runs on every PR.

---

## 7. Observability Architecture

### 7.1 Tracing

OpenTelemetry SDK in every service. Every request gets a trace ID; every LangGraph node, retrieval call, and LLM call is a span. Spans carry: tenant ID (hashed), conversation ID, retrieval strategy, retrieved chunk count, LLM model + version, tokens in/out, cost (zero in Phase A), status. Traces shipped to **Grafana Cloud free tier** (Phase A) or **Tempo/Honeycomb** (Phase B).

### 7.2 Structured logging

JSON logs with common fields: timestamp, level, service, trace_id, span_id, conversation_id, event, payload. No raw user content; PII tokenized. Logs shipped to **Grafana Loki free tier** (both phases; Phase B uses paid tier).

### 7.3 LLM-specific observability via Langfuse

Every LLM call traced with: prompt template version, rendered prompt, model, parameters, response, tokens, cost, latency. Conversations viewable end-to-end. Eval scores attached. A/B comparisons of prompt versions.

**Phase A:** Langfuse Cloud free (50K obs/month — comfortable for portfolio traffic).
**Phase B:** Langfuse paid or self-hosted enterprise.

### 7.4 Metrics

Prometheus-format metrics scraped by Grafana Cloud. Service-level (request rate, latency p50/p95/p99, error rate). AI-specific (per-stage latency, token usage, retrieval recall on golden set, faithfulness). Business (DAU, sessions/user, turns/session, mode mix).

### 7.5 Alerting

- p95 latency > 20s for 5 minutes (Phase A) / > 15s (Phase B) → page
- Error rate > 2% for 5 minutes → page
- Cost rises > 30% above 7-day average → notify (relevant only in Phase B; Phase A cost is zero)
- Faithfulness score drops > 5pp in nightly eval → block deploy, notify
- LLM provider 5xx rate > 10% for 5 minutes → notify (Phase A: trigger Ollama fallback)

---

## 8. Deployment Architecture

Full detail in **Document 11**. Headline:

### 8.1 Environments

| Environment | Purpose | Data |
|---|---|---|
| Local dev | Docker Compose on developer machine | Synthetic / small sample |
| CI | GitHub Actions runners | Small test fixtures + eval golden set |
| Staging | Cloud, mirrors prod | Anonymized sample of prod corpus |
| Production | Cloud, public | Full corpus |

In Phase A, staging and production may share a Cloud Run service with branch-based deploys (preview deployments) to keep infrastructure simple. In Phase B, they are fully separate.

### 8.2 Production deployment shape — Phase A

```
                          User
                            │
                            ▼
                     Cloudflare (CDN, TLS, DDoS)
                            │
                ┌───────────┴────────────┐
                │                        │
                ▼                        ▼
        Vercel (Next.js)         Cloud Run (FastAPI)
         frontend                  scale-to-zero
                                       │
                ┌──────────────────────┼─────────────────────┐
                │                      │                     │
                ▼                      ▼                     ▼
        Qdrant Cloud         Oracle Free VM           Neon Postgres
        (1 GB free)          (always-on:              (0.5 GB,
                              Ollama,                  scale-to-zero)
                              workers,
                              self-host fallback)

         Cloudflare R2         Neo4j Aura Free        Upstash Redis
         (10 GB free)          (200K nodes)           (256 MB free)

         External:
         - NVIDIA NIM (free tier)
         - Tavily (1K/month free)
         - Clerk (10K MAU free)
         - Langfuse Cloud (50K obs/month free)
         - Grafana Cloud (free tier)
         - Sentry (free tier)
```

### 8.3 Production deployment shape — Phase B

- Kubernetes (GKE / EKS / managed alternatives) for API and worker pods
- Managed Postgres (Neon Pro / RDS / Cloud SQL)
- Qdrant Cloud paid cluster (multi-region if needed) or self-hosted on dedicated nodes
- Neo4j Aura Pro or self-hosted Enterprise
- Cloudflare in front of everything
- Redis: Upstash paid or self-hosted with replication

### 8.4 CI / CD

GitHub Actions workflow:

- **On PR:** lint, type-check, unit tests, integration tests, run eval on 30-question fast set
- **On merge to main:** full eval (200 questions), build image, push to registry, auto-deploy to staging
- **On tag:** deploy to production with manual approval

Eval regression > 2pp on faithfulness, citation accuracy, or refusal precision blocks merge.

### 8.5 Configuration management

Twelve-factor: all config via environment variables loaded into typed Pydantic Settings classes. Helm charts (Phase B) or compose files (Phase A) for orchestration. Feature flags via a simple Postgres table.

---

## 9. Performance and Cost Budgets

### 9.1 Latency budget per turn — Phase A (p95)

Total budget: **20 seconds end-to-end**. First-token by 6 seconds.

```
For a typical statute lookup in Phase A:
  ├─ Guard + intent classify (NIM Llama 3.1 8B):    600 ms  (200ms RTT + 400ms inference)
  ├─ Query rewrite (NIM Llama 3.1 8B):              700 ms
  ├─ Hybrid retrieval (Qdrant + BM25, parallel):    500 ms
  ├─ Rerank (local BGE-reranker on M1 / NIM):       800 ms
  ├─ Generate (NIM Llama 3.3 70B, streamed):       5000 ms  (~1500 output tokens)
  ├─ Citation verifier (overlapped w/ generation):  -      (visible delay 500ms)
  └─ State persist + audit:                         300 ms
                                                  -------
                                                  ~8.0 s   to full response with verifier overlap
                                                  ~3.5 s   to first token
```

These numbers assume NIM endpoints are warm and not rate-limited. When NIM is rate-limited, the system falls back to Ollama (local M1, much faster for round trip but slower for the model itself — typical 70B generation at 8-15 tokens/sec on M1) or smaller NIM models.

### 9.2 Latency budget per turn — Phase B (p95)

```
For a typical statute lookup in Phase B:
  ├─ Guard + intent classify (Claude Haiku):        200 ms
  ├─ Query rewrite (Claude Haiku):                  300 ms
  ├─ Hybrid retrieval:                              400 ms
  ├─ Rerank (Cohere):                               500 ms
  ├─ Generate (Claude Sonnet, streamed):           3500 ms
  ├─ Citation verifier (Claude Haiku, overlapped):  -
  └─ State persist:                                 200 ms
                                                  -------
                                                  ~5.1 s   to full response
                                                  ~2.0 s   to first token
```

### 9.3 Throughput targets

| Metric | Phase A | Phase B |
|---|---|---|
| Concurrent active sessions | 10 (NIM rate limit) | 50+ |
| Queries/hour sustained | 100 | 500+ |
| Burst capacity | 2× for 5 min | 2× for 5 min |

### 9.4 Storage and compute estimates

| Corpus | Approx size | Phase A storage strategy |
|---|---|---|
| Statutes (50 priority acts + Constitution) | ~50 MB raw, ~200K chunks, ~600 MB vectors with quantization | Qdrant Cloud free tier (well under 1 GB) |
| SC judgments (subset for v1.0: leading constitutional + commercial cases, ~5K) | ~4 GB raw, ~1M chunks, ~300 MB vectors with int8 quantization | Qdrant Cloud free tier (with quantization) |
| Add'l SC judgments (deferred to Phase B if free tier insufficient) | ~20 GB raw | Self-host Qdrant on Oracle Free VM |
| High Courts (deferred to Phase B if needed) | ~80 GB raw | Self-host on Oracle Free VM, or wait for Phase B |
| USPTO patents (subset for Phase 7) | Start with 1 CPC subclass: ~100K patents, ~5 GB | Self-host Qdrant collection or extend Cloud tier |

**Note on quantization:** Qdrant supports int8 scalar quantization which cuts vector storage by 4x with negligible quality loss. This is the key technique that makes the free 1 GB Qdrant tier viable for v1.0.

### 9.5 Cost ceilings — Phase A

**Per-query cost: ₹0.**
**Monthly cost: ₹0** (or ₹125/month amortized if a custom domain is purchased).

All Phase A LLM calls are on the NIM free tier or local Ollama; all infrastructure is on free tiers. The only true cost is electricity for the M1 (negligible) and time.

### 9.6 Cost ceilings — Phase B

| Component | Approx cost per 1K queries | Notes |
|---|---|---|
| Embedding (query) | $0.001 | Voyage |
| Retrieval infra | amortized | Qdrant Cloud paid |
| Rerank | $2.00 | Cohere |
| Generation (Claude Sonnet, ~1.5K out) | $12.00 | Bulk of cost |
| Verification (Claude Haiku) | $0.50 | |
| **Total per 1K queries** | **~$14.50 (~₹1,200)** | |
| **Per query** | **~₹1.20** | |

At 100 daily queries, Phase B monthly LLM cost is ~₹3,600. Add infra (~$300/month at mid-scale) and the all-in monthly cost lands in the $1,000–$3,500 range described in the PRD.

---

## 10. Engineering Standards

Identical across phases.

### 10.1 Code

Python: Black, Ruff, mypy strict. TypeScript: Prettier, ESLint, tsc strict. All public functions typed; all public APIs documented. No production code without tests.

### 10.2 Testing

| Test type | Coverage target | Tools |
|---|---|---|
| Unit | > 70% line coverage on core libs | pytest |
| Integration | All API endpoints, all retrieval strategies | pytest + httpx |
| End-to-end | All hero use cases | Playwright |
| Eval | 200-question golden set | RAGAS + custom |
| Prompt injection | 50-attack red-team set | Custom |
| Adversarial refusal | 50-question advice-seeking set | Custom |

### 10.3 Documentation

README per repo (Document 13); per-module READMEs; ADRs for non-trivial decisions; OpenAPI spec for all public APIs (Document 9).

### 10.4 Source control

Git, GitHub, public repo (gives free unlimited Actions). Trunk-based development. PRs require CI pass, eval-harness pass, one self-review with AI pair programmer.

### 10.5 Dependency management

Python: uv with pyproject.toml lockfile. TypeScript: pnpm with strict lockfile. Renovate or Dependabot. No new dependency without documented reason.

---

## 11. Cross-Cutting Engineering Concerns

### 11.1 Configuration

All config via environment variables, loaded into typed Pydantic Settings classes. Secrets never in committed env files.

### 11.2 Error handling

All exceptions caught at LangGraph node boundaries. Structured error surfaced with user-facing language. Unhandled exceptions alerted. Retries with exponential backoff on transient provider errors (max 3).

**Phase A-specific:** NIM rate-limit errors trigger automatic Ollama fallback for the next call.

### 11.3 Rate limiting

| Limit | Anonymous | Authenticated public | Authenticated professional |
|---|---|---|---|
| Queries/hour | 30 | 200 | 500 |
| Document uploads/hour | 0 | 5 | 25 |
| Max document size | — | 10 MB | 25 MB |
| Max turns/conversation | 50 | 100 | 200 |

Enforced in Redis with sliding-window counters.

### 11.4 Caching

- **Embedding cache** (Redis or Postgres-cache fallback): content-hash keyed, infinite TTL
- **Retrieval cache** (Redis): query+filter+corpora hashed, 15-min TTL
- **Prompt cache at provider** (Phase B with Anthropic): cuts cost on static prompt parts
- **No final-answer cache** in v1.0 (too risky for conversation-dependent legal content)

### 11.5 Internationalization

i18n via next-intl. ISO 8601 timestamps internally; DD MMM YYYY display. Locale defaults to en-IN.

### 11.6 Time handling

UTC in storage. Effective-from / effective-to on statute versions and case-treatment edges. Time-windowed queries via metadata filters.

---

## 12. Engineering Phase Mapping

| Capability | Build phase | Notes |
|---|---|---|
| Repo, CI, lint, type-check, OpenTelemetry skeleton | 0 | Foundation |
| Postgres + Qdrant + ingestion for statutes | 1 | Closed-corpus statute Q&A |
| BM25 + hybrid + reranker | 1 | |
| Generation with structured output + citation verifier | 1 | |
| Case law corpus + structure-aware chunking | 2 | Case law expansion |
| Neo4j citation graph for SC judgments | 2 | |
| Treatment-aware retrieval | 2 | |
| LangGraph orchestration + conversational state | 3 | Conversational layer |
| Coreference resolution, intent classification | 3 | |
| Mode selection (Professional / Public) | 3 | |
| Streamlit prototype UI | 3 | |
| Golden eval set + RAGAS + CI integration | 4 | Evaluation harness |
| Active learning queue | 4 | |
| Tier-aware Tavily + direct scrapers | 5 | Web augmentation |
| Source archival | 5 | |
| Document upload, parse, OCR, per-user isolation | 6 | Themis Documents |
| CUAD clause classifier fine-tuning | 6 | |
| USPTO + EPO + IPO ingestion | 7 | Themis Patents |
| Claim-aware chunking, CPC filtering | 7 | |
| Patent citation graph (PatentsView) | 7 | |
| Claim-element decomposition + NLI element coverage | 7 | |
| Next.js frontend with citation viewer | 8 | Production frontend |
| Matter persistence, exports | 8 | |
| Langfuse end-to-end, prompt versioning | 9 | Observability and safety |
| Prompt-injection red-team battery | 9 | |
| Containers, Cloud Run deploy, TLS, monitoring | 10 | Deployment and launch |
| README, demo video, design-doc cleanup | 11 | Polish and packaging |
| Phase B migration | Documented only | Section 14 |

---

## 13. Cost Optimizations Implemented in Phase A

### 13.1 Cost drivers eliminated by Phase A choices

| Driver | How Phase A handles it |
|---|---|
| LLM generation | NIM free tier — zero cost per call |
| Embeddings at ingest | Local BGE-M3 on M1 — zero marginal cost; runs overnight |
| Reranker | Local BGE-reranker on M1 OR NIM free reranker — zero marginal cost |
| Vector DB | Qdrant Cloud free 1 GB with int8 quantization |
| Postgres | Neon free tier scale-to-zero |
| Hosting | Cloud Run scale-to-zero + Vercel free + Oracle Free always-on |

### 13.2 Phase A operational discipline

- Aggressive embedding deduplication (don't re-embed identical content)
- Retrieval cache (15-min TTL) on Upstash Redis
- Eval runs batched (200 questions / week) rather than continuous
- NIM concurrency capped to stay within rate limits
- Quantized vectors in Qdrant (int8) to fit free-tier storage
- Ollama-on-M1 used for dev iteration to preserve NIM quota for the deployed demo

### 13.3 Optimizations explicitly deferred to Phase B

These are documented in Section 14 as part of the upgrade path:

- Provider prompt caching (Anthropic) for cost reduction
- Distilled SLM verifier and router (replace NIM small models with fine-tuned distillations)
- Multi-region deployment for latency
- Dedicated embedding service with batched async API

---

## 14. Free-Tier vs Production Migration Guide

This section is the most-read part of the TRD for interview defense. It documents exactly what would change to move Themis Machina from Phase A (portfolio demo) to Phase B (real production), why each change matters, what it costs, and the order in which the changes would happen.

### 14.1 Migration philosophy

Three principles drive the migration plan:

1. **Migrate one component at a time, with eval between each.** The eval harness exists precisely so that swap-in changes can be measured. No two changes ship together.
2. **The architecture does not change; only the implementations do.** Because of the provider-portability principle (Section 2.2.4) and the use of LiteLLM + interface abstractions, every Phase B swap is a configuration change or a small implementation change, not a refactor.
3. **Prove value before paying for it.** Each Phase B swap should produce a measured improvement on the golden eval set before being kept. If swapping in Cohere Rerank doesn't improve recall@10 by at least 3pp, it's not worth $50/month.

### 14.2 Migration ordering

The recommended migration order from Phase A to Phase B, with eval-measurable impact:

| Step | Swap | Why first | Expected impact |
|---|---|---|---|
| 1 | NIM Llama 3.3 70B → Claude Sonnet 4 | Largest single quality lever | +4–7pp faithfulness, +3–5pp citation accuracy |
| 2 | NIM Llama 3.1 8B → Claude Haiku 4.5 | Cleaner verifier reduces hallucinated citations | +1–2pp citation accuracy |
| 3 | Local BGE-reranker → Cohere Rerank 3 | Direct recall@10 improvement | +3–5pp recall@10 |
| 4 | Local BGE-M3 → Voyage-law-2 | Domain-specialized embeddings | +2–4pp recall@10 on legal queries |
| 5 | Qdrant Cloud free → paid | Storage capacity, no rate limits | Enables full High Court corpus |
| 6 | Neo4j Aura Free → Pro | Citation graph scale | Enables full patent citation network |
| 7 | Neon free → Pro | Conversation persistence at scale | Enables more concurrent users |
| 8 | Cloud Run free → managed Kubernetes | Multi-region, no cold start | Enables low-latency outside US-Mumbai region |
| 9 | Tavily free → paid + Exa | More searches, deeper search | Enables higher web-search volume |
| 10 | LlamaParse free → paid + Reducto | Better table extraction | Enables harder PDFs (annual reports) |

Each step is evaluated against the golden set before the next is undertaken.

### 14.3 Detailed component swaps

#### LLM (generation)

- **Phase A:** NVIDIA NIM hosting Llama 3.3 70B Instruct
- **Phase B:** Anthropic Claude Sonnet 4 via direct API
- **Code change:** A single line in LiteLLM config: `model: "nvidia/meta/llama-3.3-70b-instruct"` → `model: "anthropic/claude-sonnet-4"`.
- **Why:** Claude is consistently superior at legal-domain RAG with structured output, lower hallucination, and reliable citation discipline. NIM Llama 3.3 70B is ~85–93% as good on the relevant benchmarks; Claude pushes the citation accuracy from ~92% to ~96%.
- **Cost impact:** From $0 to roughly $0.012 per query (1500 output tokens at $15/M out).

#### LLM (fast model)

- **Phase A:** NIM Llama 3.1 8B Instruct for intent classification, query rewrite, citation verification
- **Phase B:** Claude Haiku 4.5
- **Code change:** LiteLLM config.
- **Why:** Haiku is faster, more reliable on structured output, better at refusing off-scope queries. Particularly noticeable on the verifier where false positives leak through Llama 3.1 8B more often.
- **Cost impact:** ~$0.0005 per query for verifier calls.

#### Embeddings

- **Phase A:** BGE-M3 local via FastEmbed (or NIM's NV-EmbedQA-E5)
- **Phase B:** Voyage-law-2 or Voyage-3-large
- **Code change:** Implementation of `EmbeddingClient` interface swapped via factory.
- **Why:** Voyage-law-2 is specifically trained on legal text and outperforms BGE-M3 by ~5–8% on legal-domain retrieval. Voyage-3-large is a strong general embedding if law-specialized is unavailable.
- **Cost impact:** $0.12/M tokens for embeddings. At ~200 tokens per chunk and ~5M chunks total, full re-embedding costs ~$120 one-time, then ~$0.001/query.

#### Reranker

- **Phase A:** BGE-reranker-v2-m3 local on M1
- **Phase B:** Cohere Rerank 3
- **Code change:** `RerankerClient` interface implementation.
- **Why:** Cohere Rerank 3 is the best general reranker available via API. Quality improvement is largest on ambiguous queries where the top BM25/dense hit isn't the best.
- **Cost impact:** $2 per 1K rerank calls.

#### Vector DB

- **Phase A:** Qdrant Cloud free 1 GB
- **Phase B:** Qdrant Cloud paid (or self-hosted cluster on Kubernetes)
- **Code change:** None; same Qdrant API.
- **Why:** Storage capacity for full corpus; SLA-backed availability; multi-region.
- **Cost impact:** ~$100–$300/month at mid-scale.

#### Graph DB

- **Phase A:** Neo4j Aura Free
- **Phase B:** Neo4j Aura Professional or self-hosted Enterprise
- **Code change:** None; same Cypher.
- **Why:** Node and relationship limits. Full SC + HC citation network plus patent network exceeds 200K nodes.
- **Cost impact:** $65+/month.

#### Hosting

- **Phase A:** Vercel (frontend) + Cloud Run (backend, scale-to-zero) + Oracle Free ARM VM (always-on workers)
- **Phase B:** Vercel Pro + Kubernetes (or managed equivalents) across multiple regions
- **Code change:** Helm charts replace Cloud Run deploy configs.
- **Why:** Cold-start latency; multi-region; SLA.
- **Cost impact:** $200+/month base, scaling with load.

### 14.4 Interview talking points

The Phase A → Phase B migration is one of the strongest interview talking points the project gives you. Things to be ready to explain:

- **"Why didn't you just use Claude from the start?"** — Cost; portfolio constraint of demonstrating value at zero spend; the architectural discipline of provider portability is itself a senior signal.
- **"What's the actual quality gap between your free stack and Claude?"** — Specific numbers from your eval harness: faithfulness, citation accuracy, recall@10. Show the gap is 3–7 percentage points and explain the mitigations (stricter verifier prompts, more aggressive retrieval, lower retrieval threshold).
- **"How would you decide which upgrade to do first?"** — The eval-driven step ordering in Section 14.2. Each upgrade is justified by its expected impact on a specific metric.
- **"What would break under load?"** — NIM rate limits (most likely first), Qdrant 1 GB ceiling (second), Neon 0.5 GB ceiling (third), Tavily 1K/month (fourth). All have documented mitigations.
- **"What's the unit economics?"** — Phase A: ₹0/query. Phase B: ~₹1.20/query at mid-scale. Both numbers are in the TRD.

---

## 15. Open Engineering Questions

| # | Question | Resolution deadline |
|---|---|---|
| 1 | Local BGE-M3 vs NIM NV-EmbedQA-E5 — benchmark on a 100-question subset | Phase 1 |
| 2 | Optimal NIM-cloud vs local-Ollama split for dev iteration vs eval runs | Phase 1 |
| 3 | Cloud Run free tier vs Oracle Free ARM VM as primary backend host — both viable | Phase 0/10 |
| 4 | Whether to ship Streamlit UI as Phase 3 v0 and Next.js only at Phase 8 — recommended yes | Phase 3 |
| 5 | Manual Bar Council verification in v1.0 vs deferred to v1.1 | Phase 8 |
| 6 | Public vs private eval dashboard — recommended public for portfolio | Phase 4 |
| 7 | Custom domain (₹1,500/yr) vs free Vercel subdomain | Phase 10 |
| 8 | Whether to pre-record a demo video fallback in case live demo fails during an interview | Phase 11 |

---

## 16. Approval

| Role | Name | Date | Status |
|---|---|---|---|
| Technical lead | [Your name] | [Date] | Approved for build |

---

## 17. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 0.1 | [Date] | [You] | Initial outline |
| 1.0 | [Date] | [You] | Approved baseline |
| 1.1 | [Date] | [You] | Dual-track Phase A / Phase B; Section 14 added |

---

## 18. Related Documents

- **Document 1** — PRD
- **Document 3** — AI/ML System Design (the meat of the AI engineering)
- **Document 4** — App Flow & User Journey
- **Document 5** — UI/UX Design
- **Document 6** — Evaluation Plan
- **Document 7** — Safety & Responsible AI
- **Document 8** — Data Architecture
- **Document 9** — API Specification
- **Document 10** — Security & Privacy
- **Document 11** — Deployment & Infrastructure
- **Document 12** — Project Roadmap
- **Document 13** — README & Portfolio Packaging

— end of Document 2 —
