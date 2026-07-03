# Data Architecture Document

**Project:** Themis Machina
**Assistant:** Themis GPT
**Document:** 8 of 13
**Version:** 1.0
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## 1. Purpose and Scope

This document defines the complete data architecture of Themis Machina: every schema, every data store, how data flows between stores, how it is versioned, how it ages out, and the design decisions that shape it.

It is the source of truth for data engineering. Application code, migrations, and ingestion pipelines all derive from this document.

The document covers five stores: **Postgres** (relational state), **Qdrant** (vector store), **Neo4j** (citation graph), **Redis** (cache and queue), and **Cloudflare R2** (object storage). For each store it specifies: schema, indexing, retention, and Phase A constraints (free-tier limits).

---

## 2. Data Design Principles

Six principles shape every data decision:

1. **User data never crosses user boundaries.** Every schema that holds user-specific data has `user_id` as a mandatory column or collection key, enforced at the storage layer.
2. **Provenance is permanent.** Every chunk, every citation, every eval result traces back to its origin source with enough metadata to reproduce the retrieval.
3. **Effective dates are first-class.** Legal data has temporal validity. Every statute chunk and case-treatment edge carries `effective_from` and `effective_to`.
4. **Idempotent writes.** Ingest pipelines can be re-run safely. Chunk IDs are derived from content hashes; inserting the same chunk twice is a no-op.
5. **Free-tier discipline.** Phase A fits within Qdrant Cloud 1 GB, Neo4j Aura Free 200K nodes, and Neon 0.5 GB with specific techniques (quantization, selective indexing, lean schemas).
6. **Schema migrations are versioned.** Every schema change is a numbered Alembic migration. No schema change ships without a migration that can be rolled back.

---

## 3. Postgres Schema (Neon, Phase A)

Postgres holds all relational state: user accounts, sessions, conversations, matters, audit logs, eval data, and prompt versions. Phase A uses Neon's free tier (0.5 GB). With lean schemas and aggressive use of Postgres's compression, the full v1.0 relational state fits comfortably within this limit.

### 3.1 Users and accounts

```sql
-- Core user record
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    display_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'public_user'
        CHECK (role IN ('anonymous', 'public_user', 'professional_user', 'admin')),
    professional_verified BOOLEAN DEFAULT FALSE,
    professional_verified_at TIMESTAMPTZ,
    bar_council_number VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ  -- soft delete; hard delete runs 30 days after this
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- OAuth provider links
CREATE TABLE oauth_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- 'google', 'microsoft', 'apple'
    provider_account_id VARCHAR(255) NOT NULL,
    provider_email VARCHAR(320),
    access_token_hash VARCHAR(64),  -- hashed, not stored plaintext
    refresh_token_hash VARCHAR(64),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, provider_account_id)
);

-- Anonymous sessions (no user account)
CREATE TABLE anonymous_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token_hash VARCHAR(64) UNIQUE NOT NULL,
    ip_hash VARCHAR(64),  -- hashed IP for rate limiting only
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days'
);

CREATE INDEX idx_anon_sessions_token ON anonymous_sessions(session_token_hash);
CREATE INDEX idx_anon_sessions_expires ON anonymous_sessions(expires_at);
```

### 3.2 Research matters and conversations

```sql
-- A named research matter (groups conversations)
CREATE TABLE matters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(500),
    tags TEXT[],
    archived BOOLEAN DEFAULT FALSE,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_matters_user ON matters(user_id, archived, updated_at DESC);

-- A conversation (one or more turns)
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,  -- NULL for anonymous sessions
    anonymous_session_id UUID,  -- NULL for authenticated users
    matter_id UUID REFERENCES matters(id) ON DELETE SET NULL,
    mode VARCHAR(50) DEFAULT 'public'
        CHECK (mode IN ('public', 'professional', 'patent')),
    title VARCHAR(500),  -- auto-generated from topic summary
    turn_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,

    -- Ensure exactly one of user_id or anonymous_session_id is set
    CONSTRAINT conversation_owner CHECK (
        (user_id IS NOT NULL AND anonymous_session_id IS NULL) OR
        (user_id IS NULL AND anonymous_session_id IS NOT NULL)
    )
);

CREATE INDEX idx_conversations_user ON conversations(user_id, deleted_at, updated_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_conversations_session ON conversations(anonymous_session_id);
CREATE INDEX idx_conversations_matter ON conversations(matter_id);

-- Individual messages within a conversation
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_index INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    -- For assistant messages, structured fields:
    structured_answer JSONB,  -- the StructuredAnswer object (claims, citations, caveats)
    retrieved_chunk_ids TEXT[],  -- IDs of chunks retrieved this turn
    model_version VARCHAR(100),
    prompt_version VARCHAR(100),
    generation_latency_ms INTEGER,
    total_latency_ms INTEGER,
    faithfulness_score FLOAT,  -- set post-eval if this message was in an eval run
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(conversation_id, turn_index)
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, turn_index);
```

