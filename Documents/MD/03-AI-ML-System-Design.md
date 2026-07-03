# AI/ML System Design Document

**Project:** Themis Machina
**Assistant:** Themis GPT
**Document:** 3 of 13
**Version:** 1.0
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## 1. Purpose and Scope

This document is the source of truth for every AI/ML decision in Themis Machina: how retrieval is designed, how chunking is structured per corpus, how the conversational agent orchestrates a turn, how prompts are written and versioned, how citation grounding is enforced, how fine-tuning is approached, how model selection is rationalized, and how the system improves over time.

It complements **Document 2 (TRD)** by going deep on the AI engineering layer; the TRD covers the system-level engineering. Eval methodology lives in **Document 6**; safety in **Document 7**; this document touches both at the design level.

Like the TRD, this document is dual-track: every model and component choice is specified for **Phase A (Free Tier)** and **Phase B (Production-Grade)**. Phase A is the build target.

---

## 2. Design Principles

The AI/ML layer is built on eight load-bearing principles. Every subsequent section traces back to these.

1. **Retrieval beats memorization.** No legal claim is generated from parametric knowledge; every claim must be backed by retrieved text. The model is a synthesizer, not an oracle.
2. **Citations are part of the contract.** A response without correctly-attached, verified citations is a failed response — treated as a system error, not a quality issue.
3. **Right retrieval for right query.** Different question types need different retrieval strategies. The router picks; the engine doesn't apply one strategy uniformly.
4. **Verify what you generate.** Every claim is independently verified against its cited source by a separate model call before reaching the user. This is the single most important defense against hallucination.
5. **Refuse explicitly, helpfully.** When a query crosses the advice line, the system refuses with reasoning and offers what it *can* do, never leaving the user stuck.
6. **Provider portability is non-negotiable.** Every model interaction is mediated by LiteLLM or a typed interface. Phase A → Phase B is a config change, not a refactor.
7. **Eval-driven change.** Every change to retrieval, chunking, prompts, or models triggers the eval harness. Regressions block merges.
8. **Boring engineering wins.** Where a simpler approach works, take it. Over-engineering an LLM pipeline is the most common failure mode in modern AI systems.

---

## 3. Conversational Orchestration with LangGraph

### 3.1 Why LangGraph

LangGraph provides three things that simpler chains do not: explicit state machines (the conversation is a graph, not a pipeline), durable checkpoints (the conversation survives restarts and crashes), and conditional edges (routing on classified intent is first-class). For a multi-turn conversational research system with branching retrieval paths, these are necessary, not nice-to-haves.

### 3.2 State schema

The agent's state is the source of truth between turns. Every node reads from it; some nodes write to it. The state schema:

```python
class ConversationState(TypedDict):
    # Identity
    conversation_id: str
    user_id: str | None  # None for anonymous sessions
    matter_id: str | None  # the named research matter, if any

    # Mode
    mode: Literal["professional", "public", "patent"]
    verified_professional: bool

    # Message history
    messages: list[Message]  # full conversation, OpenAI-style format

    # Current turn intermediate state
    raw_query: str  # what the user just typed
    rewritten_query: str | None  # coreference-resolved standalone query
    intent: Intent | None  # classified intent
    jurisdiction_filter: str | None  # e.g., "india", "supreme_court"
    time_filter: TimeRange | None  # e.g., "before 2018-08-15"
    retrieval_strategy: RetrievalStrategy | None
    retrieved_chunks: list[RetrievedChunk]  # this turn's retrievals
    draft_answer: StructuredAnswer | None
    verified_answer: VerifiedAnswer | None

    # Persistent (carried across turns)
    accumulated_sources: dict[str, RetrievedChunk]  # all sources used this session, by id
    topic_summary: str  # rolling summary of the research topic
    research_focus: str | None  # what the user is researching, distilled
    clarifications_asked: list[str]  # so we don't re-ask the same thing
    refusals_this_session: int  # tracks pattern; triggers a softer re-engagement after 3

    # Telemetry
    turn_count: int
    last_model_versions: dict[str, str]  # which model handled which node
    last_prompt_versions: dict[str, str]  # which prompt versions ran
```

The state is persisted at every turn boundary via LangGraph's Postgres checkpointer, keyed by `conversation_id`. Reloading is cheap.

### 3.3 The state machine

The conversation graph for one turn:

```
                  ┌─────────────────┐
                  │  START          │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 1. Guard / scope│
                  └────────┬────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
       refusal         in-scope       clarify-needed
            │              │              │
            ▼              ▼              ▼
       ┌────────┐   ┌─────────────┐   ┌─────────────┐
       │ Refuse │   │ 2. Coref +  │   │ Ask         │
       │ Node   │   │  rewrite    │   │ clarifying  │
       └────┬───┘   └──────┬──────┘   │ question    │
            │              │           └──────┬──────┘
            │       ┌──────▼──────┐           │
            │       │ 3. Intent   │           │
            │       │   classify  │           │
            │       └──────┬──────┘           │
            │              │                  │
            │       ┌──────▼─────────┐        │
            │       │ 4. Retrieval   │        │
            │       │    router      │        │
            │       └──────┬─────────┘        │
            │              │                  │
            │   ┌──────────┼───────────┐      │
            │   │          │           │      │
            │   ▼          ▼           ▼      │
            │  Hybrid    Graph     Adaptive   │
            │  retrieve  expand    retrieve   │
            │   │          │           │      │
            │   └──────────┼───────────┘      │
            │              │                  │
            │       ┌──────▼──────┐           │
            │       │ 5. Rerank   │           │
            │       └──────┬──────┘           │
            │              │                  │
            │       ┌──────▼──────┐           │
            │       │ 6. Generate │           │
            │       │  (streaming)│           │
            │       └──────┬──────┘           │
            │              │                  │
            │       ┌──────▼──────────┐       │
            │       │ 7. Verify       │       │
            │       │   citations     │       │
            │       └──────┬──────────┘       │
            │              │                  │
            │       ┌──────▼──────┐           │
            │       │ 8. Memory   │           │
            │       │    update   │           │
            │       └──────┬──────┘           │
            │              │                  │
            └──────────────┴──────────────────┘
                           │
                  ┌────────▼────────┐
                  │  END            │
                  └─────────────────┘
```

