# Project Roadmap

**Project:** Themis Machina
**Assistant:** Themis GPT
**Document:** 12 of 13
**Version:** 1.0
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## 1. Purpose and Scope

This document defines the complete build schedule for Themis Machina: the week-by-week plan across 11 build phases, the specific deliverables and completion criteria for each week, the dependency ordering between phases, and the Phase B production migration plan.

It is the operational backbone of the project. All other documents describe *what* to build and *why*; this document specifies *when* and in *what order*.

---

## 2. Roadmap Philosophy

### 2.1 Phased over sprints

The roadmap is organized into 11 named phases rather than numbered sprints. Phases map to architectural layers: each phase ends with a *demoable, testable system* rather than a collection of half-finished features. This matters for a portfolio project — you can show progress at any point, and hiring managers can see working software rather than a feature list.

### 2.2 Eval gates between phases

Every phase ends with an eval milestone that must be met before the next phase starts. This enforces quality discipline and prevents "we'll fix the retrieval quality later" from becoming a permanent state.

### 2.3 Scope discipline

The roadmap includes a "cut if behind" column for every week. When behind schedule, cut features rather than cut quality. A smaller, polished, well-evaluated system is a stronger portfolio piece than a large, partially-broken one.

### 2.4 Realistic time estimates

These estimates assume **solo development, roughly 15–20 hours per week** (evenings and weekends). If you can commit more, phases compress. If you can commit less, stretch the schedule rather than rushing.

---

## 3. Timeline Overview

| Phase | Name | Weeks | Calendar weeks (example start: Week 1 = Jan 6) | Output |
|---|---|---|---|---|
| 0 | Foundation | 1 | Week 1 (Jan 6–12) | Dev environment, all 13 design docs published |
| 1 | Closed-corpus statute Q&A | 2 | Weeks 2–3 (Jan 13–26) | CLI answering statute questions with citations |
| 2 | Case law expansion | 2 | Weeks 4–5 (Jan 27–Feb 9) | CLI covers statutes + SC cases with treatment awareness |
| 3 | Conversational layer | 2 | Weeks 6–7 (Feb 10–23) | LangGraph orchestration + Streamlit UI |
| 4 | Evaluation harness | 2 | Weeks 8–9 (Feb 24–Mar 9) | Golden eval set + CI integration + published benchmark |
| 5 | Web augmentation | 1 | Week 10 (Mar 10–16) | Tier-aware Tavily + direct official scrapers |
| 6 | Themis Documents | 2 | Weeks 11–12 (Mar 17–30) | Document upload + clause analysis |
| 7 | Themis Patents | 2 | Weeks 13–14 (Mar 31–Apr 13) | Patent search + prior-art module |
| 8 | Production frontend | 2 | Weeks 15–16 (Apr 14–27) | Next.js UI with citation viewer + matters |
| 9 | Observability & safety | 1 | Week 17 (Apr 28–May 4) | Full Langfuse + prompt versioning + red-team |
| 10 | Deployment & launch | 1 | Week 18 (May 5–11) | Live demo at public URL |
| 11 | Polish & packaging | 2 | Weeks 19–20 (May 12–25) | Final README, demo video, blog post |

**Total: 20 weeks (~5 months at part-time pace)**

---

## 4. Phase 0 — Foundation (Week 1)

### Goal

A clean, working development environment with all design documents published and all dependencies verified.

### Week 1 tasks

| Day | Task | Hours |
|---|---|---|
| Mon | Create GitHub repository (public). Initialize Python project with uv, pyproject.toml, ruff, mypy config. Initialize Next.js frontend with pnpm. | 2 |
| Mon | Write and commit all 13 design documents (this roadmap is the last one). | 2 |
| Tue | Set up Docker Compose for local development: Postgres, Qdrant, Neo4j, Redis. Verify all start successfully. | 2 |
| Tue | Register for all free-tier services: NVIDIA NIM, Neon, Qdrant Cloud, Neo4j Aura, Upstash, Cloudflare R2, Clerk, Tavily, Langfuse, Grafana Cloud, Sentry. Collect all API keys. Verify each with a hello-world test. | 3 |
| Wed | Set up Ollama on M1: install, pull Qwen 2.5 14B and Llama 3.2 3B, verify inference works. | 1 |
| Wed | Configure LiteLLM with NIM + Ollama providers. Verify model switching works with a simple completion. | 2 |
| Thu | Write skeleton FastAPI application: health endpoint, auth middleware (Clerk JWT verification), error envelope, security headers, OpenTelemetry skeleton. | 3 |
| Thu | Set up GitHub Actions: basic PR workflow (lint, type-check, unit test with zero tests initially — just verify the workflow triggers). | 1 |
| Fri | Write `.env.example`. Verify `.env.local` is gitignored. Confirm no secrets are committed. | 1 |
| Fri | Write initial Alembic migration (001_initial_schema.py) with the users and sessions tables. Run it against local Postgres. | 2 |
| Weekend | Review all 13 design documents. Flag any inconsistencies. Write the first `DECISIONS.md` (ADR-001: why we chose NVIDIA NIM for Phase A). | 2 |

