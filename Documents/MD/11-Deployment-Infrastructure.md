# Deployment & Infrastructure Document

**Project:** Themis Machina
**Assistant:** Themis GPT
**Document:** 11 of 13
**Version:** 1.0
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## 1. Purpose and Scope

This document specifies the complete deployment and infrastructure design of Themis Machina: containerization strategy, environment definitions, the Phase A free-tier deployment topology, CI/CD pipelines, infrastructure-as-code, monitoring and alerting, runbooks for common failure scenarios, and the Phase B production upgrade path.

It is the operational companion to the TRD (Document 2). Where the TRD specifies *what* is deployed, this document specifies *how* it is deployed and *what happens when it breaks*.

---

## 2. Deployment Philosophy

Three principles shape every infrastructure decision:

1. **Free tier first, production-portable second.** Every infrastructure component chosen for Phase A must be replaceable with a production-grade equivalent with no architectural change — only configuration change.
2. **Immutable infrastructure.** Deployments are never made by SSHing into a server and changing files. Every change is a new container image, a new deployment.
3. **Runbooks before incidents.** Common failure scenarios are documented before they occur, not during a 3am incident.

---

## 3. Environments

### 3.1 Environment matrix

| Environment | Purpose | Infra | Data | Access |
|---|---|---|---|---|
| **Local dev** | Developer iteration | Docker Compose on laptop | Synthetic / seeded | Developer only |
| **CI** | Automated tests and eval | GitHub Actions runners | Test fixtures from repo | GitHub Actions |
| **Staging** | Pre-production validation | Same as prod (Cloud Run) | Anonymized sample corpus | Builder only |
| **Production** | Live demo | Cloud Run + Oracle Free | Full corpus | Public |

In Phase A, staging and production share the same Cloud Run service (different revisions via traffic splitting). In Phase B, they are fully separate projects.

### 3.2 Environment variables per environment

Environment variables are managed per-environment. The principle:

- **Code is environment-agnostic.** The same Docker image runs in all environments.
- **Configuration is environment-specific.** URLs, keys, feature flags are injected via env vars.
- **Secrets are never in code.** No hardcoded values, no fallback defaults for secrets.

A `.env.example` file documents all required variables without values:

```bash
# LLM
NVIDIA_NIM_API_KEY=
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1

# Authentication
CLERK_SECRET_KEY=
CLERK_PUBLISHABLE_KEY=
CLERK_JWKS_URL=https://clerk.YOUR_CLERK_DOMAIN.com/.well-known/jwks.json

# Databases
DATABASE_URL=postgresql://user:pass@host:5432/themis?sslmode=require
QDRANT_URL=https://YOUR_CLUSTER.qdrant.io
QDRANT_API_KEY=
NEO4J_URI=neo4j+s://YOUR_CLUSTER.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=

# Storage
CLOUDFLARE_R2_ACCESS_KEY_ID=
CLOUDFLARE_R2_SECRET_ACCESS_KEY=
CLOUDFLARE_R2_ENDPOINT=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
CLOUDFLARE_R2_BUCKET=themis-machina

# Cache and queue
UPSTASH_REDIS_URL=rediss://default:PASSWORD@HOST:PORT

# Document encryption
DOCUMENT_ENCRYPTION_ROOT_KEY=

# Web search
TAVILY_API_KEY=

# Observability
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
SENTRY_DSN=
OTEL_EXPORTER_OTLP_ENDPOINT=https://tempo-prod-eu-west-0.grafana.net/otlp

# Feature flags
ENABLE_PATENT_MODULE=true
ENABLE_DOCUMENT_UPLOAD=true
ENABLE_WEB_SEARCH=true
MAX_UPLOAD_SIZE_MB=25

# Phase A / Phase B selector
PHASE=A
```

---

## 4. Containerization

### 4.1 Docker image strategy

Two Docker images:

- **`themis-api`** — the FastAPI backend service (deployed to Cloud Run)
- **`themis-worker`** — the Celery worker and background services (deployed to Oracle Free VM)

The frontend is deployed to Vercel directly from source — no Docker image needed for the frontend.

### 4.2 Backend Dockerfile (`themis-api`)