### 3.4 Node-by-node specification

Each node has a stable name, a clear contract, a model assigned (Phase A and Phase B), a prompt version, and a defined error mode.

#### Node 1 — Guard / Scope Check

**Purpose:** Determine whether to proceed, refuse, or ask for clarification.

**Inputs:** `raw_query`, last 3 messages, `mode`.

**Outputs:** One of `{in_scope, refusal_advice, refusal_harmful, refusal_out_of_jurisdiction, clarify_needed}`.

**Model — Phase A:** NIM Llama 3.1 8B Instruct (fast, structured output).
**Model — Phase B:** Claude Haiku 4.5.

**Prompt sketch (versioned as `guard.v1`):**

```
You are the safety guard for Themis, a legal research assistant for Indian law.

Classify the user's latest message into exactly one of:

- in_scope: a legal research question that Themis can answer
- refusal_advice: requests legal advice for the user's situation
  ("should I sue", "what do you recommend", "what should I do")
- refusal_harmful: requests assistance with illegal activity
- refusal_out_of_jurisdiction: asks about non-Indian general law
  (US law, UK law, etc. — patents are exempt; international patents are in scope)
- clarify_needed: in scope but missing critical context
  (no jurisdiction specified for an ambiguous case name; no time period
  for a "current" question; etc.)

Mode context: {mode}
Prior conversation summary: {topic_summary}
Last user message: {raw_query}

Respond with a JSON object:
{
  "classification": "...",
  "reasoning": "...",
  "clarifying_question": "..." (only if classification is clarify_needed)
}
```

**Error mode:** If classification fails or returns invalid JSON, treat as `in_scope` and proceed (fail open on the safety side biases against false refusals; downstream verifier catches actual problems).

**Latency budget:** 600ms p95.

#### Node 2 — Coreference Resolution & Query Rewrite

**Purpose:** Produce a standalone retrieval query from the conversational query.

**Inputs:** `raw_query`, full message history, `topic_summary`.

**Outputs:** `rewritten_query`, optional explicit `jurisdiction_filter` and `time_filter` if implied.

**Model — Phase A:** NIM Llama 3.1 8B Instruct.
**Model — Phase B:** Claude Haiku 4.5.

**Prompt sketch (versioned as `rewrite.v1`):**

```
You rewrite conversational legal queries into standalone retrieval queries.

Resolve all references using the conversation history:
- "that case" → the specific case mentioned
- "the second one" → the second item in the prior response
- "the earlier section" → the specific section number
- "what about X" → expanded to a standalone question about X

Also extract:
- jurisdiction: india_general | supreme_court | high_court_delhi | ... | null
- time: a date range if implied (e.g., "before the 2018 amendment" → before 2018-08-15)

Conversation history (last 5 turns): {messages}
Topic summary: {topic_summary}
Latest user message: {raw_query}

Respond with JSON:
{
  "rewritten_query": "standalone query, max 50 words",
  "coreferences_resolved": ["it → X", "the case → Y"],
  "jurisdiction": "...",
  "time_filter": {"before": "...", "after": "..."} | null
}
```

**Error mode:** On failure, use `raw_query` as `rewritten_query` and proceed.

**Latency budget:** 700ms p95.

#### Node 3 — Intent Classification

**Purpose:** Pick the right retrieval strategy.

**Inputs:** `rewritten_query`, `mode`.

**Outputs:** `intent` — one of a fixed set:

| Intent | Description | Retrieval strategy |
|---|---|---|
| `statute_lookup` | "What does Section X say?" | Hybrid, statute corpus, exact-section boost |
| `case_lookup` | "Find me Kesavananda Bharati" | Hybrid + exact-citation fast path |
| `interpretive` | "How have courts interpreted X" | Hybrid + graph expansion (treatment) |
| `comparative` | "Compare X across two cases" | Multi-query decomposition + parallel retrieval |
| `temporal` | "What did X say before 2018?" | Hybrid + time filter |
| `procedural` | "How do I file a writ petition?" | Hybrid + strong "consult a lawyer" disclaimer |
| `patent_lookup` | "Show US10765432" | Patent corpus, by-number |
| `patent_landscape` | "Patents on solid-state batteries" | Patent corpus, CPC filter, landscape mode |
| `prior_art_search` | "Find prior art for this claim" | Multi-corpus, claim-element decomposition |
| `document_question` | "Does my contract say X?" | User document corpus + optional public |
| `cross_corpus` | "How does Indian law + patents apply to X?" | Multi-corpus, multi-query |
| `chitchat` | "thanks", "hello" | No retrieval |

**Model — Phase A:** NIM Llama 3.1 8B Instruct.
**Model — Phase B:** Claude Haiku 4.5 (faster classification).

**Prompt sketch (`intent.v1`):** few-shot prompt with 2 examples per intent class.

**Error mode:** Default to `interpretive` (a safe, broad strategy).

**Latency budget:** 400ms p95.

#### Node 4 — Retrieval Router

**Purpose:** Take the intent and produce a concrete retrieval plan.

**Inputs:** `intent`, `rewritten_query`, filters, `mode`.

**Outputs:** A `RetrievalPlan` — a sequence of retrieval calls with strategies, corpora, filters, top_k, tier policy.

This node is deterministic (rules-based), not an LLM call. It's a function mapping `(intent, filters, mode)` to a `RetrievalPlan`.

Example plans:

- For `statute_lookup`:
  ```python
  RetrievalPlan(
      calls=[RetrievalCall(
          corpus="statute",
          strategy="hybrid",
          filters={"jurisdiction": "india"},
          top_k=10,
          tier_policy=TierPolicy.TIER_1_ONLY,
      )],
      rerank_top_k=5,
  )
  ```

- For `interpretive`:
  ```python
  RetrievalPlan(
      calls=[
          RetrievalCall(corpus="case_law", strategy="hybrid", top_k=20, ...),
          RetrievalCall(corpus="statute", strategy="hybrid", top_k=10, ...),
      ],
      post_processing=[GraphExpand(on="case_law", relation="cites_with_treatment", max_hops=1)],
      rerank_top_k=8,
  )
  ```