**Total: ~21 hours**

### Phase 0 completion criteria

- [ ] GitHub repository is public with all 13 design documents
- [ ] `docker compose up` starts all local services without errors
- [ ] `uvicorn src.main:app --reload` starts without errors
- [ ] `/health` returns `{"status": "ok"}`
- [ ] NIM API key verified with a test completion
- [ ] Ollama serving Qwen 2.5 14B (verify: `ollama run qwen2.5:14b "What is Section 420 IPC?"`)
- [ ] LiteLLM switches between NIM and Ollama on demand
- [ ] Alembic migration 001 applied to local Postgres
- [ ] GitHub Actions PR workflow runs (even if trivially — zero tests pass vacuously)

### Cut if behind

The design documents can be shortened for Phase 0 — push depth to Phase 11. The critical path is: working dev environment + NIM + Ollama + LiteLLM + basic FastAPI.

---

## 5. Phase 1 — Closed-Corpus Statute Q&A (Weeks 2–3)

### Goal

A working CLI tool that answers questions about Indian statutes with grounded citations from a closed corpus. No conversation, no UI, no case law — just clean single-shot statute RAG.

### Week 2 — Ingestion pipeline

| Task | Hours |
|---|---|
| Write corpus downloaders: India Code scraper for IPC, NI Act, CPC, CrPC, Contract Act, IT Act, Companies Act, Consumer Protection Act, RERA, Arbitration Act (10 priority statutes to start) | 4 |
| Write the statute parser: extract sections, subsections, section headings, definitions. Output: structured JSON per statute. | 4 |
| Write the statute chunker: one chunk per section, metadata attached (effective dates, section number, amendment references). | 3 |
| Write the embedder: BGE-M3 via FastEmbed, batched. Write chunk ID derivation from content hash. | 2 |
| Write the Qdrant indexer: create the `corpus_statutes` collection with int8 quantization. Batch insert. Verify points are stored. | 2 |
| Run ingestion pipeline on the 10 priority statutes. Verify chunks are queryable. | 1 |
| Benchmark: BGE-M3 local vs NIM NV-EmbedQA-E5 on 20 test queries. Document findings in `DECISIONS.md` ADR-002. | 2 |

**Total: ~18 hours**

### Week 3 — Retrieval and generation

| Task | Hours |
|---|---|
| Write the hybrid retrieval service: Qdrant dense + Qdrant BM25, fused with RRF (k=60). Test against 10 hand-written statute queries. Measure Recall@10. | 4 |
| Write the local reranker: BGE-reranker-v2-m3 via sentence-transformers. Integrate into retrieval service. Benchmark reranker lift on the 10 test queries. | 3 |
| Write the generation prompt (`generate_statute.v1`): citation rules, structured output schema (StructuredAnswer), mode-aware behavior. | 3 |
| Wire up to NIM (Llama 3.3 70B): structured output generation with Pydantic validation. | 2 |
| Write the citation whitelist enforcer (Document 7, §5.2). Unit tests confirming hallucinated citations are stripped. | 2 |
| Write the CLI tool: `python -m themis.cli ask "What does Section 138 NI Act require?"`. Output: formatted answer with citations. | 2 |
| Hand-evaluate 20 statute queries via CLI. Note failures. | 2 |

**Total: ~18 hours**

### Phase 1 completion criteria

- [ ] Ingestion pipeline runs end-to-end for 10 priority statutes
- [ ] Hybrid retrieval (dense + BM25 + RRF) working
- [ ] BGE-reranker reducing top-50 to top-5
- [ ] Generation with structured output (StructuredAnswer) working
- [ ] Citation whitelist enforcer tested with unit tests
- [ ] CLI tool: `python -m themis.cli ask "..."` works
- [ ] Hand-evaluated recall: gold source in top 10 for > 80% of 20 test queries

### Cut if behind

Reduce to 5 priority statutes (IPC, NI Act, CPC, Contract Act, Constitution). Add others in Phase 2.

---

## 6. Phase 2 — Case Law Expansion (Weeks 4–5)

### Goal

Extend the corpus to Supreme Court of India judgments. Add the citation graph in Neo4j. Add treatment-awareness (overruled / distinguished / followed).

### Week 4 — Case corpus ingestion