### 3.3 LangGraph checkpointer

LangGraph uses Postgres as its checkpointer backend. The built-in LangGraph Postgres checkpointer creates its own tables. We reserve the schema `langgraph`:

```sql
-- LangGraph manages these tables; reproduced here for documentation only
-- langgraph.checkpoints
-- langgraph.checkpoint_blobs
-- langgraph.checkpoint_writes
```

The `conversation_id` is used as LangGraph's `thread_id`. Each conversation has exactly one LangGraph thread.

### 3.4 User documents

```sql
-- Record of a user-uploaded document
CREATE TABLE user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    matter_id UUID REFERENCES matters(id) ON DELETE SET NULL,
    original_filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    size_bytes INTEGER NOT NULL,
    r2_key VARCHAR(1000) NOT NULL UNIQUE,  -- path in Cloudflare R2
    parse_status VARCHAR(50) DEFAULT 'pending'
        CHECK (parse_status IN ('pending', 'parsing', 'ready', 'failed')),
    document_type VARCHAR(100),  -- 'contract', 'notice', 'judgment', 'other'
    page_count INTEGER,
    chunk_count INTEGER,
    qdrant_collection VARCHAR(255),  -- user_{user_id}_session_{session_id}
    clause_analysis JSONB,  -- CUAD labels, risk flags (for contracts)
    ocr_required BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    scoped_to VARCHAR(50) DEFAULT 'session'
        CHECK (scoped_to IN ('session', 'matter', 'permanent')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- NULL for matter-scoped; set for session-scoped
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_user_docs_user ON user_documents(user_id, deleted_at)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_user_docs_conversation ON user_documents(conversation_id);
CREATE INDEX idx_user_docs_expires ON user_documents(expires_at)
    WHERE expires_at IS NOT NULL AND deleted_at IS NULL;
```

### 3.5 Corpus provenance

```sql
-- Every ingested chunk traces back to a source file
CREATE TABLE corpus_sources (
    id VARCHAR(255) PRIMARY KEY,  -- e.g., 'ipc_s420', 'case_smt_selvi_2010'
    source_type VARCHAR(50) NOT NULL
        CHECK (source_type IN ('statute', 'case_law', 'patent', 'regulation', 'commentary')),
    jurisdiction VARCHAR(100),
    title VARCHAR(1000),
    citation VARCHAR(500),
    effective_from DATE,
    effective_to DATE,
    r2_key VARCHAR(1000),  -- original file in R2
    parsed_r2_key VARCHAR(1000),  -- parsed JSON in R2
    chunk_count INTEGER DEFAULT 0,
    ingest_status VARCHAR(50) DEFAULT 'pending',
    last_ingested_at TIMESTAMPTZ,
    content_hash VARCHAR(64),  -- SHA-256 of original file; for deduplication
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_corpus_sources_type ON corpus_sources(source_type, jurisdiction);
CREATE INDEX idx_corpus_sources_hash ON corpus_sources(content_hash);

-- Every chunk's provenance
CREATE TABLE corpus_chunks (
    id VARCHAR(255) PRIMARY KEY,  -- stable ID derived from (source_id + char_offset)
    source_id VARCHAR(255) NOT NULL REFERENCES corpus_sources(id),
    chunk_type VARCHAR(100) NOT NULL,  -- 'section', 'holding', 'claim_independent', etc.
    char_start INTEGER,
    char_end INTEGER,
    word_count INTEGER,
    tier INTEGER NOT NULL DEFAULT 1,
    qdrant_id UUID,  -- the corresponding point ID in Qdrant
    embedding_model VARCHAR(100),  -- which model was used to embed this chunk
    content_hash VARCHAR(64),  -- SHA-256 of chunk text; for dedup
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- Additional metadata stored as JSONB for flexibility
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_chunks_source ON corpus_chunks(source_id);
CREATE INDEX idx_chunks_type ON corpus_chunks(chunk_type);
CREATE INDEX idx_chunks_hash ON corpus_chunks(content_hash);
```

### 3.6 Evaluation data