- For `comparative`:
  ```python
  RetrievalPlan(
      decomposition=True,  # rewrite into sub-queries
      per_subquery=RetrievalCall(corpus="case_law", strategy="hybrid", top_k=10, ...),
      merge_strategy="rrf",
      rerank_top_k=10,
  )
  ```

**Why a rules-based router and not an LLM:** Determinism, debuggability, zero latency. The intent classifier did the LLM work; this node converts intent to plan.

#### Node 5 — Retrieval (executes the plan)

This invokes the Retrieval Service (defined in TRD §4.4). The service is the interface between the orchestrator and the underlying retrieval engines (Qdrant, Neo4j, Tavily). See §4 of this document for full retrieval design.

**Latency budget:** Varies by plan; typical 500–1500ms.

#### Node 6 — Generation

**Purpose:** Produce a structured, cited answer from retrieved chunks.

**Inputs:** `rewritten_query`, `retrieved_chunks` (post-rerank), `messages`, `mode`.

**Outputs:** `StructuredAnswer` (defined below); streamed token-by-token to the client.

**Model — Phase A:** NIM Llama 3.3 70B Instruct (or Llama 4 Maverick when available).
**Model — Phase B:** Claude Sonnet 4.

**Streaming:** Yes. The client begins rendering on the first token. The verifier runs in parallel and updates the UI asynchronously.

**Structured output schema:**

```python
class Citation(BaseModel):
    source_id: str  # references a chunk in retrieved_chunks
    locator: str | None  # paragraph number, section, etc.
    is_quote: bool  # true if the claim quotes the source verbatim

class Claim(BaseModel):
    text: str
    citations: list[Citation]
    confidence: Literal["high", "medium", "low"]

class StructuredAnswer(BaseModel):
    answer_summary: str  # 2-3 sentence summary for at-a-glance
    claims: list[Claim]  # ordered claims composing the full answer
    caveats: list[str]  # uncertainties, conflicting authorities, etc.
    follow_up_suggestions: list[str]  # max 3
    refusal_added: str | None  # if part of the response is a refusal
    advice_disclaimer_shown: bool  # mode-dependent
```

**Prompt sketch (`generate.v1`):**

```
You are Themis, a legal research assistant for Indian law. You answer using ONLY the provided sources. You never give legal advice; you only describe what the law says and how courts have interpreted it.

CRITICAL RULES:
1. Every factual or legal claim must be attached to one or more source IDs from the provided sources.
2. Never cite a source that isn't in the provided list.
3. If the sources don't support a confident answer, say so explicitly.
4. Quote statute language verbatim when reciting it; otherwise paraphrase.
5. Note conflicts between authorities when they exist.
6. In public mode, use plain language; in professional mode, use standard legal terminology.
7. For procedural or advice-adjacent questions, end with a suggestion to consult a qualified lawyer.

Mode: {mode}
User question: {rewritten_query}
Conversation focus: {research_focus}

Sources:
[s1] id=stat_ipc_420, type=statute, citation="IPC § 420"
     Effective dates: 1860-present (current version)
     Tier: 1 (primary authority)
     Text:
     {chunk text}

[s2] id=case_smt_selvi_2010, type=case, citation="Smt. Selvi v. State of Karnataka, (2010) 7 SCC 263"
     Tier: 1 (primary authority)
     Treatment: not overruled
     Relevant excerpt (para 26):
     {chunk text}

[s3] type=web, citation="LiveLaw, 'Supreme Court Holds...', published 2024-03-15"
     Tier: 3 (curated commentary)
     Snapshot URL: {archived url}
     Excerpt:
     {chunk text}

Return a JSON object matching the StructuredAnswer schema.

Important: Tier 1 citations are required for any statement of legal rule. Tier 2/3 citations may support contextual claims but cannot be the sole basis for stating what the law is.
```

**Error mode:** If structured output parsing fails, retry once with a slightly stricter prompt. If still failing, return an error to the user ("I had trouble structuring the answer — could you rephrase your question?").

**Latency budget:** 3.5–5.5s p95 streamed (Phase A); 2.5–4s p95 (Phase B).

#### Node 7 — Citation Verifier

**Purpose:** Independently verify that every cited source actually supports the claim it backs.

**Inputs:** `draft_answer.claims`, `retrieved_chunks`.

**Outputs:** `VerifiedAnswer` — same shape as draft, but each claim has a `verification_status ∈ {supported, partially_supported, unsupported, no_check}`.

**Model — Phase A:** NIM Llama 3.1 8B Instruct.
**Model — Phase B:** Claude Haiku 4.5.

**Why a separate verifier and not part of generation:** Separation of concerns. The generator is incentivized to produce a smooth answer; the verifier is incentivized to be skeptical. Different models, different prompts, different temperatures.

**Prompt sketch (`verify.v1`):**

```
You are a strict legal citation verifier. For each (claim, cited_source_id) pair, determine whether the source ACTUALLY supports the claim.

A claim is supported if:
- The cited source contains text that directly supports it, OR
- A reasonable reading of the source as a whole entails the claim

A claim is unsupported if:
- The source doesn't contain the relevant content
- The source addresses a different point
- The claim overgeneralizes from what the source says

Claim: "{claim.text}"
Cited source [{source_id}]:
{full chunk text}

Respond with JSON:
{
  "verification": "supported" | "partially_supported" | "unsupported",
  "reasoning": "one sentence",
  "suggested_correction": "..." (only if partially_supported or unsupported)
}
```

The verifier runs **per-claim in parallel.** For an answer with 5 claims and 1.5 citations per claim on average, that's ~7-8 verifier calls. With NIM's free-tier rate limits, these are throttled to a configurable max-concurrent. Typical latency overlap with generation: verifier finishes within 1-2s after generation completes.

**Action on verifier outputs:**

- All claims `supported` → render answer as-is
- Any claim `partially_supported` → render with a warning badge on that claim
- Any claim `unsupported` → strip the claim and the citation; show a UI note ("Some content was removed because citation verification failed"). In Phase A this happens ~5% of turns; the eval harness tracks the rate.

**Error mode:** On verifier timeout, mark claims as `no_check` and render with a UI indicator ("Citation verification is in progress").

#### Node 8 — Memory Update

**Purpose:** Update persistent conversation state for future turns.

**Inputs:** Full turn state.

**Outputs:** Updated `topic_summary`, `research_focus`, `accumulated_sources`.