| Task | Hours |
|---|---|
| Write the SC judgment scraper: download from Indian Kanoon or SC e-SCR (start with ~500 leading constitutional + commercial cases). | 3 |
| Write the case parser: structure-aware parsing of headnote, facts, issues, reasoning, holding. Extract paragraph numbers. | 4 |
| Write the case chunker: one chunk per paragraph within reasoning/holding, separate chunks for headnote and operative order. Metadata: case name, citation, court, date, paragraph number. | 3 |
| Write the Neo4j ingester: create Case, Statute, Court, Person nodes. Ingest citation edges from the case corpus using INTERPRETED and CITES relationships. | 4 |
| Run case law ingestion on the initial 500-case subset. Verify Qdrant + Neo4j are populated. | 2 |

**Total: ~16 hours**

### Week 5 — Treatment-aware retrieval and graph traversal

| Task | Hours |
|---|---|
| Write the citation intent classifier (treatment labeler): LLM-based classification using the `intent.v1` prompt. Classify a sample of 100 citation edges as: follows, distinguishes, doubts, overrules, background. | 3 |
| Write the Neo4j treatment query (Cypher) for "is this case still good law?": traverse from a seed case to all later cases that cite it with treatment labels. | 2 |
| Write the graph expansion retrieval strategy: seed with hybrid retrieval, expand via Neo4j treatment edges. | 3 |
| Write the case generation prompt (`generate_case.v1`): paragraph-number citations, treatment status display, professional vs public mode. | 3 |
| Extend the CLI to handle case queries. Test: "what did the SC hold in Kesavananda Bharati?", "Is ADM Jabalpur still good law?". | 2 |
| Ingest 40 more priority statutes (completing the ~50 act list). | 2 |

**Total: ~15 hours**

### Phase 2 completion criteria

- [ ] 500+ SC cases ingested in Qdrant + Neo4j
- [ ] Treatment graph populated (CITES edges with intent labels)
- [ ] "Is X still good law?" query returns treatment history via graph traversal
- [ ] Case-law retrieval: gold source in top 10 for > 75% of hand-written test queries
- [ ] 50 priority statutes ingested
- [ ] CLI handles both statute and case queries

---

## 7. Phase 3 — Conversational Layer (Weeks 6–7)

### Goal

LangGraph orchestration, multi-turn memory, intent classification, mode selection, coreference resolution. Replace the single-turn CLI with a stateful conversational backend. Add a Streamlit prototype UI.

### Week 6 — LangGraph orchestration

| Task | Hours |
|---|---|
| Write the full ConversationState schema (Document 3, §3.2). | 2 |
| Implement all 8 LangGraph nodes: Guard, Rewrite, Intent, Router, Retrieval, Generate, Verify, Memory. Wire them into the state machine. | 6 |
| Write the Postgres LangGraph checkpointer integration. Test: conversation persists across process restarts. | 2 |
| Write all per-node prompts (guard.v1, rewrite.v1, intent.v1, verify.v1, refusal_advice.v1, clarify.v1, summarize_turn.v1). Register them in the prompt_versions table. | 4 |

**Total: ~14 hours**

### Week 7 — API, memory, and Streamlit UI

| Task | Hours |
|---|---|
| Implement the core API endpoints: `POST /api/v1/conversations`, `POST /api/v1/conversations/{id}/messages` (with SSE streaming). | 4 |
| Implement the three-layer memory: working memory (last 5 turns in prompt), episodic summary (rolling 200-word summary every 5 turns), research focus extraction. | 3 |
| Build the Streamlit prototype UI: a chat interface that consumes the SSE endpoint. Shows streaming text, citation pills, source panel. | 4 |
| Implement mode selection (public/professional) in the API and Streamlit UI. Verify mode-aware generation. | 2 |
| Test multi-turn conversations manually: coreference resolution ("that case" → resolved), follow-ups, mode switching. | 2 |

**Total: ~15 hours**

### Phase 3 completion criteria

- [ ] LangGraph state machine running all 8 nodes
- [ ] Conversation state persisting to Postgres via checkpointer
- [ ] SSE streaming endpoint working
- [ ] Streamlit UI showing streaming chat with citations
- [ ] Multi-turn conversation with coreference resolution working
- [ ] Guard node correctly refusing advice questions in > 90% of manual tests
- [ ] Mode switching (public / professional) working

---

## 8. Phase 4 — Evaluation Harness (Weeks 8–9)

### Goal

Build the golden evaluation set and the CI-integrated harness. This is the most important phase for portfolio signal. Do not rush it.

### Week 8 — Golden set construction