```dockerfile
# Multi-stage build for a lean production image

# ── Stage 1: dependency builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast dependency resolution
RUN pip install uv --no-cache-dir

# Copy dependency files first (layer caching)
COPY pyproject.toml uv.lock ./

# Install all dependencies into a virtual environment
RUN uv sync --frozen --no-dev --no-cache

# ── Stage 2: production image ─────────────────────────────────────────────────
FROM python:3.12-slim AS production

# Security: run as non-root
RUN groupadd --gid 1001 themis && \
    useradd --uid 1001 --gid 1001 --no-create-home themis

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source
COPY --chown=themis:themis src/ ./src/
COPY --chown=themis:themis prompts/ ./prompts/
COPY --chown=themis:themis alembic/ ./alembic/
COPY --chown=themis:themis alembic.ini .

USER themis

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

# Entrypoint: run migrations then start the server
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8080 --workers 2"]

EXPOSE 8080
```

Key choices:
- **Multi-stage build** keeps the production image lean (no build tools, no uv binary)
- **Non-root user** — a security requirement, particularly since this processes user documents
- **Migrations on startup** — ensures the schema is always up to date before traffic arrives
- **2 workers** — Cloud Run's free tier gives 1 vCPU; 2 workers maximizes utilization

### 4.3 Worker Dockerfile (`themis-worker`)

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install uv --no-cache-dir
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

FROM python:3.12-slim AS production

RUN groupadd --gid 1001 themis && \
    useradd --uid 1001 --gid 1001 --no-create-home themis

WORKDIR /app
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=themis:themis src/ ./src/
COPY --chown=themis:themis prompts/ ./prompts/

USER themis

# Celery worker — listens to all queues
CMD ["celery", "-A", "src.celery_app", "worker", \
     "--loglevel=info", \
     "--queues=ingestion,scrape,eval,default", \
     "--concurrency=2"]
```

### 4.4 Local development with Docker Compose

```yaml
# docker-compose.yml (development only)
version: '3.9'

services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
      target: production
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql://themis:themis@postgres:5432/themis
      - QDRANT_URL=http://qdrant:6333
      - NEO4J_URI=bolt://neo4j:7687
      - UPSTASH_REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./src:/app/src:ro  # hot-reload in dev
    command: uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    environment:
      - DATABASE_URL=postgresql://themis:themis@postgres:5432/themis
      - QDRANT_URL=http://qdrant:6333
      - UPSTASH_REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - qdrant
      - redis

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: themis
      POSTGRES_PASSWORD: themis
      POSTGRES_DB: themis
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U themis"]
      interval: 5s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/themis_dev
    volumes:
      - neo4j_data:/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
  qdrant_data:
  neo4j_data:
```

Running locally:

```bash
docker compose up -d
# Seeds the corpus with a small sample
python scripts/seed_dev_corpus.py
# Runs the API with hot-reload at http://localhost:8080
```

---

## 5. Phase A Deployment Topology

### 5.1 Component placement

```
┌────────────────────────────────────────────────────────────────────┐
│ CLOUDFLARE (free)                                                  │
│ - DNS, CDN, TLS, WAF, DDoS protection                             │
│ - Proxies all traffic                                              │
└──────────────┬────────────────────┬───────────────────────────────┘
               │                    │
               ▼                    ▼
┌──────────────────────┐  ┌─────────────────────────────┐
│ VERCEL (free)        │  │ GOOGLE CLOUD RUN (free)     │
│ Next.js frontend     │  │ themis-api container         │
│ Auto-deploys from    │  │ Scale-to-zero                │
│ main branch          │  │ Max 1 instance (free tier)   │
│                      │  │ 2 vCPU, 4 GB RAM             │
└──────────────────────┘  └──────────────┬───────────────┘
                                          │ (outbound)
              ┌───────────────────────────┼──────────────────────┐
              │                           │                      │
              ▼                           ▼                      ▼
┌─────────────────────┐  ┌───────────────────────┐  ┌──────────────────┐
│ NEON (free)         │  │ QDRANT CLOUD (free)   │  │ NEO4J AURA (free)│
│ Postgres 0.5 GB     │  │ 1 GB vector store     │  │ 200K nodes       │
│ Scale-to-zero       │  │                       │  │                  │
└─────────────────────┘  └───────────────────────┘  └──────────────────┘
              │                           │
              ▼                           ▼