```sql
-- The golden eval set
CREATE TABLE eval_questions (
    id VARCHAR(100) PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    difficulty VARCHAR(50),
    question TEXT NOT NULL,
    gold_answer_summary TEXT,
    required_sources JSONB,
    required_elements JSONB,
    acceptable_variations JSONB,
    unacceptable_content JSONB,
    mode VARCHAR(50) DEFAULT 'both',
    jurisdiction_filter VARCHAR(100),
    is_fast_set BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    added_from VARCHAR(100),  -- 'initial', 'active_learning', 'regression'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Individual eval runs
CREATE TABLE eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger VARCHAR(100) NOT NULL,  -- 'pr', 'nightly', 'release', 'manual'
    pr_number INTEGER,
    git_sha VARCHAR(40),
    prompt_versions JSONB,  -- snapshot of all prompt versions used
    model_versions JSONB,   -- snapshot of all model choices
    question_count INTEGER,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'running',

    -- Aggregate metric scores
    faithfulness FLOAT,
    citation_accuracy FLOAT,
    answer_correctness FLOAT,
    recall_at_5_statutes FLOAT,
    recall_at_10_statutes FLOAT,
    recall_at_5_cases FLOAT,
    recall_at_10_cases FLOAT,
    context_precision FLOAT,
    context_recall FLOAT,
    refusal_precision FLOAT,
    false_refusal_rate FLOAT,
    hallucinated_citation_rate FLOAT,
    latency_p50_ms FLOAT,
    latency_p95_ms FLOAT,

    regression_detected BOOLEAN DEFAULT FALSE,
    regression_details JSONB
);

-- Per-question results within a run
CREATE TABLE eval_question_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    question_id VARCHAR(100) NOT NULL REFERENCES eval_questions(id),
    generated_answer TEXT,
    retrieved_chunk_ids TEXT[],
    citations JSONB,
    faithfulness_score FLOAT,
    answer_correctness_score FLOAT,
    citation_accuracy_score FLOAT,
    recall_hit_at_5 BOOLEAN,
    recall_hit_at_10 BOOLEAN,
    refusal_correct BOOLEAN,
    failure_type VARCHAR(100),  -- from failure taxonomy in Document 6
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_eval_results_run ON eval_question_results(run_id);
CREATE INDEX idx_eval_results_question ON eval_question_results(question_id);

-- User feedback (thumbs up/down)
CREATE TABLE answer_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID,
    message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    turn_index INTEGER,
    question_text TEXT,
    feedback VARCHAR(20) CHECK (feedback IN ('positive', 'negative')),
    comment TEXT,
    mode VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed BOOLEAN DEFAULT FALSE,
    eval_question_id VARCHAR(100) REFERENCES eval_questions(id)
);
```

### 3.7 Prompt and model versioning

```sql
-- The prompt library
CREATE TABLE prompt_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_name VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    template TEXT NOT NULL,
    input_schema JSONB,
    model_target VARCHAR(100),  -- which model this prompt is designed for
    phase VARCHAR(10),  -- 'A' or 'B'
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deprecated_at TIMESTAMPTZ,
    notes TEXT,
    UNIQUE(prompt_name, version)
);

-- Model registry
CREATE TABLE model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role VARCHAR(100) NOT NULL,  -- 'primary_llm', 'fast_llm', 'embedder', 'reranker'
    provider VARCHAR(100) NOT NULL,  -- 'nvidia_nim', 'ollama', 'anthropic', etc.
    model_name VARCHAR(200) NOT NULL,
    phase VARCHAR(10),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deprecated_at TIMESTAMPTZ,
    notes TEXT
);

-- Audit log
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id UUID,
    anonymous_session_id UUID,
    conversation_id UUID,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    event_data JSONB,
    ip_hash VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Partition by month for efficient aging
CREATE TABLE audit_log_2024_01 PARTITION OF audit_log
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- (additional partitions created by migration as months pass)

CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_log_event ON audit_log(event_type, created_at DESC);
```

### 3.8 Postgres capacity planning for Phase A

With Neon's free 0.5 GB, the distribution estimate:

| Table | Estimated rows | Estimated size |
|---|---|---|
| users | 100 (demo traffic) | < 1 MB |
| conversations | 500 | < 5 MB |
| messages | 5,000 | ~50 MB |
| corpus_sources | 5,000 | ~10 MB |
| corpus_chunks | 200,000 | ~100 MB |
| eval_questions | 200 | < 1 MB |
| eval_runs | 100 | ~5 MB |
| eval_question_results | 20,000 | ~50 MB |
| LangGraph checkpoints | 500 threads | ~30 MB |
| audit_log | 50,000 | ~50 MB |
| **Total** | | **~302 MB** |

Well within the 0.5 GB Neon free limit. Phase B growth (larger corpus, more users) triggers Neon Pro.

---

## 4. Qdrant Schema (Vector Store)

Qdrant holds all embeddings and powers both dense (vector similarity) and sparse (BM25) retrieval. Phase A uses the free 1 GB Qdrant Cloud cluster.

### 4.1 Collection design

One collection per corpus type, plus per-user collections for uploaded documents:

| Collection | Content | Approximate size (Phase A) |
|---|---|---|
| `corpus_statutes` | Indian statutes (~50 priority acts) | ~200K chunks, ~600 MB with int8 quantization |
| `corpus_cases_sc` | Supreme Court judgments (subset) | ~500K chunks, ~350 MB with int8 quantization |
| `corpus_cases_hc_*` | High Court judgments (per court) | Deferred to Phase B if free tier exceeded |
| `corpus_patents` | USPTO patents (one CPC subclass) | Deferred to Phase 7, self-hosted if needed |
| `corpus_web_tier2` | Archived official web sources | ~10K chunks, ~30 MB |
| `corpus_web_tier3` | Archived curated commentary | ~20K chunks, ~60 MB |
| `user_{user_id}_session_{session_id}` | Per-user uploaded doc chunks | Variable; deleted on session expiry |

**Total Phase A estimate:** ~1.04 GB with int8 quantization. This is tight against the 1 GB limit. Mitigations:
- Start with a subset of SC cases (~5K most-cited leading cases) rather than all 30K
- Apply aggressive int8 scalar quantization
- Overflow to self-hosted Qdrant on Oracle Free VM if needed

### 4.2 Vector configuration per collection

All collections share the same embedding dimensionality but with quantization for storage efficiency:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, ScalarQuantizationConfig,
    ScalarType, BM25Config, SparseVectorParams
)

client.create_collection(
    collection_name="corpus_statutes",
    vectors_config=VectorParams(
        size=1024,
        distance=Distance.COSINE,
        on_disk=False,  # keep in memory for speed on free tier
    ),
    # Int8 quantization: 4x storage reduction, negligible quality loss
    quantization_config=ScalarQuantizationConfig(
        type=ScalarType.INT8,
        quantile=0.99,
        always_ram=True,
    ),
    # Sparse vectors for BM25
    sparse_vectors_config={
        "bm25": SparseVectorParams(
            modifier=models.Modifier.IDF,
        )
    },
)
```

### 4.3 Payload schema per collection

**Statute collection payload:**

```python
class StatutePayload(BaseModel):
    chunk_id: str          # references corpus_chunks.id
    source_id: str         # references corpus_sources.id
    statute_name: str
    statute_short: str     # "IPC", "NI_Act", "Constitution"
    section: str           # "420", "138", "Article_21"
    subsection: str | None
    section_heading: str | None
    effective_from: str    # ISO date string for filter
    effective_to: str | None
    tier: int              # always 1 for statutes
    chunk_type: str        # "section", "definition", "schedule"
    word_count: int
    text: str              # the chunk text (needed for BM25 and display)
```

**Case law collection payload:**

```python
class CaseLawPayload(BaseModel):
    chunk_id: str
    source_id: str
    case_name: str
    citation: str          # "(2010) 7 SCC 263"
    court: str             # "supreme_court", "delhi_hc"
    date: str              # "2010-05-01" for filter
    chunk_type: str        # "headnote", "reasoning", "holding", etc.
    paragraph_number: int | None
    treatment_status: str  # "not_overruled", "overruled_by:X", "doubted_by:Y"
    tier: int              # 1
    word_count: int
    text: str
    judges: list[str]
```

**Patent collection payload:**

```python
class PatentPayload(BaseModel):
    chunk_id: str
    source_id: str
    patent_id: str         # "US10765432B2"
    patent_office: str     # "USPTO", "EPO", "IPO"
    chunk_type: str        # "abstract", "claim_independent", "claim_dependent", etc.
    claim_number: int | None
    claim_dependency: str | None  # "independent" or "depends_on:1"
    cpc_codes: list[str]
    assignee: str
    priority_date: str
    status: str            # "active", "expired", "abandoned"
    forward_citation_count: int
    tier: int              # 1
    word_count: int
    text: str
```

**User document collection payload:**

```python
class UserDocPayload(BaseModel):
    chunk_id: str
    user_id: str           # MANDATORY - enforced at application layer
    document_id: str       # references user_documents.id
    document_type: str     # "contract", "notice", "judgment", "other"
    chunk_type: str        # "clause", "paragraph", "section"
    clause_index: int | None
    cuad_label: str | None
    risk_label: str | None  # "standard", "review", "high_risk"
    tier: int              # 1 (user's own document is treated as primary)
    word_count: int
    text: str
```

### 4.4 Indexing strategy

All collections use HNSW indexing for approximate nearest neighbour search:

```python
from qdrant_client.models import HnswConfigDiff