| Task | Hours |
|---|---|
| Write 50 statute-lookup questions (20 easy, 20 medium, 10 hard). For each: question, gold answer summary, required sources, required elements, unacceptable content. Cross-reference every answer against the primary statute text. | 6 |
| Write 40 case-lookup and interpretive questions. Cross-reference against published SCC headnotes or official SC summaries. | 5 |
| Write 10 comparative questions (cross-case, cross-jurisdiction). | 2 |
| Write 30 safety / adversarial questions (15 advice-seeking, 5 indirect advice, 5 prompt injection, 5 scope violations). | 3 |
| Insert all 130 questions into the `eval_questions` table. Mark 20 as `fast_set = TRUE`. | 1 |

**Total: ~17 hours** (the question-writing is slow and careful by design)

### Week 9 — Harness, metrics, and CI

| Task | Hours |
|---|---|
| Write the eval runner: async, NIM-rate-limit-aware (semaphore at 5 concurrent), runs the full Themis pipeline for each question, collects answers and citations. | 4 |
| Integrate RAGAS: faithfulness, answer relevance, context precision, context recall. Configure NIM Llama 3.3 70B as the RAGAS judge. | 2 |
| Write custom metrics: answer correctness (required-elements coverage), citation accuracy (per-claim citation check), hallucinated citation rate, refusal precision, false refusal rate. | 4 |
| Write the regression checker: compare this run's metrics to the previous run's metrics; exit non-zero on > 2pp regression on blocking metrics. | 2 |
| Integrate into GitHub Actions PR workflow (eval-fast job). Test it by intentionally introducing a prompt regression and confirming the PR is blocked. | 2 |
| Write the PR comment formatter (markdown table, before/after comparison). | 1 |
| Run the first full eval. Record the baseline metrics. Publish them in the README. | 2 |

**Total: ~17 hours**

### Phase 4 completion criteria

- [ ] 130-question golden set in `eval_questions` table
- [ ] Eval runner runs end-to-end without manual intervention
- [ ] RAGAS + custom metrics working
- [ ] CI PR workflow: fast set (20 questions) runs on every relevant PR
- [ ] Regression detection: an intentional prompt regression is caught and blocks the PR
- [ ] Baseline metrics published: faithfulness ≥ 80%, citation accuracy ≥ 85%, refusal precision ≥ 90%
- [ ] A quality-over-time chart started (this is the first data point)

---

## 9. Phase 5 — Web Augmentation (Week 10)

### Goal

Tier-aware Tavily integration and direct scrapers for official sources. Every web-sourced claim is labeled by tier.

### Week 10

| Task | Hours |
|---|---|
| Write direct scrapers for Tier 2 official sources: indiacode.nic.in (statute freshness), sci.gov.in (recent SC judgments). Store archives in R2. | 3 |
| Integrate Tavily for Tier 3 (curated commentary) and Tier 4 (general web). Configure `include_domains` whitelist for Tier 3. | 2 |
| Write the web content sanitizer (Document 7, §8.3): strip injection patterns from retrieved web content before it enters the prompt. | 2 |
| Write the source archival flow: at retrieval time, snapshot the web page to R2; serve the snapshot from citations. | 2 |
| Extend the generation prompts with tier-aware citation rules (Document 3, §7.4 citation discipline block). | 1 |
| Add 20 web-augmented questions to the golden set (queries requiring Tier 2 freshness — recent amendments, recent SC judgments not yet in corpus). | 3 |
| Run eval after web integration. Confirm no regression on existing questions. | 2 |

**Total: ~15 hours**

### Phase 5 completion criteria

- [ ] Tier 2 scrapers running (indiacode.nic.in, sci.gov.in)
- [ ] Tavily Tier 3/4 working with domain whitelist
- [ ] Web content sanitizer tested with injection patterns
- [ ] Source archival working (citations point to R2 snapshots)
- [ ] No eval regression on existing 130-question set
- [ ] 20 new questions added for web-augmented coverage

---

## 10. Phase 6 — Themis Documents (Weeks 11–12)

### Goal

User document upload, per-user isolation, on-the-fly parsing, session-scoped private corpus, CUAD clause classification.

### Week 11 — Upload pipeline and isolation

| Task | Hours |
|---|---|
| Implement the document upload API endpoint (`POST /api/v1/documents/upload`). Validate file type, size, MIME. | 2 |
| Write the document encryption layer: per-user key derivation (PBKDF2), Fernet encrypt before R2 upload. | 2 |
| Write the Celery ingestion task: parse with Unstructured.io, OCR if scanned, chunk type-aware, embed with BGE-M3, index into per-user Qdrant collection. | 5 |
| Implement the status SSE stream for document processing. | 2 |
| Write the cross-user isolation integration test (Document 7, §9.1 test). Run it. Confirm it passes. | 2 |
| Add document upload to the Streamlit prototype UI. | 2 |