┌─────────────────────┐  ┌───────────────────────┐
│ UPSTASH (free)      │  │ CLOUDFLARE R2 (free)  │
│ Redis 256 MB        │  │ Object storage 10 GB  │
└─────────────────────┘  └───────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ ORACLE CLOUD FREE FOREVER (always-on VM)                          │
│ 4 ARM cores, 24 GB RAM                                            │
│ - Celery workers (document ingestion, corpus refresh)             │
│ - Celery beat (scheduled tasks)                                   │
│ - Ollama (local LLM fallback: Qwen 2.5 14B, Llama 3.2 3B)       │
│ - Self-hosted Qdrant (overflow if Cloud free 1GB is exceeded)    │
│ - BGE-M3 embedding server (local embedding fallback)             │
│ - BGE-reranker (local reranker)                                   │
│ - Corpus ingestion runs (batch, scheduled)                        │
└────────────────────────────────────────────────────────────────────┘

External APIs (all free tier):
├── NVIDIA NIM (LLMs, embeddings, reranker)
├── LANGFUSE CLOUD (LLM observability)
├── GRAFANA CLOUD (metrics, logs, traces)
├── SENTRY (error tracking)
├── CLERK (auth)
└── TAVILY (web search)
```

### 5.2 Cloud Run configuration

```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: themis-api
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"   # scale to zero when idle
        autoscaling.knative.dev/maxScale: "1"   # max 1 instance (free tier)
        run.googleapis.com/cpu-throttling: "false"  # always allocate CPU (needed for streaming SSE)
    spec:
      containerConcurrency: 80   # max concurrent requests per instance
      timeoutSeconds: 300        # 5 minutes (enough for slow prior-art searches)
      containers:
        - image: gcr.io/PROJECT_ID/themis-api:latest
          ports:
            - containerPort: 8080
          resources:
            limits:
              cpu: "1"       # 1 vCPU
              memory: "2Gi"  # 2 GB RAM
          env:
            - name: PHASE
              value: "A"
            # All secrets injected from Secret Manager
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: themis-database-url
                  key: latest
            # ... (all other secrets injected similarly)
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
```

**Important Cloud Run settings for SSE streaming:**

Cloud Run's default behavior buffers responses. For SSE to work, two settings are required:
- `run.googleapis.com/cpu-throttling: "false"` — keep CPU allocated during streaming (not just during request handling)
- Response headers must include `X-Accel-Buffering: no` to disable Cloudflare buffering

```python
# In FastAPI SSE endpoint
@app.post("/api/v1/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, ...):
    async def generate():
        async for event in orchestrator.run(message):
            yield f"event: {event.type}\ndata: {event.json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # critical for Cloudflare pass-through
        }
    )
```

### 5.3 Oracle Free VM setup

The Oracle Cloud Free Forever VM (4 ARM Ampere cores, 24 GB RAM) runs all always-on services.

Initial setup:

```bash
# Ubuntu 22.04 ARM on Oracle Cloud

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

# Install Ollama for Apple Silicon... wait, this is ARM Linux
# Ollama supports ARM Linux natively
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &  # starts the Ollama API server

# Pull the fallback models
ollama pull qwen2.5:14b
ollama pull llama3.2:3b

# Pull the embedding and reranker models (served via custom FastEmbed server)
pip install fastembed
python -m themis.services.embedding_server  # starts on port 8001

# BGE-reranker server
python -m themis.services.reranker_server   # starts on port 8002

# Install Coolify for easy container management (optional but convenient)
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Services run as systemd units on the Oracle VM:

```ini
# /etc/systemd/system/themis-worker.service
[Unit]
Description=Themis Celery Worker
After=network.target docker.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/themis
EnvironmentFile=/home/ubuntu/themis/.env.production
ExecStart=docker compose -f docker-compose.worker.yml up
ExecStop=docker compose -f docker-compose.worker.yml down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable themis-worker
systemctl enable ollama
systemctl enable themis-embedding-server
systemctl enable themis-reranker-server
```

### 5.4 Vercel frontend configuration

```json
// vercel.json
{
  "framework": "nextjs",
  "buildCommand": "next build",
  "outputDirectory": ".next",
  "env": {
    "NEXT_PUBLIC_API_URL": "https://api.themismachina.app",
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "@clerk_publishable_key"
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" }
      ]
    }
  ],
  "redirects": [
    { "source": "/health", "destination": "https://api.themismachina.app/health", "permanent": false }
  ]
}
```

Vercel auto-deploys from the `main` branch and creates preview deployments for every PR (preview deployments point to the staging API URL).

---

## 6. CI/CD Pipeline

### 6.1 Pipeline overview