# HNSW config for statute collection (smaller, can afford higher quality)
hnsw_config = HnswConfigDiff(
    m=32,             # number of connections per node (higher = better recall, more memory)
    ef_construct=200, # construction time quality (higher = slower build, better recall)
    full_scan_threshold=10000,  # below this, brute-force; above, HNSW
)
```

BM25 indexing uses Qdrant's built-in sparse vector index.

### 4.5 Filtering strategy

Qdrant supports filtered searches via payload conditions. Common filter patterns:

```python
# Statute: find current version only
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue

current_statute_filter = Filter(
    must=[
        FieldCondition(key="tier", match=MatchValue(value=1)),
        FieldCondition(key="effective_to", is_null=True),  # no end date = still current
    ]
)

# Case law: find SC cases after 2010
sc_post_2010_filter = Filter(
    must=[
        FieldCondition(key="court", match=MatchValue(value="supreme_court")),
        FieldCondition(key="date", range=Range(gte="2010-01-01")),
    ]
)

# User document: MANDATORY user scope
user_doc_filter = Filter(
    must=[
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        FieldCondition(key="document_id", match=MatchValue(value=document_id)),
    ]
)
```

---

## 5. Neo4j Schema (Citation Graph)

Neo4j holds the legal citation graph: cases citing cases with treatment labels, and the patent citation network. Phase A uses Neo4j Aura Free (200K nodes, 400K relationships).

### 5.1 Node types

```cypher
// Case node
(:Case {
    id: String,           // stable ID, e.g., "case_smt_selvi_2010"
    name: String,         // "Smt. Selvi v. State of Karnataka"
    citation: String,     // "(2010) 7 SCC 263"
    court: String,        // "supreme_court"
    date: Date,           // 2010-05-05
    year: Integer,        // 2010
    judges: [String],     // ["K.G. Balakrishnan CJ", "R.V. Raveendran J", ...]
    bench_size: Integer,  // 3 (Division Bench), 5 (Constitution Bench), etc.
    treatment_summary: String  // "not_overruled" | "overruled" | "doubted" | "affirmed"
})

// Statute node
(:Statute {
    id: String,           // "ipc_s420"
    name: String,         // "Indian Penal Code, 1860 - Section 420"
    act_short: String,    // "IPC"
    section: String,      // "420"
    effective_from: Date,
    effective_to: Date    // null if currently in force
})

// Court node (for aggregation queries)
(:Court {
    id: String,           // "supreme_court"
    name: String,         // "Supreme Court of India"
    level: String         // "apex", "high_court", "tribunal"
})

// Patent node
(:Patent {
    id: String,           // "US10765432B2"
    patent_office: String,
    title: String,
    assignee: String,
    priority_date: Date,
    status: String        // "active", "expired", "abandoned"
})

// Author/Judge node
(:Person {
    id: String,
    name: String,
    role: String          // "judge", "inventor", "assignee_person"
})
```

### 5.2 Relationship types

```cypher
// Core legal citation relationships
(:Case)-[:CITES {
    intent: String,       // "background" | "follows" | "distinguishes" | "doubts" | "overrules"
    confidence: Float,    // 0.0-1.0 (classifier confidence)
    paragraph_number: Integer | null,
    citation_text: String // the verbatim citation context (short)
}]->(:Case)

(:Case)-[:INTERPRETS {
    section: String,
    paragraph_number: Integer
}]->(:Statute)

(:Case)-[:DECIDED_BY]->(:Court)
(:Case)-[:AUTHORED_BY]->(:Person)  // presiding/leading judge

// Patent citation relationships
(:Patent)-[:CITES_PATENT {
    citation_type: String  // "backward" (this patent cites it)
}]->(:Patent)

(:Patent)-[:CITES_NPL {
    doi: String | null,
    title: String
}]->(:PatentNPL)  // non-patent literature node

// Person relationships
(:Person)-[:SERVED_ON]->(:Court)
```

### 5.3 Key Cypher queries

**Treatment chain for a case:**

```cypher
MATCH (seed:Case {id: $seed_id})
MATCH path = (seed)<-[r:CITES*1..3]-(later:Case)
WHERE later.date > seed.date
RETURN later.name, later.citation, later.date,
       [rel in relationships(path) | rel.intent] AS treatment_chain
