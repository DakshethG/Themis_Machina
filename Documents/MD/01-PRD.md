# Product Requirements Document (PRD)

**Project:** Themis Machina
**Assistant:** Themis GPT (in-conversation: "Themis")
**Document:** 1 of 13
**Version:** 1.1
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## Change log

- **v1.1** — Restructured cost model and dependency sections to reflect a dual-track plan: **Phase A — Free Tier** (development and portfolio demo, ₹0 monthly cost) and **Phase B — Production-Grade** (post-portfolio upgrade path, documented for interview defense). NVIDIA NIM and local Ollama (Apple Silicon M1) form the LLM substrate during Phase A.
- **v1.0** — Initial baseline.

---

## 1. Executive Summary

Themis Machina is a conversational AI research platform for **Indian law** with **international patent** capability. It serves both legal professionals (lawyers, law students, paralegals) and the general public through a unified conversational interface that adapts its behavior to the user's identified persona and chosen mode. Every answer the system produces is grounded in primary legal sources with verifiable, click-through citations. The system explicitly does not provide legal advice; it provides legal research.

The product is composed of three modules sharing one conversational core:

- **Themis Research** — Indian statutes, regulations, and case law
- **Themis Patents** — international prior-art and patent landscape search
- **Themis Documents** — user-uploaded document grounding (contracts, notices, judgments)

The assistant is named **Themis GPT** in technical contexts and introduces itself in-conversation simply as **"Themis."** The platform is marketed as **Themis Machina** — a deliberate echo of *Lex Machina*, with the personified Greek titaness of divine law and order in place of the abstract Latin noun.

### Two operating phases

Themis Machina is designed and documented for two distinct operating phases:

- **Phase A — Free Tier (development through portfolio demo).** Zero monthly cost. Built on NVIDIA NIM's free LLM endpoints, local Ollama on Apple Silicon, free tiers of Qdrant Cloud, Neo4j Aura, Neon, Cloudflare R2, Clerk, Tavily, Langfuse, Grafana Cloud, Vercel, and Google Cloud Run. This is the configuration the portfolio version actually runs on.
- **Phase B — Production-Grade (post-portfolio upgrade path).** Documented for interview defense and future use. Specifies what would be swapped (Claude Sonnet, Voyage embeddings, Cohere Rerank, managed Postgres, etc.) and the cost and quality impact of each upgrade.

This dual-track structure serves three purposes: it makes the project actually buildable at ₹0; it demonstrates cost-conscious engineering (a senior signal); and it documents a coherent production roadmap that the project could follow if it ever moved beyond portfolio.

This document defines what Themis Machina is, who it serves, what success looks like, what we will and will not build in v1.0, and the constraints — legal, ethical, and engineering — under which it must operate.

---

## 2. Background and Motivation

### 2.1 The problem

Legal research in India is structurally underserved. Three populations feel the gap:

- **Practicing lawyers** rely on expensive proprietary tools (SCC Online, Manupatra, LexisNexis India) that work primarily as keyword search engines. They charge ₹15,000–₹50,000 per seat per year and produce raw lists of cases. The synthesis layer — read, summarize, compare, decide what's relevant — is left to the lawyer.
- **Law students and small-firm lawyers** can use free resources (Indian Kanoon, India Code) but those are also pure search. The synthesis problem is identical.
- **Citizens** facing a legal question affecting them have access to either chaotic Google results or consumer chatbots that confidently hallucinate Indian case citations and conflate Indian and American law.

Across all three, the missing tool is the same: a research assistant that retrieves correctly, synthesizes faithfully, cites every claim, and knows when to refuse.

### 2.2 The patent gap