**Strategy:** Three layers of memory:

1. **Working memory:** Last 5 turns, full text, passed directly into the next turn's prompts.
2. **Episodic summary:** A rolling summary of the conversation, updated every 5 turns by a small LLM call. ~200-word summary.
3. **Research focus extraction:** After turn 3, run a small LLM call to distill "what is the user actually researching?" — used by the retrieval router to bias future retrievals.

**Model — Phase A:** NIM Llama 3.1 8B (for summary and focus extraction).
**Model — Phase B:** Claude Haiku 4.5.

**Persistence:** Postgres via LangGraph checkpointer.

---

## 4. Retrieval Design

### 4.1 Retrieval taxonomy

The system supports a fixed set of retrieval strategies. Each is invoked by name from the retrieval plan.

| Strategy | When to use |
|---|---|
| `bm25_only` | Exact-citation lookups (case names, section numbers, patent numbers) |
| `dense_only` | Semantic exploration with no terminology constraints (rare in legal) |
| `hybrid` | Default — combine BM25 and dense via RRF |
| `hybrid_rerank` | Default for most queries — hybrid then cross-encoder rerank |
| `hyde` | Short or vague queries where the literal query terms are sparse |
| `decompose_then_retrieve` | Multi-part queries ("compare X across A, B, C") |
| `graph_expand` | Treatment / prior-art chains; seed with hybrid, expand via Neo4j |
| `adaptive` | Re-retrieve with a new query if initial reranker confidence is low |

### 4.2 Hybrid retrieval (the workhorse)

For each query, run in parallel:

- **Dense:** Qdrant vector search over the embedding of the query. Top 100 candidates.
- **Sparse / BM25:** Qdrant's native BM25 index. Top 100 candidates.

Fuse with **Reciprocal Rank Fusion (RRF)** with k=60:

```python
def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda x: -x[1])
```

Pass the top-50 fused candidates to the reranker.

**Why hybrid:** Dense finds semantic matches ("China exposure" ↔ "operations in the PRC"). Sparse catches exact legal terms that dense models often miss (section numbers, latin tags like *res judicata*, party names). On legal text, hybrid+RRF beats either alone by 8–15 percentage points on recall@10 in published benchmarks.

**Why RRF specifically:** Parameter-free, robust, no per-domain tuning. The k=60 default works.

### 4.3 Reranking

Top 50 fused candidates go to a cross-encoder reranker. The reranker scores each (query, chunk) pair jointly — far more accurate than the bi-encoder embeddings used for first-stage retrieval.

**Phase A:** Local BGE-reranker-v2-m3 (run via sentence-transformers on M1 with Metal acceleration), or NIM's NV-RerankQA-Mistral4B-v3.

**Phase B:** Cohere Rerank 3.

Output: top 5-10 chunks, passed to generation.

**Important:** The reranker's top-1 confidence score is monitored. If it's below a threshold (calibrated per query type during Phase 1), the system falls into `adaptive` mode and re-retrieves with a rewritten query.

### 4.4 HyDE (Hypothetical Document Embeddings)

For short or vague queries, the literal query terms may not match retrieval well. HyDE asks an LLM to write a hypothetical document that *would* answer the query, then embeds that hypothetical document for retrieval.

```python
async def hyde_retrieve(query: str, corpus: Corpus) -> list[RetrievedChunk]:
    # Generate hypothetical answer paragraph
    hyp = await llm.complete(
        prompt=f"Write a one-paragraph passage from a {corpus.name} document "
               f"that answers: {query}",
        max_tokens=200,
    )
    # Embed and retrieve against the hypothesis
    embedding = await embedder.embed(hyp)
    return await qdrant.search(corpus, embedding, top_k=50)
```

Use sparingly — adds ~600ms of LLM latency. Worth it for vague queries; not for specific lookups.

### 4.5 Query decomposition

For comparative or multi-part queries, decompose into atomic sub-queries.

Example: "Compare how Delhi and Bombay High Courts have ruled on Section 138 cheque bounce cases since 2020" decomposes to:

- "Delhi High Court Section 138 cheque bounce rulings since 2020"
- "Bombay High Court Section 138 cheque bounce rulings since 2020"

Each sub-query runs hybrid retrieval independently. Results are merged via RRF for joint reranking, or kept separate for per-jurisdiction presentation in the answer.

Decomposition is done by a small LLM call (`decompose.v1` prompt).

### 4.6 Graph expansion (treatment-aware retrieval)

For "is this case still good law?" or "how has this precedent been treated?" queries, the system uses Neo4j to traverse the citation graph.

Schema (full schema in Document 8):

```cypher
(:Case {id, name, citation, court, date})
    -[:CITES {
        intent: "background" | "follows" | "distinguishes" | "doubts" | "overrules",
        confidence: float
    }]->
(:Case)
```

Traversal pattern:

```cypher
// Find the seed case via hybrid retrieval first, then:
MATCH (seed:Case {id: $seed_id})
MATCH path = (seed)<-[:CITES*1..2]-(later:Case)
WHERE later.date > seed.date
RETURN later, [r in relationships(path) | r.intent] AS treatment_chain
ORDER BY later.date DESC
LIMIT 20
```

The orchestrator post-processes this to surface "this case has been **overruled** by X (2018)" or "this case has been **distinguished** by Y (2019)" prominently in the answer.

**Phase A reality check:** Neo4j Aura Free has 200K node and 400K relationship limits. For v1.0, this comfortably holds the Supreme Court citation graph (~30K cases with average 5-8 citations = ~200K edges); High Court citation graphs are deferred until Phase B or self-hosting.

### 4.7 Adaptive retrieval

If the reranker's top-1 score after first retrieval is below a calibrated threshold:

1. Run a small LLM call to rewrite the query in a different framing
2. Re-retrieve with the new query
3. Merge with the original retrieval via RRF
4. Rerank again

Maximum one retry to bound latency. The threshold is calibrated during Phase 1 by sweeping over the eval set and choosing the cutoff that maximizes recall@10 minus latency cost.

### 4.8 Metadata filtering

Every retrieval call carries optional filters:

```python
class RetrievalFilters(BaseModel):
    jurisdiction: str | None
    court: str | None  # "supreme_court", "delhi_hc", etc.
    date_range: DateRange | None
    statute: str | None  # restrict to chunks from a specific statute
    section: str | None  # restrict to a specific section
    cpc_classes: list[str] | None  # for patents
    assignee: str | None  # for patents
    chunk_type: list[ChunkType] | None  # e.g., only "claim" chunks for patents
    tier: list[int] | None  # restrict to certain tiers
```

Filters apply as Qdrant payload filters, narrowing the search space before vector or BM25 scoring. Critically: **`user_id` is a non-optional filter for any retrieval over user-uploaded documents.**

---

## 5. Chunking Strategy per Corpus

Chunking is where most legal RAG systems quietly fail. Different document types require different chunking rules. Generic 512-token windows lose structural meaning and break retrieval.

### 5.1 Statutes

**Unit of chunking:** One chunk per *section*, never split a section mid-sentence.

**Granularity rules:**

- For statutes with very long sections (e.g., the Companies Act section on related party transactions), split at subsection boundaries `(1)`, `(2)`, etc.
- Always include the section number, the statute name, and the section heading at the start of the chunk
- Defined terms (the "Definitions" section of a statute) are special: each defined term is its own chunk

**Metadata attached to every statute chunk:**

```python
class StatuteChunkMetadata(BaseModel):
    statute_id: str  # "ipc", "ni_act", "constitution"
    statute_name: str  # human-readable
    section: str  # "420", "138", "Article 14"
    subsection: str | None
    section_heading: str | None
    effective_from: date
    effective_to: date | None  # None if current
    amended_by: list[str]  # list of amendment act citations
    tier: int  # 1 for primary
    chunk_type: Literal["section", "definition", "schedule"]
    word_count: int
```

**Why effective dates matter:** A query "what does Section 377 say?" must produce different answers for "today" vs "before 2018." The retrieval filter sets the effective-date constraint based on intent.

### 5.2 Case law (judgments)

**Unit of chunking:** Structure-aware, by judgment component.

A judgment has identifiable parts: headnote, facts, issues, arguments, reasoning (often the longest), and operative order. Each becomes its own chunk type:

```python
class CaseChunkType(StrEnum):
    HEADNOTE = "headnote"
    FACTS = "facts"
    ISSUES = "issues"
    ARGUMENTS = "arguments"
    REASONING = "reasoning"  # the ratio
    HOLDING = "holding"  # the operative order
    DICTA = "dicta"  # asides
```

**Chunking rules:**

- Within `reasoning`, split by paragraph (judgments are numbered by paragraph)
- Each paragraph becomes a chunk; include the paragraph number in metadata
- Headnotes and holdings are denser; allow longer chunks (up to 800 tokens)
- The chunk text always includes the case name and paragraph number as a header

**Metadata:**

```python
class CaseChunkMetadata(BaseModel):
    case_id: str
    case_name: str
    citation: str  # "(2010) 7 SCC 263"
    court: str  # "supreme_court", "delhi_hc"
    date: date
    judges: list[str]
    chunk_type: CaseChunkType
    paragraph_number: int | None
    treatment_status: str  # "not_overruled" | "overruled_by:X" | "doubted" | etc.
    tier: int  # 1
    word_count: int
```

**The headnote chunk gets a retrieval boost.** Headnotes are concise summaries of the judgment, high signal per token. The reranker is configured to boost headnote chunks by a tunable factor (calibrated on the eval set).

### 5.3 Patents

**Unit of chunking:** Each independent claim is its own chunk. Each dependent claim is its own chunk, with a metadata reference to its parent.

**Why claims separately:** Patent claims are the legally operative content. A prior-art search hinges on claim-element matching. Embedding the entire specification as one chunk loses this.

The specification (background, summary, detailed description, drawings) is chunked by section:

```python
class PatentChunkType(StrEnum):
    ABSTRACT = "abstract"
    CLAIM_INDEPENDENT = "claim_independent"
    CLAIM_DEPENDENT = "claim_dependent"
    BACKGROUND = "background"
    SUMMARY = "summary"
    DETAILED_DESCRIPTION = "detailed_description"
    DRAWING_DESCRIPTION = "drawing_description"
```

**Metadata:**

```python
class PatentChunkMetadata(BaseModel):
    patent_id: str  # "US10765432B2"
    patent_office: str  # "USPTO", "EPO", "IPO"
    title: str
    chunk_type: PatentChunkType
    claim_number: int | None  # for claim chunks
    claim_dependency: str | None  # "independent" | "depends_on:1"
    cpc_codes: list[str]
    ipc_codes: list[str]
    assignee: str
    inventors: list[str]
    filing_date: date
    priority_date: date
    issue_date: date
    status: Literal["active", "expired", "abandoned"]
    forward_citation_count: int
    tier: int  # 1
```

**Status matters.** "Cite this active patent" vs "cite this expired patent for prior-art purposes" are very different. The generation prompt is aware of patent status.

### 5.4 User-uploaded documents

**Unit of chunking:** Document-type-aware.

The system detects the document type on upload using a small classifier:

- **Contract** → clause-by-clause chunking; each clause is a chunk; CUAD classifier runs to label each clause's type
- **Legal notice** → paragraph chunking; preserve the demand/allegation structure
- **Judgment** → same chunking as case law
- **Other** → structure-aware chunking via Unstructured.io defaults

**Per-clause metadata for contracts:**

```python
class ClauseChunkMetadata(BaseModel):
    document_id: str
    user_id: str  # mandatory for isolation
    session_id: str
    clause_index: int
    clause_type: str | None  # CUAD label: "Indemnification", "Termination", etc.
    risk_label: Literal["standard", "review", "high_risk"] | None
    detected_party_role: str | None  # "buyer", "seller", "licensor"
    tier: int  # 1 for the user's own document
```

### 5.5 Web sources (Tier 2 / 3 / 4)