ORDER BY later.date DESC
LIMIT 30
```

**Find all cases that have overruled X:**

```cypher
MATCH (seed:Case {id: $seed_id})<-[r:CITES {intent: "overrules"}]-(overruler:Case)
RETURN overruler.name, overruler.citation, overruler.date, r.paragraph_number
```

**How has a statute section been interpreted over time?**

```cypher
MATCH (s:Statute {id: $statute_id})<-[r:INTERPRETS]-(c:Case)
RETURN c.name, c.citation, c.date, r.section, r.paragraph_number
ORDER BY c.date ASC
```

**Patent forward citations:**

```cypher
MATCH (p:Patent {id: $patent_id})<-[:CITES_PATENT]-(later:Patent)
RETURN later.id, later.title, later.assignee, later.priority_date
ORDER BY later.priority_date DESC
LIMIT 20
```

### 5.4 Neo4j Aura Free capacity planning

For Phase A (SC judgments only, subset of ~5K leading cases):

| Node type | Count | Relationships |
|---|---|---|
| Case | 5,000 | — |
| Statute | 1,000 | — |
| Court | 20 | — |
| Person | 500 | — |
| CITES edges (avg 5 per case) | — | 25,000 |
| INTERPRETS edges (avg 3 per case) | — | 15,000 |
| DECIDED_BY edges | — | 5,000 |
| **Total** | ~6,520 nodes | ~45,000 edges |

Well within Aura Free limits (200K nodes, 400K relationships). The full 30K SC judgment graph (~150K nodes, ~250K edges) still fits within Aura Free limits — the limit becomes relevant when adding High Courts.

---

## 6. Redis Schema (Upstash, Phase A)

Redis holds volatile state: cache, session tokens, rate-limit counters, and the Celery broker queue. Phase A uses Upstash Redis free tier (256 MB, 10K commands/day).

### 6.1 Key namespace design

All keys follow the pattern `{namespace}:{sub-key}`. Namespaces:

| Namespace | Pattern | TTL | Purpose |
|---|---|---|---|
| `embed_cache` | `embed_cache:{content_hash}` | No TTL | Embedding cache (content-addressed) |
| `retrieval_cache` | `retrieval_cache:{query_hash}` | 15 min | Retrieval result cache |
| `rate_limit` | `rate_limit:{user_id_or_ip}:{window}` | 1 hour | Sliding window rate limit |
| `session` | `session:{token_hash}` | 7 days | Anonymous session validation |
| `doc_status` | `doc_status:{doc_id}` | 24 hours | Document upload progress |
| `celery` | `celery:*` | Managed by Celery | Task queue |

### 6.2 Embedding cache

```python
# Key: embed_cache:{sha256(text)[:16]}
# Value: JSON-serialized list of floats (the embedding vector)
# TTL: none (embeddings are deterministic for a given text + model)

async def get_cached_embedding(text: str, model: str) -> list[float] | None:
    key = f"embed_cache:{model[:8]}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    return None

async def set_cached_embedding(text: str, model: str, embedding: list[float]) -> None:
    key = f"embed_cache:{model[:8]}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    # Store as compact float16 to save space
    await redis.set(key, json.dumps(embedding))
```

### 6.3 Rate limiting

Sliding window rate limiter using Redis sorted sets:

```python
async def check_rate_limit(
    identifier: str,  # user_id or ip_hash
    limit: int,       # max requests
    window_seconds: int = 3600
) -> tuple[bool, int]:  # (allowed, remaining)
    now = time.time()
    window_start = now - window_seconds
    key = f"rate_limit:{identifier}:{window_seconds}"

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)   # remove old requests
    pipe.zadd(key, {str(now): now})               # add current request
    pipe.zcard(key)                               # count in window
    pipe.expire(key, window_seconds)
    results = await pipe.execute()

    count = results[2]
    allowed = count <= limit
    remaining = max(0, limit - count)
    return allowed, remaining
```

### 6.4 Upstash capacity planning

256 MB and 10K commands/day. Main consumers:

- Embedding cache: ~10K cached embeddings × ~8 KB average = ~80 MB
- Retrieval cache: ~1K cached results × ~50 KB average = ~50 MB
- Rate limiting: minimal (sorted sets with short TTLs)
- Celery broker: small (queue overhead)

Total estimate: ~130-150 MB — within the 256 MB limit for portfolio traffic. If free-tier limits are hit, fall back to Postgres-backed caching for lower-priority entries.

---

## 7. Cloudflare R2 Object Storage

R2 holds binary objects: original source files, parsed JSON intermediates, user-uploaded documents, and web page archives. Phase A uses the R2 free tier (10 GB, 1M Class A operations/month).

### 7.1 Key namespace design

```
r2://themis-machina/
    corpus/
        raw/
            statutes/
                india_code/{statute_id}/current.pdf
                india_code/{statute_id}/v2018.pdf
            cases/
                sc/{year}/{case_id}.pdf
                delhi_hc/{year}/{case_id}.pdf
            patents/
                uspto/{year}/{patent_id}.xml
        parsed/
            statutes/{statute_id}.json
            cases/{case_id}.json
            patents/{patent_id}.json
    user_docs/
        {user_id}/
            {session_id}/
                {doc_id}/
                    original.{ext}   # encrypted
                    parsed.json       # encrypted
    web_archive/
        tier2/
            {domain}/{date}/{url_hash}.html
        tier3/
            {domain}/{date}/{url_hash}.html
    eval/
        golden_set/v1.0/questions.json
        run_results/{run_id}.json