**Total: ~15 hours**

### Week 12 — CUAD clause classifier and cross-corpus retrieval

| Task | Hours |
|---|---|
| Download CUAD dataset. Fine-tune distilbert-base-uncased on 80% of CUAD (split at contract level). Train on M1 via MPS backend. | 4 |
| Evaluate the fine-tuned CUAD model on the 20% holdout. Report per-class F1 and macro-F1. Compare to published CUAD baseline. | 2 |
| Integrate CUAD classifier into the ingestion pipeline: for detected contracts, label every clause chunk with its CUAD type + risk label. | 2 |
| Implement cross-corpus retrieval: user document chunks + public corpus chunks retrieved and joint-reranked for "compare my contract to typical norms" queries. | 3 |
| Add 30 document-question entries to the golden eval set. Run eval. | 3 |

**Total: ~14 hours**

### Phase 6 completion criteria

- [ ] Document upload API working end-to-end
- [ ] Per-user Qdrant collection isolation confirmed by integration test
- [ ] Application-level document encryption working
- [ ] CUAD classifier fine-tuned: macro-F1 ≥ 0.70 on holdout
- [ ] Clause classification visible in the Streamlit UI
- [ ] Cross-corpus retrieval (user doc + public) working
- [ ] Eval set: 160 questions. No regression on existing metrics.

---

## 11. Phase 7 — Themis Patents (Weeks 13–14)

### Goal

USPTO patent ingestion for one CPC subclass, claim-aware chunking, CPC filtering, patent citation graph, prior-art search with claim-element decomposition.

### Week 13 — Patent corpus ingestion

| Task | Hours |
|---|---|
| Pick a CPC subclass as the portfolio focus (recommendation: H01M — electrochemical energy storage, i.e., batteries. Relevant to EV/clean energy; manageable size; good prior art for demos). | 0.5 |
| Download H01M patents from USPTO bulk data or Google Patents Public Data (BigQuery). ~80K patents. | 2 |
| Write the patent XML parser: extract title, abstract, all claims (preserving structure), key specification sections. | 4 |
| Write the claim-aware chunker: each independent claim as a separate chunk, dependent claims linked to parent, specification sections by type. Full metadata (patent_id, CPC codes, assignee, priority date, status, forward_citation_count). | 3 |
| Create `corpus_patents` Qdrant collection with appropriate metadata payloads. | 1 |
| Run patent ingestion on H01M subset. Ingest patent citation network from PatentsView into Neo4j. | 3 |

**Total: ~13.5 hours**

### Week 14 — Patent retrieval and prior-art pipeline

| Task | Hours |
|---|---|
| Write the patent landscape query: CPC pre-filter → hybrid retrieval → cluster abstracts → LLM landscape summary. | 3 |
| Write the claim decomposer (`claim_decompose.v1` prompt): takes a claim text, outputs a list of elements with IDs. | 2 |
| Write the element coverage NLI check (`element_coverage.v1` prompt): for each (element, candidate chunk) pair, determines coverage. | 2 |
| Write the prior-art report assembler: coverage matrix, element-by-element analysis, novelty assessment with caveats. | 3 |
| Write the patent prior-art API endpoint with SSE streaming for the coverage matrix. | 2 |
| Add patent mode to the Streamlit UI. | 1 |
| Add 40 patent questions to the golden eval set (landscape queries, patent lookups, 5 prior-art queries with known answers). | 3 |

**Total: ~16 hours**

### Phase 7 completion criteria

- [ ] H01M patent corpus ingested (Qdrant + Neo4j)
- [ ] Patent landscape query working with clustered summary
- [ ] Claim decomposition working for test claims
- [ ] Prior-art element coverage matrix computed and displayed
- [ ] Patent forward/backward citation graph traversal working
- [ ] Eval set: 200 questions. Faithfulness ≥ 85%, citation accuracy ≥ 90%.

---

## 12. Phase 8 — Production Frontend (Weeks 15–16)

### Goal

Replace the Streamlit prototype with the Next.js production UI. Implement the citation viewer, source panel, matter persistence, export, and mode selector.

### Week 15 — Core chat UI and citation viewer

| Task | Hours |
|---|---|
| Set up the Next.js app with the Themis design system: tokens (colors, typography, spacing), shadcn/ui base components customized. | 3 |
| Build the chat layout: three-pane structure (sidebar, chat column, source panel). Responsive behavior for < 1280px. | 3 |
| Build the Composer component with SSE consumption, streaming text rendering, citation pill emission on `citation_found` events. | 4 |
| Build the Source Panel: citation cards per tier, verbatim source viewer on click, tier color coding. | 3 |
| Build the Message bubble component with claims, caveats, follow-up suggestion strips, verification status badge. | 2 |