```
Developer pushes to feature branch
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ On Pull Request (PR pipeline)                                       │
│                                                                     │
│  Lint + type check (ruff, mypy, tsc, eslint)      ~2 min          │
│  Unit tests (pytest, jest)                         ~3 min          │
│  Integration tests (pytest + httpx)               ~5 min          │
│  Security scan (bandit, npm audit, detect-secrets)~2 min          │
│  Eval fast set (30 questions via NIM)              ~8 min          │
│  Post eval results as PR comment                   ~1 min          │
│                                                                     │
│  Total: ~21 minutes                                                 │
│  Gate: any failure blocks merge                                     │
└─────────────────────────────────────────────────────────────────────┘
         │ merge to main
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ On merge to main (staging pipeline)                                 │
│                                                                     │
│  Eval full set (200 questions via NIM + Ollama)    ~25 min         │
│  Build Docker image (themis-api)                   ~4 min          │
│  Push image to GitHub Container Registry           ~2 min          │
│  Deploy to Cloud Run (staging revision)            ~2 min          │
│  Smoke test staging (5 end-to-end queries)        ~2 min          │
│  Publish eval results to dashboard                 ~1 min          │
│                                                                     │
│  Total: ~36 minutes                                                 │
│  Gate: eval regression blocks; smoke test failure blocks           │
└─────────────────────────────────────────────────────────────────────┘
         │ manual release tag
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ On release tag (production pipeline)                                │
│                                                                     │
│  Full eval set + citation accuracy + latency benchmark ~45 min    │
│  Build + tag production Docker image               ~4 min          │
│  Manual approval gate (GitHub Environment protection) — required   │
│  Deploy to Cloud Run (production revision, 100% traffic)  ~2 min  │
│  Production smoke test (3 queries, check latency)  ~2 min         │
│                                                                     │
│  Total: ~55 minutes (mostly eval)                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 GitHub Actions workflow files

**PR pipeline:**

```yaml
# .github/workflows/pr.yml
name: PR Checks

on:
  pull_request:
    branches: [main]

jobs:
  lint-and-type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install uv && uv sync
      - run: ruff check src/ tests/
      - run: mypy src/ --strict
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && pnpm install && pnpm lint && pnpm tsc --noEmit

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install uv && uv sync
      - run: pytest tests/unit/ -v --tb=short

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_USER: themis, POSTGRES_PASSWORD: themis, POSTGRES_DB: themis }
        options: --health-cmd pg_isready --health-interval 5s
      redis:
        image: redis:7-alpine
        options: --health-cmd "redis-cli ping" --health-interval 5s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install uv && uv sync
      - env:
          DATABASE_URL: postgresql://themis:themis@localhost:5432/themis
          UPSTASH_REDIS_URL: redis://localhost:6379
          # NIM and Qdrant are mocked in integration tests
        run: pytest tests/integration/ -v --tb=short

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install bandit detect-secrets && bandit -r src/ -ll -ii
      - run: detect-secrets scan --baseline .secrets.baseline
      - run: cd frontend && npm audit --audit-level=high

  eval-fast:
    runs-on: ubuntu-latest
    if: |
      contains(github.event.pull_request.changed_files, 'src/retrieval') ||
      contains(github.event.pull_request.changed_files, 'src/orchestration') ||
      contains(github.event.pull_request.changed_files, 'prompts') ||
      contains(github.event.pull_request.changed_files, 'src/models')
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install uv && uv sync
      - env:
          NVIDIA_NIM_API_KEY: ${{ secrets.NVIDIA_NIM_API_KEY }}
          QDRANT_URL: ${{ secrets.QDRANT_STAGING_URL }}
          QDRANT_API_KEY: ${{ secrets.QDRANT_STAGING_API_KEY }}
          DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
          NEO4J_URI: ${{ secrets.NEO4J_URI }}
          NEO4J_USERNAME: ${{ secrets.NEO4J_USERNAME }}
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
        run: |
          python -m themis_eval.runner \
            --mode fast \
            --pr-number ${{ github.event.pull_request.number }} \
            --git-sha ${{ github.sha }} \
            --output-file eval_results.json
      - uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('eval_results.json'));
            const comment = buildEvalComment(results);
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment,
            });
      - run: python -m themis_eval.check_regression --results eval_results.json
```

**Staging pipeline:**

```yaml
# .github/workflows/staging.yml
name: Deploy to Staging

on:
  push:
    branches: [main]