**Unit of chunking:** Article section (where structure exists) or paragraph (where it doesn't).

Web sources are archived at retrieval time (HTML snapshot stored in R2). The chunk metadata includes:

```python
class WebChunkMetadata(BaseModel):
    url: str
    archived_url: str  # R2 path
    domain: str
    tier: Literal[2, 3, 4]
    published_date: date | None
    retrieved_date: date
    title: str
    chunk_type: Literal["article_section", "paragraph", "headline"]
```

**The archived snapshot is the canonical source for citations.** When the user clicks a web citation, they see the snapshot, not the live URL. This protects against citation rot.

---

## 6. Embedding Strategy

### 6.1 Embedding model selection

| Phase | Embedding model | Dimensions | Where |
|---|---|---|---|
| Phase A primary | BGE-M3 via FastEmbed (local on M1) | 1024 | Local M1 inference |
| Phase A alternative | NIM NV-EmbedQA-E5-v5 | 1024 | NIM API |
| Phase B | Voyage-law-2 or Voyage-3-large | 1024 | Voyage API |

BGE-M3 is the recommended Phase A default. It supports multilingual text (relevant for Indian legal mixing English with Hindi terms), is open-weight, runs on M1 at acceptable speed, and gives within 5–8% of paid embeddings on legal benchmarks.

### 6.2 Embedding strategy

- **Same model for queries and documents** (standard practice for bi-encoders)
- **Batched embedding at ingest time** (M1 can handle ~50-100 chunks/second in batches of 32)
- **Content-hash caching:** Don't re-embed chunks whose content hasn't changed. Cache in Postgres.
- **Int8 quantization on storage:** Qdrant supports int8 scalar quantization at indexing time. Reduces vector storage 4x with negligible recall impact. Critical for Phase A 1 GB tier.
- **Cosine similarity** as the distance metric

### 6.3 Re-embedding strategy

When does a chunk get re-embedded?

- **Source content changed:** new amendment to a statute, corrected text → new chunk hash, re-embed
- **Embedding model upgrade:** Phase A → Phase B migration requires re-embedding the entire corpus once. Estimated cost in Phase B: ~$120 one-time for Voyage.

---

## 7. Prompt Engineering

### 7.1 Prompt versioning

Every prompt is versioned with a stable name and a semantic version number. Versioned in code as Pydantic templates with explicit input schemas:

```python
class GuardPromptV1(PromptTemplate):
    name = "guard"
    version = "v1.2.0"
    inputs = ["raw_query", "mode", "topic_summary"]
    template = """..."""
```

Prompt versions are tagged in every Langfuse trace and stored in the model versions registry in Postgres. The eval harness can compare two prompt versions head-to-head on the golden set.

### 7.2 Prompt design conventions

The Themis Machina prompt library follows seven conventions:

1. **System prompt up top, user query at bottom.** Models attend most to the start and end; place rules and the query at those positions.
2. **Explicit structured output.** Always demand JSON matching a schema. Parse-and-validate every response.
3. **Few-shot examples for hard cases.** Particularly for the intent classifier and the verifier — 2–3 examples per class.
4. **Negative examples.** Show what *not* to do. Especially for the citation rules.
5. **Explicit "say so" instruction.** "If you don't know, say so explicitly." Models follow this when told.
6. **Mode awareness in every prompt.** The mode (Professional / Public / Patent) is passed and acted on.
7. **Concise system prompts.** Long system prompts dilute attention. Aim for under 800 tokens of system content.

### 7.3 Prompt categories

The full prompt library contains roughly 18 distinct prompts. Each lives in its own file under `prompts/`:

| Prompt | Purpose | Phase A model | Phase B model |
|---|---|---|---|
| `guard.v1` | Scope and refusal classification | Llama 3.1 8B | Haiku |
| `rewrite.v1` | Coreference resolution | Llama 3.1 8B | Haiku |
| `intent.v1` | Query intent classification | Llama 3.1 8B | Haiku |
| `decompose.v1` | Multi-query decomposition | Llama 3.1 8B | Haiku |
| `hyde.v1` | Hypothetical document for HyDE | Llama 3.1 8B | Haiku |
| `generate_statute.v1` | Statute Q&A generation | Llama 3.3 70B | Sonnet |
| `generate_case.v1` | Case-law generation | Llama 3.3 70B | Sonnet |
| `generate_interpretive.v1` | Interpretive synthesis | Llama 3.3 70B | Sonnet |
| `generate_patent.v1` | Patent Q&A generation | Llama 3.3 70B | Sonnet |
| `generate_prior_art.v1` | Prior-art structured output | Llama 3.3 70B | Sonnet |
| `generate_document.v1` | User document Q&A | Llama 3.3 70B | Sonnet |
| `verify.v1` | Citation verification | Llama 3.1 8B | Haiku |
| `refusal_advice.v1` | Advice refusal with referral | Llama 3.1 8B | Haiku |
| `clarify.v1` | Ask clarifying question | Llama 3.1 8B | Haiku |
| `summarize_turn.v1` | Update topic summary | Llama 3.1 8B | Haiku |
| `extract_focus.v1` | Distill research focus | Llama 3.1 8B | Haiku |
| `claim_decompose.v1` | Decompose patent claim into elements | Llama 3.3 70B | Sonnet |
| `element_coverage.v1` | NLI element-coverage check | Llama 3.1 8B | Haiku |

### 7.4 The citation discipline in prompts

The citation rules in `generate_*.v1` are the highest-stakes prompt content in the system. They appear identically in every generation prompt:

```
CITATION RULES (non-negotiable):

1. Every factual claim about the law, a case, a procedure, or a fact must
   be followed by one or more citation IDs in square brackets: [s1] or [s1,s3].

2. The only valid citation IDs are those provided in the Sources section
   above. Inventing a citation ID is a critical error.

3. A claim about "what the law says" or "the rule is X" must be backed by
   a Tier 1 source (statute or case law). Tier 2 (official secondary) and
   Tier 3 (curated commentary) sources may support contextual claims only.
   Tier 4 (general web) may never be the sole basis for a legal claim.

4. When you quote source text verbatim, use quotation marks AND attach the
   citation. When you paraphrase, no quotation marks but still attach the
   citation.

5. If the sources do not support a confident answer, say so explicitly.
   Do not fabricate a confident answer from weak sources.

6. If sources conflict, surface the conflict; do not silently pick one.
```

This block is the single most important prompt content in the system. Changes to it require a full eval re-run before merge.

---

## 8. Fine-Tuning Plans

### 8.1 What we fine-tune (and what we don't)

The Phase A philosophy is: fine-tune only when prompting can't reach acceptable quality, or when fine-tuning unlocks meaningful cost reduction.

We **fine-tune** three things:

- **CUAD clause classifier** (Phase 6) — clause type classification on contracts
- **Citation intent classifier** (optional, Phase 2 or later) — case-citation treatment
- **Distilled verifier** (Phase B candidate) — small model trained on Claude verifier labels

We **do not** fine-tune the primary generation model. Adapting Llama 3.3 70B for citation discipline is achievable through prompting + verification.

### 8.2 CUAD clause classifier

**Task:** Multi-label classification of contract clauses across 41 CUAD categories (Indemnification, Liability Cap, Change of Control, etc.).

**Data:** Contract Understanding Atticus Dataset (CUAD) — 510 contracts, 13K labeled clauses. Public domain.

**Base model:** `distilbert-base-uncased` or `legal-bert-base-uncased`.

**Setup:**

- Train on M1 via PyTorch with MPS (Metal Performance Shaders) backend
- Multi-label classification (sigmoid output per class)
- Class imbalance: weighted BCE loss, oversample rare classes
- Eval split: hold out 20% of contracts (not clauses) to prevent leakage

**Reported metrics in README:**

- Per-class precision/recall/F1
- Macro-F1 across all 41 classes
- Comparison against published CUAD baselines

**Target:** Macro-F1 > 0.75. Published baselines (RoBERTa-base, DeBERTa-v3-large) report 0.75–0.85.

**Output integration:** When a user uploads a contract, the classifier labels every chunk. Labels feed into the risk-flagging system and into clause-aware retrieval.

### 8.3 Citation intent / treatment classifier (optional)

**Task:** Given a sentence where Case B cites Case A, classify the intent: `follows`, `distinguishes`, `doubts`, `overrules`, `background`.

**Data:** Combine **SciCite-style** existing labels (~11K) with **synthetic labels** generated from a frontier model (Claude or DeepSeek V3) over high-impact citations in Indian SC judgments — then human-validate a 500-citation sample. The eval set is held out.

**Base model:** SciBERT or `legal-bert`.

**Why this is optional:** A well-prompted Phase A LLM can do this reasonably well without fine-tuning. Fine-tuning unlocks per-citation classification at thousands per second on M1, which matters only when building the full SC citation graph at scale. Recommended for Phase 2 if time permits; deferrable.

### 8.4 Distilled verifier (Phase B candidate)

A frontier-grade verifier (Claude Haiku) is expensive at scale. The distillation strategy:

1. Run Claude Haiku as verifier on 10K diverse (claim, source) pairs from production logs
2. Use Claude's verdicts as training labels
3. Fine-tune Phi-4 or Llama 3.2 3B on the labeled pairs
4. Deploy the distilled model as the verifier; reserve Claude for spot-checking

**Expected outcome:** ~95% agreement with Claude at 10× lower cost. This is a Phase B optimization, documented but deferred.

---

## 9. Model Selection Rationale

### 9.1 Why specific Phase A models

**Generation: Llama 3.3 70B Instruct (or Llama 4 Maverick).**
On the OpenAI-compatible NIM endpoint. The 70B-class Llama models are the strongest open-weight generation models on instruction-following and structured output as of 2026. Within 5–10% of Claude Sonnet on RAG-with-citations tasks per published benchmarks. The trade is acceptable for ₹0 cost.

**Routing / verification: Llama 3.1 8B.**
Strong enough for binary and few-class classification; ~3× faster than the 70B; comfortably handles structured output. Nemotron-mini is a reasonable alternative if NIM rate-limits the 8B.

**Embeddings: BGE-M3 local.**
Multilingual coverage relevant to Indian legal text. Runs locally on M1 — no rate limits, no quota, full control. Within 5–8% of Voyage on legal benchmarks. Importantly: embedding all corpus chunks happens once during ingest and is dominated by throughput, not per-call latency — exactly the case where local inference shines.

**Reranker: BGE-reranker-v2-m3 local.**
Same logic as embeddings. Cross-encoder rerankers are bottlenecked by per-pair scoring, which on a top-50 list is 50 inference calls per query. On M1 with batching, this completes in 500–800ms — acceptable.

### 9.2 Why specific Phase B models

**Generation: Claude Sonnet 4.**
Best-in-class citation grounding among frontier models. Lower hallucination rate on legal text. Reliable structured output. Worth the cost for production.

**Verification: Claude Haiku 4.5.**
Cheap, fast, accurate enough to act as the verifier. Same provider family as Sonnet, which simplifies billing and observability.

**Embeddings: Voyage-law-2.**
Domain-specialized for legal text. ~5–8% better recall on legal benchmarks vs general embeddings. The single highest-ROI Phase B swap for retrieval quality.

**Reranker: Cohere Rerank 3.**
Best general reranker available via API. Particularly strong on ambiguous queries.

### 9.3 Model swap mechanism

Every model is invoked via a typed interface:

```python
class LLMClient(Protocol):
    async def complete(
        self,
        prompt: Prompt,  # versioned prompt object
        max_tokens: int,
        temperature: float,
        response_format: type[BaseModel] | None,
        stream: bool,
    ) -> LLMResponse: ...

class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

class RerankerClient(Protocol):
    async def rerank(self, query: str, chunks: list[str]) -> list[float]: ...
```

Concrete implementations:

- `NIMLLMClient`, `OllamaLLMClient`, `AnthropicLLMClient` (all conform to `LLMClient`)
- `LocalBGEEmbeddingClient`, `NIMEmbeddingClient`, `VoyageEmbeddingClient`
- `LocalBGERerankerClient`, `NIMRerankerClient`, `CohereRerankerClient`

A configuration-driven factory selects the implementation at startup. The Phase A → Phase B swap is changing the config, nothing else.

---

## 10. Patent Pipeline Specifics

### 10.1 Patent ingestion

USPTO data is XML (RedBook DTD). Parsing follows the standard pattern: extract title, abstract, claims (preserving structure), description sections, classifications, metadata. Each claim becomes a chunk; each spec section becomes a chunk; each retains rich metadata.

Ingest batches are large — even one CPC subclass may be 50K-100K patents. Strategy:

- Parallel parsing across CPU cores
- Batched embedding (M1 throughput limits)
- Bulk Qdrant ingestion in chunks of 1000 points
- Estimate: ~6 hours to ingest 100K patents on M1 with quantization

### 10.2 Prior-art search pipeline

The core differentiated feature. Given a patent claim:

1. **Decompose** the claim into elements via `claim_decompose.v1` prompt
2. **Retrieve** candidates for each element separately (multi-query, parallel hybrid search)
3. **For each candidate**, run `element_coverage.v1` — an NLI prompt: "Does this prior art document teach this element?"
4. **Score per-element coverage** across all candidates
5. **Report**: per-element best matches, overall novelty score, gaps

The output is a structured prior-art report:

```python
class PriorArtReport(BaseModel):
    claim_text: str
    elements: list[ClaimElement]  # decomposed
    candidates: list[PriorArtCandidate]
    coverage_matrix: list[list[Coverage]]  # elements × candidates
    novelty_assessment: NoveltyAssessment  # "likely novel" / "possibly anticipated" / "anticipated"
    caveats: list[str]
```

This is *not* a freedom-to-operate opinion. The output explicitly states it as a research aid; the README and UI reinforce this.

---

## 11. Themis Documents Specifics

### 11.1 Document type detection

On upload, a small classifier identifies the document type:

- Contract (commercial agreement)
- Legal notice (statutory notices, demand letters)
- Judgment (court order)
- Statute extract or government notification
- Other

Detection uses a few-shot LLM classifier on the first 1000 tokens of the parsed document.

### 11.2 Contract analysis

For contracts:

1. Clause segmentation (rule-based on standard contract markers, refined by LLM for edge cases)
2. Per-clause CUAD classification (the fine-tuned model from §8.2)
3. Per-clause risk label using a structured prompt that considers the user's stated role (buyer/seller/licensee)
4. Indexing into the per-user Qdrant collection with full clause metadata

The user can ask:

- "What does my contract say about termination?"
- "Are there any unusual clauses?"
- "What's the indemnification cap?"
- "Compare the termination clause to typical commercial contract norms"

For the last query, the system retrieves both from the user's contract and from the public corpus, with clear citation tier labels.

### 11.3 Cross-corpus retrieval (user doc + public)

When a query spans user documents and the public corpus, the retrieval router schedules two parallel retrievals:

- One against the user's Qdrant collection
- One against the public corpus

Results are merged for joint reranking. Citation rendering distinguishes "your document" from public sources clearly.

---

## 12. Continuous Improvement

### 12.1 Active learning loop

User feedback (thumbs up/down on every answer, optional free-text comment) flows into Postgres. A weekly review process:

1. Pull the 20 most thumbs-down answers from the past week
2. Categorize: retrieval miss, generation error, verification failure, scope refusal that should have been an answer, advice that should have been a refusal, other
3. For retrieval misses: add the (question, missed_chunk) to the eval set
4. For generation errors: review the prompt; consider a version bump
5. For verification failures: review the verifier prompt
6. For scope misclassifications: add to the guard's few-shot examples

The eval set grows from ~200 questions at launch to ~500 over six months.

### 12.2 Prompt A/B testing

When a prompt version is bumped (e.g., `generate.v1` → `generate.v2`), the eval harness runs both versions head-to-head on the golden set and reports:

- Per-metric difference (faithfulness, citation accuracy, etc.)
- Per-query category difference
- Latency and cost difference

A new prompt version ships only if it's measurably better, with the eval report attached to the merge PR.

### 12.3 Retrieval calibration

Two retrieval parameters are calibrated by sweep on the eval set:

- **Reranker confidence threshold** for triggering adaptive retrieval
- **RRF k** (default 60, sometimes worth tuning per corpus)

These are revisited after every major corpus expansion (Phase 2, Phase 6, Phase 7).

### 12.4 Model upgrade evaluation

When a new model is released (e.g., a new Llama version on NIM, or Claude updates in Phase B), the same head-to-head eval methodology applies. The model is swapped in via LiteLLM config, the full eval set runs, and the new model ships only if measurably better.

---

## 13. Failure Modes and Mitigation

| Failure mode | Detection | Mitigation |
|---|---|---|
| Hallucinated citation reaches user | Verifier flags it pre-render | Strip claim and citation; UI shows "removed: unverified citation" |
| Retrieval returns nothing relevant | Reranker top score below threshold | Adaptive re-retrieval; if still empty, system says "I couldn't find authoritative sources for this" |
| LLM produces invalid structured output | Pydantic validation fails | Single retry with stricter prompt; on second failure, user-friendly error |
| NIM rate-limit hit mid-conversation | HTTP 429 from NIM | Automatic fallback to Ollama for the current turn; log incident |
| Ollama unavailable | Connection error | Hard failure; show maintenance message |
| Qdrant 1 GB tier exceeded | Storage metric crosses 95% | Block new ingest; alert; advance to Phase B early or spill cases to self-hosted Qdrant |
| Prompt injection in retrieved web content | Pre-LLM sanitization pass + post-LLM tool-call detector | Reject the chunk; log incident; trigger red-team eval |
| Conversation state corruption | LangGraph checkpointer error | Reload from last good checkpoint; if none, start fresh with a "conversation reset" message |

---

## 14. Open AI/ML Questions

| # | Question | Resolution deadline |
|---|---|---|
| 1 | BGE-M3 vs NIM NV-EmbedQA-E5 — benchmark on 100-question set | Phase 1 |
| 2 | Best Llama variant available on NIM at Phase 1 start | Phase 1 |
| 3 | Whether to fine-tune the citation intent classifier in Phase 2 or defer | Phase 2 |
| 4 | Reranker confidence threshold for adaptive trigger | Phase 4 |
| 5 | RRF k tuning per corpus | Phase 4 |
| 6 | Whether to ship Phase 7 with USPTO-only or include EPO from the start | Phase 7 |

---

## 15. Approval

| Role | Name | Date | Status |
|---|---|---|---|
| AI/ML lead | [Your name] | [Date] | Approved for build |

---

## 16. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | [Date] | [You] | Approved baseline |

---

## 17. Related Documents

- **Document 1** — PRD
- **Document 2** — TRD (system-level engineering)
- **Document 4** — App Flow & User Journey
- **Document 6** — Evaluation Plan (eval methodology in depth)
- **Document 7** — Safety & Responsible AI
- **Document 8** — Data Architecture (schemas)
- **Document 9** — API Specification

— end of Document 3 —