**Total: ~15 hours**

### Week 16 — Matters, export, auth, and mode selector

| Task | Hours |
|---|---|
| Implement Clerk authentication in the Next.js frontend: sign-in flow, JWT management in memory, refresh token cookie. | 3 |
| Build the Sidebar: matters list, "Continue last" item, mode badge at bottom, account/settings links. | 3 |
| Build the Matter management UI: create, rename, archive, tag. Restore conversation from a matter. | 2 |
| Build the Export flow: trigger export, poll status, download PDF/Markdown. | 2 |
| Build the Mode Selector dropdown: public / professional / patent modes, transition message on switch. | 1 |
| Build the Document Upload modal: drag-drop, progress states, clause-flagging panel in source sidebar. | 2 |
| End-to-end smoke test of the full UI: all flows from Document 4 tested manually. | 2 |

**Total: ~15 hours**

### Phase 8 completion criteria

- [ ] Full Next.js UI replacing Streamlit
- [ ] SSE streaming working in the browser
- [ ] Citation pills clickable; source panel opens correct source
- [ ] Clerk authentication working
- [ ] Matters: create, continue, export
- [ ] Document upload: end-to-end working with the real UI
- [ ] Mode selector working; professional mode shows paragraph-level citations

---

## 13. Phase 9 — Observability & Safety Hardening (Week 17)

### Goal

Full Langfuse integration, prompt versioning, end-to-end tracing, prompt injection red-team, OWASP security audit.

### Week 17

| Task | Hours |
|---|---|
| Complete Langfuse integration: tag every LLM call with prompt version, model version, conversation ID. Verify traces appear in Langfuse dashboard. | 2 |
| Implement prompt versioning registry: every prompt served from the `prompt_versions` table, version ID included in every Langfuse trace. | 2 |
| Complete the Grafana Cloud dashboards: operational dashboard (request rate, latency, error rate) and AI quality dashboard (eval metrics over time). | 2 |
| Configure all alerting rules from Document 11, §8.3. Test each alert fires correctly. | 2 |
| Run the full manual red-team battery (Document 7, §11): all 4 areas (novel persona overrides, indirect advice extraction, web content injection, document injection). Write SECURITY.md with findings. | 4 |
| Expand the safety eval set to 50 questions (add 20 injection + indirect advice patterns). Run eval. Verify injection resistance is 100%. | 2 |
| Final prompt versioning audit: confirm every deployed prompt is in the `prompt_versions` table with the correct version string. | 1 |

**Total: ~15 hours**

### Phase 9 completion criteria

- [ ] Every LLM call in Langfuse with prompt version and model version
- [ ] Grafana dashboards live and displaying real data
- [ ] All alerting rules confirmed working
- [ ] Red-team battery complete; SECURITY.md published
- [ ] Safety eval: 50 questions, injection resistance 100%, refusal precision ≥ 93%
- [ ] Eval: 200 questions, faithfulness ≥ 87%, citation accuracy ≥ 91%, hallucinated citation rate ≤ 1.5%

---

## 14. Phase 10 — Deployment & Launch (Week 18)

### Goal

Public live demo at a stable URL. Complete deployment pipeline. All pre-launch checklists passed.

### Week 18

| Task | Hours |
|---|---|
| Run `scripts/bootstrap.sh` against real GCP project. Verify all secrets are in Secret Manager. | 2 |
| Deploy the first production Cloud Run revision. Configure Cloudflare DNS, TLS, WAF rules. | 3 |
| Deploy Next.js frontend to Vercel. Configure custom domain (if purchased) or use themismachina.vercel.app. | 1 |
| Run the full safety checklist (Document 7, §14). Confirm all boxes are checked. | 2 |
| Run the production smoke test: 10 real queries via the live UI, verify streaming, citations, source panel. | 1 |
| Set up the Oracle Free VM: install Ollama, pull models, start embedding server and reranker server, start Celery workers, configure systemd. | 3 |
| Verify end-to-end latency from India: measure p50 and p95 from an Indian IP. Document findings. | 1 |
| Publish `OPERATIONS.md` with the free-tier usage dashboard. | 1 |

**Total: ~14 hours**

### Phase 10 completion criteria

- [ ] Live URL accessible from any browser
- [ ] Cloudflare in front with TLS and WAF
- [ ] CI/CD: staging and production pipelines running
- [ ] Safety checklist: all boxes checked
- [ ] Oracle VM: Ollama, Celery workers, embedding/reranker servers running
- [ ] Latency: p95 under 22s from India (NIM is US-hosted; acceptable)
- [ ] Nightly eval scheduled and running on Oracle VM