jobs:
  eval-full:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install uv && uv sync
      - env:
          NVIDIA_NIM_API_KEY: ${{ secrets.NVIDIA_NIM_API_KEY }}
          # ... all staging env vars
        run: |
          python -m themis_eval.runner \
            --mode full \
            --trigger merge \
            --git-sha ${{ github.sha }}

  build-and-push:
    needs: eval-full
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Authenticate to GitHub Container Registry
        run: echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
      - name: Build and push
        run: |
          docker build -f docker/Dockerfile.api -t ghcr.io/${{ github.repository }}/themis-api:${{ github.sha }} .
          docker push ghcr.io/${{ github.repository }}/themis-api:${{ github.sha }}

  deploy-staging:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SERVICE_ACCOUNT_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - name: Deploy to Cloud Run (staging revision)
        run: |
          gcloud run deploy themis-api \
            --image gcr.io/${{ vars.GCP_PROJECT_ID }}/themis-api:${{ github.sha }} \
            --region us-central1 \
            --tag staging \
            --no-traffic \
            --project ${{ vars.GCP_PROJECT_ID }}

  smoke-test:
    needs: deploy-staging
    runs-on: ubuntu-latest
    steps:
      - run: |
          python scripts/smoke_test.py \
            --base-url https://staging---themis-api-HASH-uc.a.run.app \
            --queries 5
```

### 6.3 Deployment strategy (zero-downtime)

Cloud Run supports revision-based traffic splitting, enabling zero-downtime deployments:

```bash
# Deploy new revision without traffic
gcloud run deploy themis-api \
  --image gcr.io/PROJECT/themis-api:SHA \
  --no-traffic \
  --tag canary

# Send 10% of traffic to canary, watch for errors
gcloud run services update-traffic themis-api \
  --to-tags canary=10

# If health checks pass after 5 minutes, send 100% traffic
gcloud run services update-traffic themis-api \
  --to-latest
```

For Phase A with low traffic, the simpler approach is acceptable: deploy and switch 100% immediately. Zero-downtime canary is a Phase B operational practice.

### 6.4 Rollback procedure

If a deployment causes problems:

```bash
# List recent revisions
gcloud run revisions list --service themis-api

# Roll back to a previous revision by name
gcloud run services update-traffic themis-api \
  --to-revisions themis-api-PREVIOUS_SHA=100

# Verify rollback
curl https://api.themismachina.app/health
```

Rollback completes in under 30 seconds.

---

## 7. Infrastructure as Code

### 7.1 What is codified

All infrastructure is defined as code or configuration. Manual console clicks are only for one-time bootstrapping (creating the GCP project, enabling APIs).

| Component | IaC tool | Location |
|---|---|---|
| Cloud Run service | gcloud CLI + YAML | `infra/cloud-run/service.yaml` |
| Vercel config | `vercel.json` | `frontend/vercel.json` |
| Docker images | Dockerfile | `docker/Dockerfile.api`, `docker/Dockerfile.worker` |
| Oracle VM services | systemd unit files | `infra/oracle-vm/systemd/` |
| Docker Compose (dev) | `docker-compose.yml` | root |
| Database migrations | Alembic | `alembic/versions/` |
| Celery beat schedule | Python | `src/celery_app.py` |
| GitHub Actions | YAML | `.github/workflows/` |

Terraform is deferred to Phase B. Phase A's infrastructure is small enough to manage with raw YAML files and gcloud CLI commands.

### 7.2 Infrastructure bootstrap script

A `scripts/bootstrap.sh` documents and automates the one-time setup:

```bash
#!/bin/bash
# bootstrap.sh — sets up Phase A infrastructure from scratch
# Run once when setting up the project. Idempotent.

set -e

PROJECT_ID=${GCP_PROJECT_ID:?Required}
REGION=${GCP_REGION:-us-central1}

echo "=== Phase A Infrastructure Bootstrap ==="

# 1. Enable GCP APIs
gcloud services enable run.googleapis.com secretmanager.googleapis.com \
  artifactregistry.googleapis.com --project $PROJECT_ID

# 2. Create Artifact Registry for Docker images
gcloud artifacts repositories create themis-docker \
  --repository-format docker \
  --location $REGION \
  --project $PROJECT_ID \
  --description "Themis Machina Docker images" \
  2>/dev/null || echo "Artifact registry already exists"

# 3. Create service account for Cloud Run
gcloud iam service-accounts create themis-api \
  --display-name "Themis API Service Account" \
  --project $PROJECT_ID \
  2>/dev/null || echo "Service account already exists"