The patent research problem mirrors this at the international level. Existing patent search interfaces (USPTO PatFT, Google Patents, EPO Espacenet) are search engines, not assistants. Prior-art search demands expertise that engineers building products typically lack; cross-corpus reasoning (a claim's novelty depends on patents, academic literature, and product documentation collectively) is left entirely to the human.

### 2.3 Why now

Three converging factors make Themis Machina buildable in 2026 in a way it would not have been in 2024:

- Strong open-weight LLMs (Llama 3.3 70B, Llama 4, DeepSeek V3, Qwen 2.5) match or approach frontier closed models on most retrieval-augmented generation tasks
- **NVIDIA NIM and similar free-tier endpoints** make these models accessible at no cost for development
- Hybrid retrieval, cross-encoder reranking, structured outputs, and tool-use have matured into production patterns
- The open Indian legal data ecosystem has expanded — India Code, Supreme Court e-SCR, Indian Kanoon — so a credible corpus can be assembled without proprietary licenses
- GraphRAG over citation networks and claim-level NLI techniques are now stable enough for treatment-aware reasoning

### 2.4 The dual purpose

Themis Machina serves a second purpose beyond being a useful product. It is a deliberate, full-stack AI engineering portfolio project designed to demonstrate production-grade competence across:

- Multi-corpus retrieval-augmented generation
- Hybrid lexical + dense + graph retrieval
- Cross-encoder reranking and tier-aware citation
- Conversational orchestration with LangGraph
- Fine-tuning (citation intent and clause classification)
- Continuous evaluation with golden eval sets
- Observability and prompt versioning
- Responsible-AI design under legal constraints
- Production deployment, security, and monitoring
- **Cost-conscious infrastructure choices** (the free-tier build is itself a signal)

The engineering decisions documented across these 13 design documents are part of the artifact. The goal is both a working system *and* a paper trail demonstrating senior AI engineering thinking.

---

## 3. Goals and Non-Goals

### 3.1 Goals

Themis Machina will:

1. Answer legal research questions about Indian law with grounded citations to primary sources
2. Allow conversational, multi-turn research with memory and coreference resolution
3. Support patent and prior-art research over international patent corpora
4. Allow users to upload their own documents and have answers grounded in both the document and the public corpus
5. Distinguish clearly between *what the law says* and *what someone should do*, refusing the latter
6. Provide source-tier-aware citations
7. Produce auditable conversations
8. Maintain measurable answer quality through a continuously evolving evaluation harness with regression protection in CI
9. Serve two personas (professional and public) with mode-aware behavior on a single platform
10. Operate with strict per-user data isolation, no training on user-uploaded content, and clear data retention policies
11. **Run at ₹0 monthly operating cost during the portfolio phase** while remaining architecturally portable to a paid production stack

### 3.2 Non-goals

Themis Machina will not:

1. Provide legal advice or legal opinions on specific fact patterns
2. Recommend a course of action ("you should sue", "you should accept this offer")
3. Predict litigation outcomes, settlement values, or judicial behavior
4. Generate ready-to-file legal documents (petitions, complaints, formal notices)
5. Replace a registered lawyer, advocate, or patent agent
6. Cover non-Indian jurisdictions for general law (only patents are international)
7. Operate as a freedom-to-operate (FTO) opinion tool for patents
8. Train on user-uploaded documents under any circumstance
9. Provide a Hindi or regional-language interface in v1.0

### 3.3 Scope boundary

When the user's request crosses a non-goal boundary, the system explicitly declines that specific request — without abandoning the conversation. The system continues to be helpful within scope. A user asking "can you draft a petition for me?" gets a refusal on drafting plus an offer to summarize the relevant procedure, the typical structure of such a petition, and the standard authorities cited in similar matters.

---

## 4. Users and Personas

The product serves three personas. Personas A and B share the conversational interface; Persona C accesses the Patents module which has a slightly different UI surface.

### 4.1 Persona A — The Legal Professional

**Snapshot:** Practicing lawyers, in-house counsel, law students at recognized institutions, paralegals, and legal researchers.

**Representative user — Priya, 29.** Third-year associate at a mid-sized Bengaluru litigation firm. She handles commercial disputes. She is researching whether a recent Supreme Court judgment on the Insolvency and Bankruptcy Code has impacted the *Essar Steel* line of cases. She needs precise citations, paragraph numbers, and the ability to verify each source quickly.

**Needs:** exact citations in Indian formats (SCC, AIR, JT); paragraph-level references; treatment awareness (overruled / distinguished / followed); export to briefs; legal-terminology tolerance; sustained multi-turn research; honest uncertainty when authorities conflict.

### 4.2 Persona B — The Informed Citizen

**Snapshot:** Citizens researching a legal question affecting them personally.

**Representative user — Arjun, 41.** Small business owner in Indore. Has received a notice under Section 138 of the Negotiable Instruments Act. Wants to understand what this means and what defenses exist before engaging a lawyer.

**Needs:** plain-language explanations; strong reinforcement that this is research not advice; "see a lawyer for this" signposts; what kind of professional to consult; citations to show a lawyer; preliminary research without spending money.

### 4.3 Persona C — The IP Researcher

**Snapshot:** R&D engineers, academic researchers, patent attorneys, IP strategists.

**Representative user — Dr. Meera, 38.** R&D lead at a battery startup. Needs prior-art research across US, EP, IN patents plus academic literature for a graphene cathode innovation.

**Needs:** multi-jurisdictional patent search; claim-element decomposition; cross-corpus retrieval; honest novelty assessment with caveats; CPC awareness; citation-network visualization.

### 4.4 Mode selection

| Mode | Default for | Effects |
|---|---|---|
| **Professional** | Verified legal professionals | Full terminology; citation export; no plain-language softening |
| **Public** | Unauthenticated users | Plain-language; strong disclaimers; "consult a lawyer" routing |
| **Patent** | Anyone using the Patents module | International corpus; claim-element tools; CPC filters; IP-specific UI |

### 4.5 Persona verification

For Professional mode, manual review of a Bar Council number, law-school credential, or organizational email unlocks export features and lighter terminology defaults. Public mode is the system's safe default.

---

## 5. Product Scope

### 5.1 Themis Research (Module 1)

**Corpus:** Constitution of India with amendment effective-dates; ~50 priority central statutes (IPC, CrPC, CPC, Evidence Act, Contract Act, IT Act, Companies Act, GST acts, NI Act, IBC, Arbitration Act, Consumer Protection Act, RERA, etc.); subordinate rules and regulations; Supreme Court judgments 1950–present (~30K judgments); Delhi, Bombay, Karnataka, Madras, Calcutta High Court judgments; Constitutional Assembly Debates.

**Capabilities:** statute lookup; case lookup; interpretive questions; treatment-aware citation; historical/temporal queries; cross-jurisdictional questions within India; procedural questions with "consult a lawyer" guidance.

**Out of scope for v1.0:** lower courts and tribunals; state-specific legislation; Hindi-language interface; audio/video proceedings.

### 5.2 Themis Patents (Module 2)

**Corpus:** USPTO granted patents (1976+) and applications (2001+); EPO patents via OPS; WIPO PATENTSCOPE / DOCDB; Indian Patent Office (InPASS); patent citation network via PatentsView; CPC scheme; arXiv full-text; PMC Open Access subset.

**Capabilities:** patent lookup; landscape view; prior-art search with claim-element decomposition; cross-jurisdictional comparison; cross-corpus prior art; citation graph traversal.

**Out of scope for v1.0:** FTO opinions; validity opinions; drafting assistance; litigation prediction.

### 5.3 Themis Documents (Module 3)

**Capabilities:** upload PDF/DOCX/scanned image up to 25 MB; structure-aware parsing; OCR; session-scoped private vector store; joint document + public corpus queries; CUAD-fine-tuned clause classification on contracts; risk flagging; per-user isolation; deletion on demand and session expiry; never used for training.

**Out of scope for v1.0:** drafting/redlining in binding form; document diff comparison; form-filling automation.

### 5.4 Conversational layer (cross-module)

Multi-turn memory with coreference resolution; topic tracking; clarifying questions on ambiguous intent; mode-aware generation; mid-session mode switching; transcript and citation export; named persistent research matters; conversation forking.

### 5.5 Source augmentation layer (tier-aware)

| Tier | Sources | Use |
|---|---|---|
| **Tier 1** | Closed corpus (statutes, cases, patents) | Primary authority. All "what the law is" claims must cite Tier 1. |
| **Tier 2** | Direct scrape of official sources (indiacode.nic.in, sci.gov.in, prsindia.org) | Freshness checks |
| **Tier 3** | Curated commentary via Tavily whitelist (LiveLaw, Bar and Bench, SCC blog) | Context; labeled as commentary not law |
| **Tier 4** | General web via Tavily | Used cautiously; never sole basis for legal claims |

Citation rendering distinguishes tiers visually; Tier 4 is dimmed and labeled.

---

## 6. Functional Requirements

### 6.1 Conversational

Natural-language English queries; 50-turn conversation state; coreference resolution; intent classification and routing; refusal of out-of-scope / advice / harmful queries while staying helpful in scope; clarifying questions on ambiguity; structured response generation with claims, citations, uncertainty; follow-ups without re-retrieval; first-token streaming under 2s (Phase B) / under 3s (Phase A).

### 6.2 Retrieval

Hybrid BM25 + dense retrieval over all corpora; cross-encoder reranking; metadata filtering (jurisdiction, court, date, statute, section, CPC, assignee); query decomposition; HyDE for vague queries; adaptive re-retrieval; GraphRAG for treatment chains and patent citation chains.

### 6.3 Citation grounding

Every factual claim tagged with citation IDs; citations rejected unless retrieved in the current turn; verifier confirms citation supports the claim; on-click verbatim source viewer; tier badges per citation; quote/paraphrase distinction.

### 6.4 Document upload

PDF, DOCX, scanned image up to 25 MB; structure-aware parsing; OCR for scans; session-scoped vector store; absolute cross-user isolation; deletion on session expiry or user request; no training data use; document-only or joint document+corpus queries.

### 6.5 Patent module

Claim-aware chunking (independent claims separate; dependents linked); CPC pre-filtering; lookup by number/assignee/inventor/CPC/priority date; citation graph expansion; claim-element decomposition; NLI element-coverage check.

### 6.6 Safety and refusal

Refuse legal advice with non-condescending message + professional referral; refuse drafting binding documents; refuse harmful queries; detect and resist prompt injection in retrieved web content; honest uncertainty; no claim to be a licensed professional; advice-adjacent → referral.

### 6.7 Audit and observability

Every query, retrieval, model call, and response logged; conversation transcripts persisted; per-model and per-prompt versioning; per-stage latency and token cost; Langfuse traces.

### 6.8 Accounts and sessions

Anonymous sessions (limited features); authenticated via OAuth (Google, Microsoft, Apple); manual Professional verification; per-user named research matters; per-user document workspaces; account deletion with full data erasure within 30 days.

### 6.9 Export

Conversation transcript as PDF/Markdown; citation list in Indian format and optionally OSCOLA/Bluebook; retrieved public documents; copy-with-citation per answer.

---

## 7. Non-Functional Requirements

### 7.1 Performance — Phase A (Free Tier)

| Metric | Target |
|---|---|
| First-token latency (streamed) | < 3s (p50), < 6s (p95) |
| Full response latency | < 12s (p50), < 20s (p95) |
| Retrieval recall @ 10 (statutes) | > 85% on golden set |
| Retrieval recall @ 10 (cases) | > 80% on golden set |
| Concurrent active sessions | 10 on free-tier infra (NIM rate limits dominate) |

### 7.2 Performance — Phase B (Production)

| Metric | Target |
|---|---|
| First-token latency | < 2s (p50), < 4s (p95) |
| Full response latency | < 8s (p50), < 15s (p95) |
| Retrieval recall @ 10 (statutes) | > 92% on golden set |
| Retrieval recall @ 10 (cases) | > 88% on golden set |
| Concurrent active sessions | 50+ |

### 7.3 Quality (both phases)

| Metric | Phase A target | Phase B target |
|---|---|---|
| Faithfulness | > 88% | > 92% |
| Citation accuracy | > 92% | > 95% |
| Answer correctness (LLM-as-judge) | > 75% | > 80% |
| Refusal precision (adv. set) | > 95% | > 95% |
| Hallucinated citation rate | < 2% | < 1% |

Note: Phase A targets are deliberately slightly lower because open-weight Llama 3.3 70B and DeepSeek V3 perform marginally below Claude Sonnet on citation-grounded legal tasks (typically a 3–7 percentage point gap on faithfulness in published evals). The architectural gap is closed by stricter prompt engineering, more aggressive verification, and a tighter retrieval-side citation enforcement — discussed in Document 3.

### 7.4 Cost — Phase A (the entire build)

| Item | Cost |
|---|---|
| **Monthly operational cost** | **₹0** |
| NVIDIA NIM (LLMs, embeddings, reranker) | Free tier |
| Local Ollama on M1 (fallback + dev) | Free (hardware already owned) |
| Qdrant Cloud (1 GB) | Free tier |
| Neo4j Aura | Free tier |
| Neon Postgres (0.5 GB) | Free tier |
| Upstash Redis (256 MB) | Free tier |
| Cloudflare R2 (10 GB) | Free tier |
| Clerk Auth (10K MAU) | Free tier |
| Tavily search (1K/month) | Free tier |
| Vercel + Google Cloud Run + Oracle Free VM | Free tier |
| Langfuse Cloud (50K obs/month) | Free tier |
| Grafana Cloud + Sentry | Free tier |
| GitHub Actions (public repo) | Free unlimited |
| Custom domain (optional) | ~₹1,500/year |

### 7.5 Cost — Phase B (production at mid-scale, ~500 daily active users)

| Item | Approx monthly cost |
|---|---|
| Claude Sonnet (primary LLM) | $400–$1,200 |
| Claude Haiku (verifier, router) | $50–$200 |
| Voyage embeddings + reranker, Cohere Rerank | $50–$200 |
| Qdrant Cloud paid | $100–$300 |
| Neo4j Aura Professional | $65–$200 |
| Managed Postgres (Neon/Supabase Pro) | $25–$100 |
| Redis (Upstash paid) | $20–$100 |
| Cloudflare R2 (paid usage) | $10–$50 |
| Clerk paid / WorkOS | $25–$200 |
| Tavily paid + Exa | $50–$200 |
| Container hosting (Cloud Run paid + workers) | $100–$300 |
| Observability (Langfuse + Grafana + Sentry paid) | $100–$300 |
| **Total monthly** | **$1,000 – $3,500** |

Detailed migration analysis lives in **TRD Section 14 — Free-Tier vs Production**.

### 7.6 Reliability

| Metric | Phase A | Phase B |
|---|---|---|
| Uptime | Best-effort (free tiers may sleep on idle) | 99.5% |
| Graceful degradation | Manual fallback chain (NIM → Ollama → cached) | Automatic via LiteLLM |
| Backups | Weekly manual export | Daily automated |

### 7.7 Security and privacy (identical across phases)

| Requirement | Specification |
|---|---|
| Authentication | OAuth 2.1 with PKCE (Clerk) |
| Data in transit | TLS 1.3 |
| Data at rest | AES-256 (provider-managed) |
| User document isolation | Per-user Qdrant collections + Postgres RLS + audit |
| PII in logs | Tokenized |
| Audit retention | 1 year |
| Compliance | DPDP-aligned defaults |

### 7.8 Accessibility

WCAG 2.1 AA: keyboard navigation, screen-reader compatibility, color contrast, resizable text, logical heading structure.

### 7.9 Internationalization

English-only UI in v1.0. Source language preserved verbatim. INR display. DD MMM YYYY dates. Hindi UI in v1.1.

---

## 8. Success Metrics

### 8.1 Engineering success (Phase A targets)

- Eval harness reports > 88% faithfulness, > 92% citation accuracy, < 2% hallucinated citation rate on the v1.0 golden eval set (200 questions)
- End-to-end p95 latency under 20 seconds
- Prompt-injection red-team defense rate > 95%
- Advice-seeking refusal precision > 95%
- CI runs full eval on every PR touching retrieval or generation; blocks merges on > 2pp regression

### 8.2 Product success (in the public demo)

- Median session length > 5 minutes
- Average turns per session > 4
- Refusal-on-scope under 5% of sessions
- > 30% of authenticated users return within 30 days

### 8.3 Portfolio success

- Published README walks readers through retrieval design, eval methodology, safety reasoning, and observability at senior-engineer depth
- Live demo accessible at a custom domain or free-tier subdomain
- Eval dashboard publicly shows quality progression
- All 13 design documents published alongside code
- 3–5 minute demo video shows real multi-turn legal research
- **README includes the "Production Migration Plan" section** (the Phase A → Phase B walkthrough)

---

## 9. Constraints and Risks

### 9.1 Legal and regulatory

- Not a law firm or legal services provider
- All marketing distinguishes research from advice
- DPDP compliance for user data
- Bar Council of India rules — position outside legal-services definitions
- Patents Act — no patentability opinions
- Disclaimer text reviewed by a qualified lawyer before public launch

### 9.2 Technical risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM hallucinated citations leak to users | Medium | High | Verifier + structured generation + retrieved-set whitelist |
| Corpus gaps or errors | High | Medium | Tier-aware augmentation; honest "I'm not sure" |
| Prompt injection from web sources | Medium | High | Sanitization; instruction isolation; treat web content as data |
| Latency exceeds usability threshold | Medium (Phase A) / Low (Phase B) | Medium | Streaming; caching; provider prompt cache |
| NIM rate-limit during eval batch runs | High (Phase A) | Medium | Concurrency caps in eval runner; Ollama fallback |
| NIM model deprecation mid-build | Medium | Medium | TRD specifies model *categories* with multiple acceptable choices |
| Free-tier Qdrant 1 GB capacity exceeded | Medium | Medium | Aggressive chunk size tuning; spill cases to Postgres |
| Cost runaway in Phase B | Medium | Medium | Per-user budgets; SLM routing; cost telemetry |

### 9.3 Product risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Users misuse outputs as legal advice | High | High | Persistent disclaimers; advice-mode refusal; UI tone |
| Lawyers reject AI tooling on principle | Medium | Medium | Research aid, not replacement |
| Public users overestimate the system | High | High | Plain-language disclaimers in public mode |
| Patent users seek FTO opinions | Medium | High | Explicit refusal + "see a patent agent" routing |

### 9.4 Portfolio-specific risks

| Risk | Mitigation |
|---|---|
| Scope creep delays launch | Phased plan; cut features to ship Phase 10 |
| Eval set too easy or too hard | Build incrementally; baseline comparison |
| Demo breaks during interview | Pre-recorded fallback; offline mode |
| Free-tier provider changes terms mid-build | Architecture is provider-portable via LiteLLM and interface abstraction |

---

## 10. Dependencies — Dual Track

External dependencies are listed in two columns: the Phase A free-tier choice and the Phase B production choice.

### 10.1 External services

| Capability | Phase A (Free) | Phase B (Production) | Failover during Phase A |
|---|---|---|---|
| Primary LLM | NVIDIA NIM (Llama 3.3 70B / Llama 4 / DeepSeek V3) | Anthropic Claude Sonnet | Ollama local Qwen 2.5 14B |
| Fast LLM (router, verifier) | NVIDIA NIM (Llama 3.1 8B / Nemotron-mini) | Claude Haiku or GPT-4o-mini | Ollama local Llama 3.2 3B |
| Embeddings | NVIDIA NIM (NV-EmbedQA-E5) or BGE-M3 local | Voyage-law-2 or Voyage-3-large | Local BGE-M3 always-available |
| Reranker | NVIDIA NIM (NV-RerankQA-Mistral4B) or BGE-reranker local | Cohere Rerank 3 | Local BGE-reranker always-available |
| Vector DB | Qdrant Cloud free 1 GB | Qdrant Cloud paid or self-host | Self-host Qdrant in Docker |
| Lexical (BM25) | Qdrant native BM25 | Same (or dedicated Elasticsearch) | — |
| Graph DB | Neo4j Aura Free (200K nodes) | Neo4j Aura Pro or self-host Enterprise | Self-host Neo4j Community |
| Relational DB | Neon free (0.5 GB) | Neon Pro / Supabase Pro / RDS | Self-host Postgres |
| Cache / queue | Upstash Redis free (256 MB) | Upstash paid / self-host | Postgres-cache fallback |
| Object storage | Cloudflare R2 free (10 GB) | R2 paid | — |
| Auth | Clerk free (10K MAU) | Clerk paid / WorkOS | Self-host Authentik |
| Web search | Tavily free (1K/month) | Tavily paid + Exa | Direct scraping only |
| Doc parsing | Unstructured OSS + LlamaParse free (1K pages/day) | LlamaParse paid + Reducto | PyMuPDF local |
| OCR | Tesseract local | AWS Textract / Azure Doc Intelligence | — |
| LLM observability | Langfuse Cloud free (50K obs/month) | Langfuse paid / self-host enterprise | Self-host Langfuse |
| General observability | Grafana Cloud free + Sentry free | Grafana Cloud paid / DataDog | OTel + local stack |
| Frontend hosting | Vercel free | Vercel Pro | — |
| Backend hosting | Cloud Run free + Oracle Cloud Free ARM VM | Kubernetes (GKE/EKS) or managed | — |
| CI/CD | GitHub Actions (public repo, unlimited) | Same | — |
| Domain | Vercel subdomain free, or custom (~₹1,500/yr) | Custom domain | — |

### 10.2 Data dependencies (identical in both phases)

| Source | Acquisition | Licensing |
|---|---|---|
| India Code | Scrape / bulk | Public domain |
| Supreme Court e-SCR | API / scrape | Public domain |
| Indian Kanoon | Rate-limited scrape | Re-use of public judgments |
| High Court judgments | Per-court scrape | Public domain |
| USPTO bulk data | Direct download | Public domain |
| Google Patents Public Data | BigQuery free tier | Free |
| EPO OPS | API | Free for moderate use |
| Indian Patent Office (InPASS) | Scrape | Public domain |
| arXiv | S3 bulk | arXiv license |
| PMC OA | FTP bulk | PMC OA license |
| CPC scheme | Direct download | Public |

### 10.3 Open-source dependencies (identical in both phases)

LangGraph, LiteLLM, Qdrant client, Elasticsearch client (if needed), Neo4j Python driver, Postgres (psycopg / SQLAlchemy), Redis client, Unstructured.io, PyMuPDF, Tesseract, FastEmbed (for local embeddings), sentence-transformers (for local reranker), FastAPI, Pydantic, Celery, Next.js, RAGAS, DeepEval.

---

## 11. Release Phases and Roadmap

Themis Machina ships across 11 distinct build phases over ~20 weeks at solo, part-time pace. Headline phases:

| Phase | Output |
|---|---|
| 0 — Foundation | Dev environment, design docs published |
| 1 — Closed-corpus statute Q&A | CLI tool answering statute questions with citations |
| 2 — Case law expansion | Statutes + Supreme Court cases |
| 3 — Conversational layer | LangGraph orchestration + Streamlit UI |
| 4 — Evaluation harness | Golden eval set + CI + first benchmark |
| 5 — Web augmentation | Tier-aware Tavily + direct official-source scrape |
| 6 — Themis Documents | Document upload + isolation + CUAD clause analysis |
| 7 — Themis Patents | International patents + claim-element prior art |
| 8 — Production frontend | Next.js + citation viewer + matter persistence |
| 9 — Observability and safety | Full Langfuse / OTel / prompt versioning |
| 10 — Deployment and launch | Live demo at custom or free subdomain |
| 11 — Polish and portfolio packaging | README, demo video, design-doc cleanup |

The full schedule lives in **Document 12 — Project Roadmap**.

**Phase B (Production Migration)** is a documented but not-executed phase, described in **TRD Section 14** for portfolio defense purposes.

---

## 12. Open Questions

| # | Question | Resolution deadline |
|---|---|---|
| 1 | Local embedding (BGE-M3) vs NIM embedding (NV-EmbedQA-E5) — benchmark on a 100-question subset | Phase 1 |
| 2 | Optimal mix of NIM-cloud and local-Ollama for dev iteration vs eval runs | Phase 1 |
| 3 | Cloud Run free tier vs Oracle Cloud Free Forever ARM VM as primary backend host | Phase 10 |
| 4 | Whether to ship Streamlit UI as v0 (Phase 3) and Next.js only at Phase 8 — recommended yes | Phase 3 |
| 5 | Manual Bar Council verification in v1.0 vs deferred to v1.1 | Phase 8 |
| 6 | Public vs private eval dashboard — recommended public for portfolio | Phase 4 |
| 7 | Custom domain (₹1500/yr) vs free Vercel subdomain | Phase 10 |
| 8 | Whether to pre-record a demo video fallback in case live demo fails in an interview | Phase 11 |

---

## 13. Approval

| Role | Name | Date | Status |
|---|---|---|---|
| Project owner | [Your name] | [Date] | Approved for build |
| Technical lead | [Your name] | [Date] | Approved |

---

## 14. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 0.1 | [Date] | [You] | Initial outline |
| 1.0 | [Date] | [You] | Approved baseline |
| 1.1 | [Date] | [You] | Dual-track Phase A / Phase B added |

---

## 15. Related Documents

- **Document 2** — Technical Requirements Document (TRD)
- **Document 3** — AI/ML System Design
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

— end of Document 1 —