---

## 15. Phase 11 — Polish & Portfolio Packaging (Weeks 19–20)

### Goal

The project is complete. Phase 11 turns it into a portfolio artifact that hiring managers respect.

### Week 19 — README and documentation polish

| Task | Hours |
|---|---|
| Write the final README (Document 13). This is the most important single file in the project. | 6 |
| Polish all 13 design documents: fix any inconsistencies discovered during the build, update open questions to reflect actual decisions, update metrics to reflect final eval results. | 4 |
| Write `CONTRIBUTING.md` (how someone would add to this project). | 1 |
| Write `CHANGELOG.md` (what shipped in each phase). | 1 |
| Write `OPERATIONS.md` (the week's free-tier usage snapshot + the known limitations section). | 1 |

**Total: ~13 hours**

### Week 20 — Demo, video, and final publication

| Task | Hours |
|---|---|
| Prepare the hero demo: 5 specific multi-turn research sessions (one statute, one case law, one document, one patent, one cross-corpus) that showcase the full system. Practice each until it runs smoothly. | 3 |
| Record a 3–5 minute demo video: screen record the hero demos, narrate with focus on the AI engineering decisions (not just the output). Avoid a product-pitch tone — this is engineering-focused. | 2 |
| Publish the demo video (YouTube unlisted or Loom). Embed the link prominently in the README. | 0.5 |
| Update the live demo with the final corpus (add remaining High Court cases if Qdrant capacity permits). | 2 |
| Final eval run: publish the final quality metrics in the README quality table. | 1 |
| Write a 2,000-word engineering blog post: "Building Themis Machina — production RAG + GraphRAG + evaluation on free-tier infrastructure". Post to personal blog or dev.to. | 3 |
| Add Themis Machina to your resume and LinkedIn with the live URL and the README metrics table. | 0.5 |
| Share the project: HN Show HN post, relevant subreddits (r/MachineLearning, r/LanguageTechnology, r/india), LegalTech communities. | 1 |

**Total: ~13 hours**

### Phase 11 completion criteria

- [ ] README is publication-quality (passes the "would this impress a senior AI engineer?" test)
- [ ] All 13 design documents are consistent with the built system
- [ ] Demo video is published and linked in the README
- [ ] Final eval results published (faithfulness ≥ 88%, citation accuracy ≥ 92%, hallucinated citation rate ≤ 1%, refusal precision ≥ 95%)
- [ ] Engineering blog post published
- [ ] Project shared publicly

---

## 16. Week-by-Week Summary

| Week | Phase | Primary focus |
|---|---|---|
| 1 | 0 | Dev environment, design docs, NIM + Ollama setup |
| 2 | 1 | Corpus ingestion pipeline for statutes |
| 3 | 1 | Hybrid retrieval, reranker, generation, CLI |
| 4 | 2 | SC case law ingestion + Neo4j citation graph |
| 5 | 2 | Treatment-aware retrieval, case generation |
| 6 | 3 | LangGraph nodes, Postgres checkpointer, prompts |
| 7 | 3 | API endpoints, SSE streaming, Streamlit UI |
| 8 | 4 | Golden eval set construction (130 questions) |
| 9 | 4 | Eval harness, RAGAS, CI integration, baseline metrics |
| 10 | 5 | Web augmentation, Tavily, Tier 2 scrapers |
| 11 | 6 | Document upload pipeline, per-user isolation |
| 12 | 6 | CUAD fine-tuning, cross-corpus retrieval |
| 13 | 7 | Patent ingestion (H01M) + patent citation graph |
| 14 | 7 | Prior-art pipeline, claim decomposition, NLI coverage |
| 15 | 8 | Next.js chat UI, citation viewer, source panel |
| 16 | 8 | Auth, matters, export, mode selector, doc upload UI |
| 17 | 9 | Langfuse, prompt versioning, red-team, safety hardening |
| 18 | 10 | Cloud Run deploy, Cloudflare, Oracle VM, launch |
| 19 | 11 | README, documentation polish |
| 20 | 11 | Demo video, blog post, public launch |

---

## 17. Dependency Map

Some phases have hard dependencies; others can be partially parallelized if you have more time.

```
Phase 0 (Foundation)
    └─► Phase 1 (Statute Q&A)
             └─► Phase 2 (Case Law)  ──────────────────────────────────┐
                      └─► Phase 3 (Conversational)                     │
                               └─► Phase 4 (Eval Harness) ─────────────┤
                                        └─► Phase 5 (Web Aug)          │
                                                 └─► Phase 6 (Docs)    │
                                                          └─► Phase 7 ──┘
                                                          (Patents)
                                                               └─► Phase 8 (Frontend)
                                                                        └─► Phase 9 (Observability)
                                                                                 └─► Phase 10 (Deploy)
                                                                                          └─► Phase 11 (Polish)
```

Phases 6 (Documents) and 7 (Patents) can be swapped in order with no dependency violation. If the patent work interests you more, do Phase 7 before Phase 6.

---

## 18. Risk Register (Schedule)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Indian Kanoon scraping becomes blocked | Medium | High | Switch to SC e-SCR API; use IndiaCode for statutes |
| NVIDIA NIM rate limits cause eval runs to take 3x longer | High | Medium | Run eval with Ollama fallback; reduce concurrency to 3 |
| BGE-M3 local performance is too slow on M1 for ingestion batch | Low | Medium | Use NIM embedding API for ingestion batches; reserve M1 for query-time |
| Qdrant 1 GB exceeded before Phase 7 | Medium | Medium | Use quantization + selective case subset; overflow to Oracle VM |
| CUAD fine-tuning takes too long on M1 | Medium | Medium | Use Hugging Face free GPU (T4) for training; keep M1 for inference |
| Phase scope grows beyond 20 weeks | Medium | Medium | Cut Phase 7 (Patents) to Phase B; deliver Phase 8–11 without patents |
| Cloud Run cold starts cause demo to fail during an interview | Medium | High | Pre-record fallback demo video; keep-alive scheduled job |

---

## 19. Phase B — Production Migration (Post-Portfolio)

Phase B is documented for completeness and interview defense. It is not part of the 20-week build.

### Phase B trigger conditions

Consider initiating Phase B when any of these occur:

- More than 50 daily active users (Qdrant, Neon, and Upstash free tiers begin to constrain)
- An enterprise or law firm expresses serious interest
- A security incident requires stronger controls (SOC2, SSO, audit logging)
- The patent corpus needs to expand beyond one CPC subclass

### Phase B migration order

Following the migration order from TRD Section 14.2:

| Step | Change | Timeline |
|---|---|---|
| 1 | LLM → Claude Sonnet 4 | 1 day (LiteLLM config change) |
| 2 | Fast LLM → Claude Haiku 4.5 | 1 day |
| 3 | Reranker → Cohere Rerank 3 | 1 day |
| 4 | Embeddings → Voyage-law-2 | 1 week (re-embed all chunks: ~$120 cost) |
| 5 | Qdrant → paid (or self-hosted cluster) | 1 week |
| 6 | Neo4j → Aura Pro | 1 day |
| 7 | Neon → Pro / Cloud SQL | 1 day |
| 8 | Hosting → Kubernetes or Cloud Run paid | 2 weeks |
| 9 | Secrets → HashiCorp Vault | 1 week |
| 10 | Monitoring → full production stack | 1 week |
| 11 | High Court corpus expansion | 2–4 weeks ingestion |
| 12 | Full 30K SC corpus | 2 weeks ingestion |

**Estimated Phase B timeline:** 2–3 months to complete all steps.

**Estimated Phase B monthly cost at 500 DAU:** $1,000–$3,500/month (detailed in TRD Section 14.3).

---

## 20. Success Definition

The project is complete and portfolio-ready when all of the following are true:

**Quality:**
- Faithfulness ≥ 88% on the 200-question golden eval set
- Citation accuracy ≥ 92%
- Hallucinated citation rate ≤ 1%
- Refusal precision ≥ 95%
- Prompt injection resistance: 100%

**Product:**
- Live URL accessible from any browser
- All three modules working: Themis Research, Themis Documents, Themis Patents
- Multi-turn conversation with coreference resolution working
- Matter persistence and export working

**Engineering signal:**
- All 13 design documents published in the repo
- SECURITY.md + SECURITY_AUDIT.md published
- Eval dashboard publicly shows quality over time
- Demo video embedded in README
- Engineering blog post published

**Cost:**
- Monthly operating cost: ₹0 (Phase A)

When all of these are true, the project achieves its dual purpose: a useful tool *and* a portfolio artifact that demonstrates senior AI engineering competence.

---

## 21. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | [Date] | [You] | Approved baseline |

---

## 22. Related Documents

All other documents in the set:

- **Document 1** — PRD
- **Document 2** — TRD
- **Document 3** — AI/ML System Design
- **Document 4** — App Flow & User Journey
- **Document 5** — UI/UX Design
- **Document 6** — Evaluation Plan
- **Document 7** — Safety & Responsible AI
- **Document 8** — Data Architecture
- **Document 9** — API Specification
- **Document 10** — Security & Privacy
- **Document 11** — Deployment & Infrastructure
- **Document 13** — README & Portfolio Packaging

— end of Document 12 —