# 4. Grant minimal permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member "serviceAccount:themis-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role "roles/secretmanager.secretAccessor"

# 5. Load secrets into Secret Manager from .env.production
while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" == "#"* ]] && continue
  gcloud secrets create "$key" --data-file=- --project $PROJECT_ID <<< "$value" \
    2>/dev/null || \
  gcloud secrets versions add "$key" --data-file=- --project $PROJECT_ID <<< "$value"
done < .env.production

echo "=== Bootstrap complete ==="
echo "Next: deploy the first revision with ./scripts/deploy.sh"
```

---

## 8. Monitoring and Alerting

### 8.1 Observability stack

The full observability stack uses Grafana Cloud's free tier:

```
Application code
    │ OpenTelemetry SDK
    ▼
Cloud Run service
    │ OTLP (traces, metrics, logs)
    ├──► Grafana Tempo (traces) ──► Grafana dashboard
    ├──► Grafana Loki (logs) ──► Grafana Explore
    └──► Prometheus remote write (metrics) ──► Grafana dashboard

LLM calls
    │ Langfuse SDK
    ▼
Langfuse Cloud (LLM traces) ──► Langfuse dashboard

Errors
    │ Sentry SDK
    ▼
Sentry (error tracking + alerting)
```

### 8.2 Key dashboards

**Main operational dashboard (Grafana):**

| Panel | Metric |
|---|---|
| Request rate | `rate(http_requests_total[5m])` |
| Error rate | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])` |
| Latency p50/p95/p99 | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` |
| Active sessions | `themis_active_sessions_total` |
| LLM cost today | `sum(themis_llm_cost_total{period="today"})` (Phase B only) |
| NIM rate limit hits | `rate(themis_nim_rate_limit_total[5m])` |
| Ollama fallback rate | `rate(themis_llm_fallback_total{provider="ollama"}[5m])` |

**AI quality dashboard (Langfuse + Grafana):**

| Panel | Source |
|---|---|
| Faithfulness trend | Nightly eval results in Postgres → Grafana |
| Citation accuracy | Same |
| Hallucinated citation rate | Same |
| Refusal precision | Same |
| Verifier pass rate | Langfuse trace aggregation |
| Model latency (p50/p95 per node) | Langfuse trace aggregation |

### 8.3 Alerting rules

Alerts configured in Grafana Cloud:

```yaml
# Critical alerts — wake-me-up-at-3am tier
- alert: ErrorRateHigh
  expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Error rate above 5% for 5 minutes"

- alert: ServiceDown
  expr: up{job="themis-api"} == 0
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Themis API is unreachable"

# Warning alerts — check-in-the-morning tier
- alert: LatencyHigh
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 25
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "p95 latency above 25s for 10 minutes"

- alert: NIMRateLimitHigh
  expr: rate(themis_nim_rate_limit_total[5m]) > 2
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "NIM rate limits hit more than 2x/min — Ollama fallback active"

- alert: QdrantCapacityHigh
  expr: themis_qdrant_storage_used_bytes / (1 * 1024 * 1024 * 1024) > 0.9
  for: 30m
  labels:
    severity: warning
  annotations:
    summary: "Qdrant storage above 90% of free-tier 1 GB limit"

- alert: EvalRegressionDetected
  expr: themis_eval_regression_detected == 1
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Nightly eval detected a quality regression — check eval results"
```

Alerts route to email in Phase A. In Phase B, PagerDuty or Opsgenie integration handles on-call rotation.

---

## 9. Runbooks

### 9.1 Runbook: NIM rate limit exceeded

**Symptoms:** Requests are failing with `503 SERVICE_UNAVAILABLE`. Logs show `LLM_RATE_LIMIT_EXCEEDED`. The `themis_nim_rate_limit_total` metric is spiking.

**Immediate action:**

The system should automatically fall back to Ollama on the Oracle VM. Check if the fallback is working:

```bash
# Check Cloud Run logs
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload:"ollama_fallback"' \
  --project $GCP_PROJECT_ID --limit 20