```

### 7.2 Encryption for user documents

User documents in R2 are encrypted at the application layer before upload:

```python
from cryptography.fernet import Fernet
import hashlib, base64

def derive_user_key(root_key: bytes, user_id: str) -> Fernet:
    """Derive a per-user encryption key from the root key and user ID."""
    key_material = hashlib.pbkdf2_hmac(
        'sha256',
        root_key,
        user_id.encode(),
        iterations=100_000
    )
    key = base64.urlsafe_b64encode(key_material[:32])
    return Fernet(key)

async def upload_user_document(
    user_id: str,
    document_id: str,
    content: bytes,
    root_key: bytes
) -> str:
    f = derive_user_key(root_key, user_id)
    encrypted = f.encrypt(content)
    key = f"user_docs/{user_id}/{document_id}/original.enc"
    await r2_client.put_object(bucket="themis-machina", key=key, body=encrypted)
    return key
```

The root encryption key is stored in the cloud provider's secret manager (Cloudflare's own secrets in Phase A, Vault in Phase B). It is never in the codebase or environment files.

### 7.3 R2 capacity planning

| Content type | Estimated volume (Phase A) |
|---|---|
| Statute raw files (50 acts) | ~500 MB |
| SC case raw files (5K cases) | ~5 GB |
| Parsed JSON intermediates | ~2 GB |
| User documents (demo traffic) | ~100 MB |
| Web archives (Tier 2/3) | ~200 MB |
| Eval data | ~50 MB |
| **Total** | **~7.85 GB** |

Within the 10 GB R2 free tier. Phase B (full 30K SC corpus + High Courts) requires R2 paid.

---

## 8. Data Lineage and Provenance

Every data artifact has a traceable lineage from source to display.

### 8.1 A chunk's complete lineage

```
Source (India Code statute XML)
    ↓ download
corpus_sources row (id="ni_act_s138", r2_key="corpus/raw/statutes/ni_act/current.pdf")
    ↓ parse (Unstructured.io)
Parsed JSON (r2_key="corpus/parsed/ni_act_s138.json")
    ↓ chunk (legal-aware section chunker)
corpus_chunks row (id="ni_act_s138_ch00042", char_start=1430, char_end=2180)
    ↓ embed (BGE-M3 or NIM)
Qdrant point (collection="corpus_statutes", id=<uuid>)
    ↓ retrieve (hybrid search + rerank)
RetrievedChunk (id="ni_act_s138_ch00042", score=0.87, tier=1)
    ↓ generate (LLM with citation)
Claim (text="...", citations=[Citation(source_id="ni_act_s138_ch00042")])
    ↓ verify (verifier confirms support)
VerifiedClaim (status="supported")
    ↓ display
UI citation pill [s1] → click → source viewer → verbatim text highlighted
```

This lineage is reconstructable from the Postgres `corpus_chunks` table and the Qdrant payload. Given a source ID in a citation, the UI can fetch the original document from R2 and display the exact text.

### 8.2 Conversation lineage

```
User message (messages.id)
    → LangGraph state (langgraph.checkpoints.thread_id)
    → retrieved_chunk_ids (messages.retrieved_chunk_ids[])
    → structured_answer (messages.structured_answer JSONB)
    → citations (within structured_answer)
    → Langfuse trace (keyed by conversation_id + turn_index)