# Check Ollama status on Oracle VM
ssh ubuntu@ORACLE_VM_IP "systemctl status ollama"
```

**If Ollama fallback is working:** No immediate action. The system will operate with slightly higher latency. The NIM rate limit resets hourly.

**If Ollama fallback is also failing:**

```bash
# Restart Ollama on Oracle VM
ssh ubuntu@ORACLE_VM_IP "systemctl restart ollama && sleep 10 && systemctl status ollama"
```

**Root cause and prevention:** If this happens during eval runs, reduce the eval concurrency:
```python
# In config/eval_thresholds.json
"max_concurrent": 3  # reduce from 5 to 3
```

### 9.2 Runbook: Qdrant free-tier capacity approaching limit

**Symptoms:** `themis_qdrant_storage_used_bytes` approaching 1 GB. Ingestion jobs may start failing.

**Immediate actions (in order):**

1. **Check what's taking space:**

```python
# Run in a Python shell or admin endpoint
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
for collection in client.get_collections().collections:
    info = client.get_collection(collection.name)
    print(f"{collection.name}: {info.vectors_count} vectors, approx {info.disk_data_size / 1e6:.1f} MB")
```

2. **Delete stale user document collections:**

```sql
-- Find expired user doc collections in Postgres
SELECT qdrant_collection, expires_at
FROM user_documents
WHERE expires_at < NOW() AND deleted_at IS NULL;
```

Then for each found:

```python
client.delete_collection(collection_name)
```

3. **Switch to self-hosted Qdrant on Oracle VM:**

```bash
# Start self-hosted Qdrant on Oracle VM
ssh ubuntu@ORACLE_VM_IP "docker run -d -p 6333:6333 -v /home/ubuntu/qdrant_data:/qdrant/storage qdrant/qdrant"

# Update QDRANT_URL in Cloud Run to point to Oracle VM
gcloud run services update themis-api \
  --update-env-vars QDRANT_URL=http://ORACLE_VM_IP:6333 \
  --region us-central1
```

4. **If still insufficient:** Defer Phase 7 (patents) until Phase B Qdrant is provisioned.

### 9.3 Runbook: Neon Postgres scale-to-zero latency

**Symptoms:** First request after idle period is slow (up to 3-5s). This is Neon's cold-start behavior.

**Diagnosis:** Check if Neon is in the suspended state via the Neon dashboard.

**Mitigation:** A keep-alive ping every 5 minutes (runs as a Cloud Run scheduled job):

```yaml
# cloud-scheduler.yaml
- name: neon-keepalive
  schedule: "*/5 * * * *"
  target:
    uri: https://api.themismachina.app/api/v1/status
  method: GET
```

This prevents Neon from suspending. Acceptable on the free tier since it's only a simple health query.

### 9.4 Runbook: Cloud Run cold start

**Symptoms:** Occasional 3-8 second delay on first request after idle period (Cloud Run scale-to-zero).

**Diagnosis:** Check Cloud Run metrics for `startup_latency`.

**Mitigation options:**

1. **Cloud Run minimum instances (paid):** Set `minScale: 1` — costs ~$5/month but eliminates cold starts.
2. **Scheduled keepalive (free):** Same as above — a Cloud Scheduler job hits the health endpoint every 10 minutes. Effective if traffic is somewhat regular.
3. **Accept it (Phase A):** Cold starts are acceptable for a portfolio demo with low traffic. Document them honestly in the README.

For Phase A, option 3 is recommended. Document the known behavior.

### 9.5 Runbook: Deploy failure

**Symptoms:** GitHub Actions deploy job failed. Cloud Run shows the new revision in error state.

**Immediate action:**

```bash
# Check Cloud Run revision status
gcloud run revisions list --service themis-api --region us-central1

# If new revision is unhealthy, route all traffic back to previous
gcloud run services update-traffic themis-api \
  --to-revisions PREVIOUS_REVISION_NAME=100 \
  --region us-central1
```

**Common causes:**

- Database migration failed → Check Alembic output in Cloud Run logs
- Secret not found → Check Secret Manager for missing secrets
- Image pull failed → Check artifact registry permissions and image name
- Health check failing → Application crash; check application logs

### 9.6 Runbook: Citation accuracy regression detected

**Symptoms:** Nightly eval shows hallucinated citation rate above threshold. Alert fires.

**Diagnosis (in order):**

1. Check which questions regressed:

```sql
SELECT q.question, r.failure_type, r.faithfulness_score
FROM eval_question_results r
JOIN eval_questions q ON q.id = r.question_id
JOIN eval_runs run ON run.id = r.run_id
WHERE run.completed_at > NOW() - INTERVAL '25 hours'
  AND r.failure_type = 'hallucination_citation'
ORDER BY r.faithfulness_score ASC;
```

2. Check if a prompt changed recently (git log on `prompts/` directory)

3. Check if the LLM provider changed model versions (NIM sometimes silently updates)

4. Replay the failing questions with the previous prompt version and compare

**Resolution:**

- If prompt change caused it: revert the prompt version
- If provider model change caused it: adjust the prompt or add few-shot examples targeting the failing pattern
- Add the failing questions to the golden set regardless

---

## 10. Cost Tracking (Phase A)

Phase A is designed to run at ₹0 monthly. The monitoring stack tracks this:

```python
# Custom metric: LLM API spend per provider
# Phase A: this should always be 0 for NIM (free tier)
themis_llm_cost_total{provider="nvidia_nim", model="llama-3.3-70b"} 0.0
themis_llm_cost_total{provider="ollama", model="qwen2.5-14b"} 0.0  # local

# Rate limit headroom
themis_nim_rate_limit_remaining{window="per_minute"} 35  # out of 40
```

A weekly check reviews all free tier limits:

| Service | Usage this week | Free limit | Headroom |
|---|---|---|---|
| NIM API calls | ~5,000 | Generous | OK |
| Qdrant storage | 650 MB | 1 GB | 35% |
| Neon Postgres | 210 MB | 500 MB | 58% |
| Upstash commands | 48,000 | 10K/day (70K/week) | 31% |
| Cloudflare R2 | 5.2 GB | 10 GB | 48% |
| Langfuse observations | 32,000 | 50K/month | 36% |
| Cloud Run requests | 180,000 | 2M/month | 91% |

This table is updated weekly and published in the project's `OPERATIONS.md`.

---

## 11. Phase B Upgrade Path

When Themis Machina moves from portfolio to production, the infrastructure upgrade path:

| Component | Phase A | Phase B upgrade |
|---|---|---|
| Backend hosting | Cloud Run free (1 instance) | Cloud Run paid OR GKE Autopilot |
| Postgres | Neon free | Neon Pro OR Cloud SQL |
| Vector DB | Qdrant Cloud 1GB | Qdrant Cloud paid OR self-hosted cluster |
| Graph DB | Neo4j Aura Free | Neo4j Aura Pro |
| Cache | Upstash free | Upstash Pay-as-you-go |
| LLM | NVIDIA NIM free | Anthropic Claude (via LiteLLM) |
| Secrets | Cloud Run env vars | HashiCorp Vault |
| IaC | Raw YAML + gcloud CLI | Terraform |
| Monitoring | Grafana free | Grafana Pro OR Datadog |
| CI/CD | GitHub Actions (public repo) | Same + deployment environments |
| Deployment strategy | Immediate 100% switch | Blue-green or canary |

The migration from Phase A to Phase B is a configuration change in most cases:

- LLM: change `PHASE=A` to `PHASE=B` and set `ANTHROPIC_API_KEY`
- Postgres: update `DATABASE_URL` to point to the new instance
- Qdrant: update `QDRANT_URL` and `QDRANT_API_KEY`
- Hosting: update `gcloud run deploy` to use `minScale: 2` and `maxScale: 10`

No code changes required. This is the "provider portability" principle from the TRD paying off.

---

## 12. Open Infrastructure Questions

| # | Question | Resolution deadline |
|---|---|---|
| 1 | Should the Oracle Free VM use Docker with Coolify for container management, or raw systemd? Recommendation: systemd for simplicity | Phase 3 |
| 2 | Cloud Run region: us-central1 (default, free tier) vs asia-south1 (Mumbai, better latency to India but verify free tier availability) | Phase 10 |
| 3 | Should the production deployment use Cloud Run's `--min-instances 1` (eliminates cold starts but costs ~$5/month) or accept cold starts? | Phase 10 |
| 4 | Should Vercel preview deployments point to staging API or a dedicated preview environment? Recommendation: staging API | Phase 8 |
| 5 | When Qdrant free tier runs out, migrate to self-hosted on Oracle VM or upgrade to Qdrant Cloud paid? Recommendation: self-hosted on Oracle VM first (Oracle VM has 24GB RAM) | As needed |

---

## 13. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | [Date] | [You] | Approved baseline |

---

## 14. Related Documents

- **Document 2** — TRD (what is deployed)
- **Document 7** — Safety & Responsible AI (security controls in deployment)
- **Document 9** — API Specification (what the API gateway exposes)
- **Document 10** — Security & Privacy (network security, secrets management)
- **Document 12** — Project Roadmap (when each phase's infrastructure is stood up)

— end of Document 11 —