```

Full conversation playback is available in Langfuse for debugging and eval.

---

## 9. Data Migrations

All schema changes are managed with **Alembic** (the Postgres migration tool for SQLAlchemy/asyncpg stacks).

### 9.1 Migration conventions

- Every migration has a descriptive name: `001_initial_schema.py`, `002_add_corpus_chunks_embedding_model.py`
- Every migration can be rolled back (has both `upgrade()` and `downgrade()`)
- Migrations are run automatically on deploy via a pre-start hook
- No breaking migrations ship without a migration plan that ensures zero downtime

### 9.2 Schema evolution by phase

| Migration | Phase | Description |
|---|---|---|
| 001 | Phase 0 | Initial schema: users, sessions, conversations, messages |
| 002 | Phase 1 | Add corpus_sources, corpus_chunks tables |
| 003 | Phase 1 | Add eval_questions, eval_runs, eval_question_results |
| 004 | Phase 2 | Add prompt_versions, model_versions tables |
| 005 | Phase 3 | Add matters table; add matter_id FK to conversations |
| 006 | Phase 4 | Add answer_feedback table |
| 007 | Phase 6 | Add user_documents table |
| 008 | Phase 9 | Add audit_log table (partitioned) |
| 009 | Phase B | Add professional_verified fields to users |

---

## 10. Data Retention and Cleanup Jobs

Scheduled jobs running on Oracle Free VM (as Celery beat tasks):

```python
# Celery beat schedule
CELERYBEAT_SCHEDULE = {
    # Clean up expired anonymous sessions (daily at 3am IST)
    'cleanup-anonymous-sessions': {
        'task': 'themis.tasks.cleanup_anonymous_sessions',
        'schedule': crontab(hour=3, minute=0),
    },

    # Clean up expired session-scoped user documents (daily at 3:30am IST)
    'cleanup-expired-documents': {
        'task': 'themis.tasks.cleanup_expired_documents',
        'schedule': crontab(hour=3, minute=30),
    },

    # Refresh Tier 2 web archives (daily at 4am IST)
    'refresh-tier2-archives': {
        'task': 'themis.tasks.refresh_official_source_archives',
        'schedule': crontab(hour=4, minute=0),
    },

    # Run nightly eval (2am IST)
    'nightly-eval': {
        'task': 'themis.tasks.run_nightly_eval',
        'schedule': crontab(hour=2, minute=0),
    },

    # Partition maintenance: create next month's audit_log partition (1st of month)
    'audit-log-partition': {
        'task': 'themis.tasks.create_audit_partition',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),
    },
}
```

Cleanup task for expired documents:

```python
@celery.task
async def cleanup_expired_documents():
    """Delete session-scoped documents past their expiry date."""
    expired_docs = await db.fetch("""
        SELECT id, user_id, qdrant_collection, r2_key
        FROM user_documents
        WHERE expires_at < NOW()
          AND deleted_at IS NULL
          AND scoped_to = 'session'
        LIMIT 100
    """)

    for doc in expired_docs:
        # Delete from Qdrant (drop the whole per-user collection)
        await qdrant.delete_collection(doc["qdrant_collection"])
        # Delete from R2
        await r2.delete_object(doc["r2_key"])
        # Mark as deleted in Postgres
        await db.execute("""
            UPDATE user_documents
            SET deleted_at = NOW()
            WHERE id = $1
        """, doc["id"])
```

---

## 11. Data Access Patterns and Query Optimization

### 11.1 Hottest query paths

In production traffic, the hottest database operations are:

1. **LangGraph checkpoint load/save** (every turn): Postgres, highly optimized by LangGraph's built-in checkpointer
2. **Message insert** (every turn): Postgres, simple insert
3. **Qdrant retrieval** (every query): read-heavy, covered by HNSW index
4. **Rate limit check** (every request): Redis, O(log n) sorted-set operation
5. **Embedding cache lookup** (every retrieval): Redis GET, O(1)
6. **Matter listing** (sidebar render): Postgres, covered by `idx_matters_user`

### 11.2 Slow path optimizations

- **Full-conversation export** (infrequent): materializes the conversation into a document; runs as a background task, not in-request
- **Eval run** (nightly): runs as a Celery task with NIM concurrency cap; not in the request path
- **Document ingestion** (on upload): Celery task; async

### 11.3 Connection pooling

All Postgres connections go through asyncpg connection pools:

```python
# Maximum pool size for Phase A (NeonDB free tier allows up to 100 connections)
DATABASE_POOL_MIN_SIZE = 2
DATABASE_POOL_MAX_SIZE = 10  # conservative for free tier
DATABASE_POOL_MAX_INACTIVE_CONNECTION_LIFETIME = 300  # 5 minutes
```

---

## 12. Open Data Architecture Questions

| # | Question | Resolution deadline |
|---|---|---|
| 1 | When Phase A Qdrant 1 GB is close to capacity, move to self-hosted Qdrant on Oracle Free VM or reduce corpus scope? | Phase 4 (monitor from this point) |
| 2 | Should parsed JSON intermediates be stored in R2 indefinitely or have a TTL? | Phase 1 |
| 3 | User document Postgres row: store the clause analysis JSONB inline or as a separate table? | Phase 6 |
| 4 | Should the embedding cache (Redis) have a max-size eviction policy or grow indefinitely within the 256 MB cap? | Phase 1 |
| 5 | Should the Celery broker (Redis) be the same Upstash instance as the cache, or separate? Recommendation: same instance with different key prefixes for Phase A | Phase 1 |

---

## 13. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | [Date] | [You] | Approved baseline |

---

## 14. Related Documents

- **Document 2** — TRD (data stores overview)
- **Document 3** — AI/ML System Design (embedding strategy, chunking per corpus)
- **Document 7** — Safety & Responsible AI (user document isolation, encryption)
- **Document 9** — API Specification (data models exposed in the API)
- **Document 10** — Security & Privacy (encryption, access control)
- **Document 11** — Deployment & Infrastructure (database hosting)

— end of Document 8 —
