# Security & Privacy Document

**Project:** Themis Machina
**Assistant:** Themis GPT
**Document:** 10 of 13
**Version:** 1.0
**Status:** Approved for build
**Owner:** [Your name]
**Last updated:** [Date]

---

## 1. Purpose and Scope

This document specifies the security architecture and privacy design of Themis Machina: authentication flows, authorization model, encryption at every layer, secrets management, network security, security testing, privacy controls, and regulatory compliance posture.

It complements **Document 7 (Safety & Responsible AI)**, which covers the AI-specific threat model (prompt injection, hallucination, scope enforcement). This document covers the infrastructure and application security layer.

The security design must satisfy two constraints simultaneously: it must be rigorous enough for a production legal AI system (where user data includes uploaded contracts, legal notices, and sensitive research), and it must be implementable on a free-tier infrastructure stack (Phase A).

---

## 2. Security Design Principles

1. **Zero-trust by default.** Every request is authenticated and authorized regardless of where it originates. No internal traffic is implicitly trusted.
2. **Least privilege everywhere.** Every service account, IAM role, API key, and user role has the minimum permissions required. Nothing more.
3. **Defense in depth.** No single security control is relied upon exclusively. Multiple independent controls address each threat.
4. **Fail secure.** On security control failure, default to the more restrictive behavior (deny, not permit).
5. **Privacy by design.** User data minimization, retention limits, and deletion rights are architectural properties, not afterthoughts.
6. **Auditable.** Every security-relevant event is logged with enough context to reconstruct what happened.

---

## 3. Authentication Architecture

### 3.1 Overview

Authentication is delegated to **Clerk** in Phase A (WorkOS in Phase B). Themis Machina never handles raw passwords. All authentication flows use OAuth 2.1 with PKCE.

The authentication flow:

```
User → Clerk (OAuth provider) → Clerk issues session token
     → Frontend exchanges token with Themis API
     → Themis API verifies token against Clerk JWKS
     → Themis API issues internal JWT
     → Frontend stores JWT in memory (not localStorage)
     → JWT sent as Bearer token on every API request
```

### 3.2 OAuth 2.1 with PKCE

All OAuth flows use PKCE (Proof Key for Code Exchange) to prevent authorization code interception:

```
1. Frontend generates code_verifier (random 32-byte value)
2. Frontend computes code_challenge = SHA-256(code_verifier)
3. Frontend redirects to Clerk with code_challenge
4. Clerk authenticates user, issues authorization code
5. Frontend exchanges code + code_verifier for tokens
6. Clerk verifies SHA-256(code_verifier) == code_challenge
7. Tokens issued only if the challenge matches
```

This prevents code interception attacks — even if an attacker intercepts the authorization code, they cannot exchange it without the code_verifier.

### 3.3 JWT lifecycle

| Property | Value |
|---|---|
| Algorithm | RS256 (asymmetric — Clerk signs, Themis verifies) |
| Access token lifetime | 1 hour |
| Refresh token lifetime | 30 days |
| Refresh token rotation | Yes — each use issues a new refresh token |
| Token storage on client | Access token: in-memory only (never localStorage, never sessionStorage) |
| Refresh token storage | HttpOnly, Secure, SameSite=Strict cookie |

Why access token in-memory: localStorage is accessible to any JavaScript on the page, including injected scripts via XSS. An in-memory token is lost on page refresh (the refresh token cookie handles re-authentication silently), and is not accessible to script injection attacks.

### 3.4 JWT validation in FastAPI

```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

security = HTTPBearer()
jwks_client = PyJWKClient("https://clerk.themismachina.app/.well-known/jwks.json")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> AuthenticatedUser:
    token = credentials.credentials
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience="themis-machina-api",
            issuer="https://clerk.themismachina.app",
        )
        return AuthenticatedUser(
            user_id=payload["sub"],
            email=payload["email"],
            role=payload.get("themis_role", "public_user"),
            professional_verified=payload.get("professional_verified", False),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_EXPIRED"})
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN"})
```

JWKS keys are cached with a 1-hour TTL; the client fetches fresh keys on cache miss, preventing stale-key failures when Clerk rotates keys.

### 3.5 Anonymous session authentication

Anonymous sessions use a cryptographically random token (32 bytes, URL-safe base64-encoded) stored in an HttpOnly cookie.

```python
import secrets
from datetime import timedelta

def create_anonymous_session() -> tuple[str, str]:
    """Returns (token, token_hash) — store only the hash."""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash

async def validate_anonymous_session(
    session_token: str = Header(None, alias="X-Session-Token")
) -> AnonymousSession:
    if not session_token:
        raise HTTPException(status_code=401, detail={"code": "NO_SESSION"})
    token_hash = hashlib.sha256(session_token.encode()).hexdigest()
    session = await db.fetchrow("""
        SELECT id, expires_at FROM anonymous_sessions
        WHERE session_token_hash = $1
          AND expires_at > NOW()
    """, token_hash)
    if not session:
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION"})
    return AnonymousSession(session_id=session["id"])
```

The raw token is never stored — only its SHA-256 hash. This means a database breach cannot be used to impersonate anonymous sessions.

---

## 4. Authorization Model

### 4.1 Role hierarchy

```
admin
  └─ professional_user
       └─ public_user
            └─ anonymous
```

Each role inherits the capabilities of all roles below it.

| Capability | Anonymous | Public | Professional | Admin |
|---|---|---|---|---|
| Ask research questions | ✓ (30/hr) | ✓ (200/hr) | ✓ (500/hr) | ✓ |
| Upload documents | ✗ | ✓ (5/hr) | ✓ (25/hr) | ✓ |
| Save research matters | ✗ | ✓ | ✓ | ✓ |
| Export in formal citation formats | ✗ | ✗ | ✓ (verified) | ✓ |
| Patent prior-art search | ✓ (limited) | ✓ | ✓ | ✓ |
| View eval results | ✗ | ✗ | ✗ | ✓ |
| Trigger eval runs | ✗ | ✗ | ✗ | ✓ (internal only) |
| Delete any user's data | ✗ | ✗ | ✗ | ✓ |

### 4.2 Resource-level authorization

Beyond roles, every resource (conversation, matter, document) is owned by a specific user. Ownership is enforced at the query level:

```python
async def get_conversation_or_403(
    conversation_id: str,
    current_user: AuthenticatedUser,
    db: AsyncConnection
) -> ConversationRow:
    row = await db.fetchrow("""
        SELECT * FROM conversations
        WHERE id = $1
          AND user_id = $2
          AND deleted_at IS NULL
    """, conversation_id, current_user.user_id)
    if not row:
        # Return 404 (not 403) to avoid revealing existence to unauthorized users
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    return row
```

The policy is to return 404 rather than 403 when a user tries to access a resource they don't own — this prevents enumeration attacks (an attacker can't tell whether a resource exists if they're not authorized).

### 4.3 Postgres row-level security

As a defense-in-depth measure, Postgres RLS policies enforce ownership at the database layer:

```sql
-- Enable RLS on all user-owned tables
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE matters ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see their own rows
CREATE POLICY conversations_owner_policy ON conversations
    USING (user_id = current_setting('app.current_user_id')::uuid);

CREATE POLICY user_documents_owner_policy ON user_documents
    USING (user_id = current_setting('app.current_user_id')::uuid);

-- Set the app.current_user_id at the start of each transaction
async def set_rls_user(conn, user_id: str):
    await conn.execute(f"SET LOCAL app.current_user_id = '{user_id}'")
```

The application sets `app.current_user_id` at the start of every database transaction. Even if an application-layer bug passes the wrong `user_id` parameter, the RLS policy catches it.

### 4.4 Service accounts and IAM

Each backend service runs with a dedicated IAM service account:

| Service | Account | Permissions |
|---|---|---|
| API Gateway (Cloud Run) | `themis-api@...` | Cloud Run invoker, Secret Manager accessor, Neon DB writer |
| Ingestion workers (Oracle VM) | `themis-worker@...` | R2 write, Qdrant write, Postgres write |
| Eval service | `themis-eval@...` | Postgres read/write (eval tables only), R2 read |
| Background scrapers | `themis-scraper@...` | R2 write, Postgres write (corpus tables only) |

No service account has blanket admin access. Cross-service communication uses short-lived tokens issued per-request.

---

## 5. Encryption

### 5.1 Encryption in transit

All external connections use TLS 1.3. Internal connections (Cloud Run → Neon, Cloud Run → Qdrant, Cloud Run → Upstash Redis) also use TLS where supported by the provider.

TLS configuration:

```
Minimum protocol: TLS 1.3
Cipher suites: TLS_AES_128_GCM_SHA256, TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256
Certificate authority: Let's Encrypt (auto-renewed via Cloudflare)
HSTS: max-age=31536000; includeSubDomains
```

### 5.2 Encryption at rest

| Storage | Encryption | Key management |
|---|---|---|
| Neon Postgres | AES-256 (provider-managed) | Neon's built-in encryption |
| Qdrant Cloud | AES-256 (provider-managed) | Qdrant Cloud encryption |
| Upstash Redis | AES-256 (provider-managed) | Upstash encryption |
| Cloudflare R2 | AES-256 (provider-managed) | Cloudflare encryption |
| User document files | AES-256 (application-managed, additional layer) | Fernet with per-user key (see §5.3) |

### 5.3 Application-level encryption for user documents

User-uploaded documents receive an additional encryption layer managed by the application, independent of the cloud provider. This means a cloud provider breach cannot expose document contents.

Key derivation:

```python
import os
import hashlib
import base64
from cryptography.fernet import Fernet

ROOT_ENCRYPTION_KEY = os.environ["DOCUMENT_ENCRYPTION_ROOT_KEY"]  # 32 bytes, from secret manager

def derive_document_key(user_id: str) -> Fernet:
    """
    Derive a per-user encryption key via PBKDF2.
    The same user always gets the same key (deterministic derivation).
    Changing the root key requires re-encryption of all documents.
    """
    key_material = hashlib.pbkdf2_hmac(
        hash_name='sha256',
        password=ROOT_ENCRYPTION_KEY.encode(),
        salt=user_id.encode(),
        iterations=100_000,
        dklen=32,
    )
    return Fernet(base64.urlsafe_b64encode(key_material))

async def encrypt_and_upload(
    user_id: str,
    document_id: str,
    content: bytes,
) -> str:
    fernet = derive_document_key(user_id)
    encrypted = fernet.encrypt(content)
    r2_key = f"user_docs/{user_id}/{document_id}/original.enc"
    await r2.put_object(key=r2_key, body=encrypted)
    return r2_key

async def download_and_decrypt(
    user_id: str,
    r2_key: str,
) -> bytes:
    encrypted = await r2.get_object(key=r2_key)
    fernet = derive_document_key(user_id)
    return fernet.decrypt(encrypted)
```

### 5.4 Secret management

**Phase A:**

- Application secrets stored as environment variables in Cloud Run and Vercel
- Secrets set via the provider's secrets interface (not in code or version control)
- A `.env.example` file in the repo shows required variable names without values
- A `.gitignore` rule ensures `.env`, `.env.local`, `.env.production` are never committed
- Secret rotation: manual, performed when a secret is suspected compromised or on a 90-day schedule

**Phase B:**

- HashiCorp Vault (self-hosted) or GCP Secret Manager for centralized secret storage
- Dynamic secrets for Postgres (Vault issues short-lived credentials per-request)
- Automatic 90-day rotation via Vault policies

Required secrets:

```
# LLM providers
NVIDIA_NIM_API_KEY
ANTHROPIC_API_KEY          # Phase B

# Authentication
CLERK_SECRET_KEY
CLERK_PUBLISHABLE_KEY
CLERK_JWKS_URL

# Databases
DATABASE_URL               # Neon connection string (includes credentials)
QDRANT_URL
QDRANT_API_KEY
NEO4J_URI
NEO4J_USERNAME
NEO4J_PASSWORD

# Storage
CLOUDFLARE_R2_ACCESS_KEY_ID
CLOUDFLARE_R2_SECRET_ACCESS_KEY
CLOUDFLARE_R2_BUCKET

# Cache
UPSTASH_REDIS_URL          # includes auth

# Document encryption
DOCUMENT_ENCRYPTION_ROOT_KEY   # 32 random bytes, base64-encoded

# Observability
LANGFUSE_SECRET_KEY
LANGFUSE_PUBLIC_KEY
SENTRY_DSN

# Web search
TAVILY_API_KEY
```

---

## 6. Network Security

### 6.1 Network topology

```
Internet
    │
    ▼
Cloudflare (CDN, WAF, DDoS protection, TLS termination)
    │
    ├── Vercel (Next.js frontend) — only receives HTTP requests
    │
    └── Google Cloud Run (FastAPI backend)
           │ (outbound only)
           ├── Neon Postgres (TLS)
           ├── Qdrant Cloud (TLS)
           ├── Neo4j Aura (TLS + Bolt)
           ├── Upstash Redis (TLS)
           ├── Cloudflare R2 (HTTPS)
           ├── NVIDIA NIM API (HTTPS)
           └── External APIs (Tavily, Clerk) (HTTPS)

Oracle Free VM (workers, always-on services)
    │ (outbound only, inbound only from Cloud Run)
    ├── Qdrant (self-hosted, if overflow)
    ├── Ollama (local LLM fallback)
    └── Celery workers
```

### 6.2 Cloudflare WAF rules

Cloudflare's WAF is configured with:

- **OWASP Core Rule Set** — blocks known injection patterns, XSS, path traversal
- **Rate limiting rules** — 100 requests/minute per IP (before application-level rate limiting)
- **Bot protection** — blocks known malicious bots, allows search engine crawlers only on public pages
- **IP reputation** — blocks IPs with poor reputation scores
- **Custom rules:**
  - Block requests with Content-Length > 30 MB (larger than any expected payload)
  - Block requests with unusual User-Agent patterns
  - Rate limit `/api/v1/sessions/anonymous` to 10/minute per IP (prevents session token farming)

### 6.3 CORS configuration

```python
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = [
    "https://themismachina.app",      # production frontend
    "https://www.themismachina.app",
    "https://staging.themismachina.app",
    "http://localhost:3000",          # local development only
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,           # needed for cookie-based refresh tokens
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "X-Session-Token", "Content-Type"],
    max_age=86400,                    # preflight cache: 24 hours
)
```

CORS is the last line of defense against cross-origin requests — not the primary security mechanism (auth tokens are).

### 6.4 Security headers

FastAPI middleware adds security headers to every response:

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'nonce-{nonce}'; "  # nonce injected per-request
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
        "font-src 'self' fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://clerk.themismachina.app; "
        "frame-ancestors 'none';"
    )
    return response
```

### 6.5 Input validation and sanitization

All API inputs are validated by Pydantic before reaching any business logic. Common attack vectors defended:

**SQL injection:** Not possible through SQLAlchemy's parameterized queries. Never use raw string interpolation in SQL.

**Path traversal:** R2 key construction never uses user-supplied input directly:

```python
def safe_r2_key(user_id: str, document_id: str, suffix: str) -> str:
    """Construct an R2 key, never using user input for path components."""
    # user_id and document_id are UUIDs (validated by Pydantic)
    # suffix is from a fixed allowlist
    assert suffix in ("original.enc", "parsed.json", "clauses.json")
    return f"user_docs/{user_id}/{document_id}/{suffix}"
```

**SSRF (Server-Side Request Forgery):** When the system fetches external URLs (Tier 2/3 web content via Tavily), the fetch goes through Tavily's infrastructure, not directly from the backend. Direct HTTP fetches in the codebase (for corpus downloads) use a fixed allowlist of domains.

**ReDoS:** Regular expressions in the sanitizer (Document 7, §8.3) use linear-time patterns only. No catastrophic backtracking.

---

## 7. Privacy Architecture

### 7.1 Data minimization

Themis Machina collects the minimum data required to provide the service:

| Data we collect | Why | Not collected |
|---|---|---|
| Email address | Authentication, account identification | Real name (optional display name only) |
| OAuth provider ID | SSO authentication | OAuth access tokens (never stored after exchange) |
| Conversation messages | To provide the service | Biometric data, payment information, location |
| Uploaded documents | To provide document analysis | Documents after session expiry (auto-deleted) |
| Usage metadata (timestamps, turn counts) | Service improvement, rate limiting | Full behavioral profiles, cross-session tracking |
| Feedback (thumbs up/down) | Eval improvement | Specific user identity linked to feedback (anonymized in eval use) |

### 7.2 Purpose limitation

Data collected for one purpose is not used for another:

- Conversation data is used to provide the research service; it is not used for training models
- Feedback is used for eval improvement; it is not used for user profiling or ad targeting
- Usage metadata is used for rate limiting and abuse prevention; it is not sold or shared with third parties

This is a commitment embedded in the architecture: the data pipeline for eval (Document 6) operates on anonymized question-answer pairs, not on raw user conversations.

### 7.3 Data subject rights (DPDP / GDPR)

| Right | Implementation |
|---|---|
| Access | `GET /api/v1/me/data-export` generates a ZIP of all user data within 24 hours |
| Correction | `PATCH /api/v1/me` allows display name update; email changes via Clerk |
| Deletion | `DELETE /api/v1/me` begins 30-day soft-delete window; hard delete removes all data |
| Portability | Data export is in machine-readable JSON format |
| Objection to processing | Account deletion is the primary mechanism |

### 7.4 Cookie policy

| Cookie | Type | Purpose | TTL |
|---|---|---|---|
| `__clerk_session` | HttpOnly, Secure, SameSite=Strict | Clerk session (auth) | Clerk-managed |
| `themis_refresh` | HttpOnly, Secure, SameSite=Strict | Refresh token for API JWTs | 30 days |
| `themis_anon` | HttpOnly, Secure, SameSite=Strict | Anonymous session token | 7 days |
| `themis_prefs` | Not HttpOnly, Secure, SameSite=Lax | UI preferences (mode, dark mode) | 1 year |

No third-party cookies. No tracking cookies. No advertising cookies.

### 7.5 Analytics

Phase A uses no third-party analytics. Simple server-side logging (request counts, latency percentiles, error rates) aggregated without user identification is sufficient.

If analytics are added in Phase B, they will use a privacy-preserving tool (Plausible, Umami) that does not use cookies or fingerprinting, rather than Google Analytics.

### 7.6 Privacy policy

A Privacy Policy is published at `/privacy`. Key commitments stated plainly:

- We never sell user data
- We never use user conversations to train AI models
- Uploaded documents are deleted automatically after session expiry
- Users can delete their account and all data at any time
- We use free-tier services from Neon, Qdrant, Cloudflare, etc. — links to their privacy policies
- We comply with India's DPDP Act

The Privacy Policy is reviewed by a qualified privacy professional before public launch.

---

## 8. Security Testing

### 8.1 SAST (Static Application Security Testing)

Integrated into CI via GitHub Actions:

```yaml
- name: Security scan (Bandit)
  run: |
    pip install bandit
    bandit -r src/ -ll -ii  # medium severity, medium confidence threshold

- name: Dependency vulnerability scan
  run: |
    pip install safety
    safety check --full-report
```

Bandit catches common Python security issues: hardcoded passwords, SQL injection patterns, insecure use of `eval`, weak cryptography, etc.

Safety checks Python dependencies against a vulnerability database. A PR with a vulnerable dependency is blocked.

For TypeScript:

```yaml
- name: npm audit
  run: |
    cd frontend
    npm audit --audit-level=high  # fails on high or critical vulnerabilities
```

### 8.2 DAST (Dynamic Application Security Testing)

Before each major release, a DAST scan runs against the staging environment:

- **OWASP ZAP** in API scan mode against the staging API
- Checks for: XSS, CSRF, injection, authentication bypass, sensitive data exposure, security header gaps
- Results are reviewed; critical/high findings block the release

### 8.3 Dependency scanning

Dependabot is enabled on the GitHub repository:

- Daily scans of Python and TypeScript dependencies
- PRs automatically created for security updates
- Critical vulnerabilities generate an immediate alert

### 8.4 Secret scanning

GitHub's secret scanning is enabled. It detects accidentally committed API keys, credentials, or tokens and alerts immediately.

Additionally, a pre-commit hook runs `detect-secrets` locally:

```bash
pip install detect-secrets
detect-secrets scan > .secrets.baseline
# Pre-commit: detect-secrets scan --baseline .secrets.baseline
```

### 8.5 Security-focused code review checklist

Every PR involving auth, data access, or user input goes through a security checklist:

```markdown
## Security checklist

### Authentication / Authorization
- [ ] Does this endpoint require auth? If so, is it enforced?
- [ ] Does every data access include a user_id filter?
- [ ] Are RLS policies active for the affected tables?

### Input validation
- [ ] Is all user input validated by Pydantic before use?
- [ ] Are file uploads validated for type, size, and content?
- [ ] Are path components constructed from fixed values only (no user input)?

### Cryptography
- [ ] Are passwords/tokens hashed before storage (never stored plaintext)?
- [ ] Is any new encryption using established algorithms (AES-256, SHA-256, Fernet)?
- [ ] Are there any hardcoded secrets or keys?

### Error handling
- [ ] Do error messages avoid leaking internal details (stack traces, user IDs)?
- [ ] Is the error response format consistent with the standard envelope?

### Logging
- [ ] Are security-relevant events logged (auth failures, access denied, injection attempts)?
- [ ] Do logs avoid including raw user content or PII?
```

### 8.6 Penetration testing plan

Before Phase 10 (public launch), a manual penetration test covers:

**Scope:**
- Authentication bypass attempts
- Privilege escalation (anonymous → public → professional → admin)
- Cross-user data leakage (attempting to access another user's conversations, documents)
- API endpoint enumeration
- Injection attacks (SQL, prompt, path traversal, SSRF)
- Session fixation and hijacking
- Insecure direct object reference (IDOR)
- Rate limit bypass

**Conducted by:** The builder (you) using standard tools (OWASP ZAP, Burp Suite Community, SQLMap for specific endpoints).

**Output:** A `SECURITY_AUDIT.md` documenting findings and mitigations, published alongside the README.

---

## 9. Incident Response Security Procedures

Supplementing Document 7 (§12) with security-specific procedures:

### 9.1 Credential compromise

If an API key or secret is suspected compromised:

1. Immediately rotate the credential via the provider's interface
2. Search logs for all requests authenticated with the compromised credential
3. If user data was accessed: assess scope, prepare user notification
4. Update the secret in all deployed environments (Cloud Run, Vercel)
5. Run a full audit of active sessions and invalidate as needed

### 9.2 Data breach procedure

If user data is confirmed or suspected to have been accessed without authorization:

1. Preserve logs and evidence (do not modify or delete)
2. Isolate the affected system if it is actively being exploited
3. Identify the scope: which users, what data, what time period
4. Under DPDP: notify the Data Protection Board within 72 hours of discovery
5. Notify affected users within the timeframe required by applicable law
6. Publish a security incident report on the repository

### 9.3 Responsible disclosure

A `SECURITY.md` at the repository root provides:

```markdown
## Security Policy

### Reporting a vulnerability

If you discover a security vulnerability in Themis Machina, please report it
responsibly by emailing security@themismachina.app.

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigations

We will:
- Acknowledge receipt within 48 hours
- Provide an initial assessment within 5 business days
- Keep you informed of progress
- Credit you in the fix acknowledgement (if you wish)

We ask that you:
- Do not exploit the vulnerability or access user data
- Do not publicly disclose before we have had a reasonable time to fix
- Do not disrupt service availability

We do not take legal action against good-faith security researchers.
```

---

## 10. Compliance Posture

### 10.1 India — Digital Personal Data Protection Act (DPDP)

The DPDP Act came into force in 2023 and its rules are being notified progressively. Themis Machina's compliance posture:

| DPDP obligation | Status |
|---|---|
| Notice to users about data processing | Implemented in Privacy Policy and UI |
| Consent for processing | Implemented at registration and in upload flow |
| Purpose limitation | Architectural (data pipeline is separated from training pipeline) |
| Data minimization | Implemented (minimum collection) |
| Accuracy | Users can correct display name; email managed by Clerk |
| Storage limitation | Retention limits and cleanup jobs implemented (Document 8) |
| Data principal rights (access, correction, deletion, portability) | Implemented via API endpoints |
| Grievance mechanism | Contact email in Privacy Policy |
| Significant data fiduciary obligations | Not applicable for v1.0 (low user volume) |
| Cross-border transfer restrictions | Data primarily stored within Cloudflare / Neon's applicable regions; reviewed before Phase B scale |

### 10.2 GDPR (applicable to EU visitors)

Themis Machina does not actively target EU users but applies GDPR-equivalent protections (which satisfy DPDP requirements) as a baseline:

| GDPR article | Implementation |
|---|---|
| Art. 6 (Lawful basis) | Contract performance (registered users); Legitimate interests (anonymous users for abuse prevention) |
| Art. 13 (Privacy notice) | Privacy Policy published at /privacy |
| Art. 15 (Access) | Data export endpoint |
| Art. 17 (Deletion) | Account deletion flow |
| Art. 20 (Portability) | JSON data export |
| Art. 25 (Privacy by design) | This document; data minimization throughout |
| Art. 32 (Security) | TLS, encryption, access controls throughout |

### 10.3 What is NOT in scope

| Framework | Status |
|---|---|
| SOC 2 | Out of scope for v1.0; relevant for Phase B if enterprise sales begin |
| ISO 27001 | Out of scope for v1.0 |
| HIPAA | Out of scope — no intentional handling of PHI |
| PCI-DSS | Out of scope — no payment processing |

---

## 11. Security in the Development Workflow

### 11.1 Pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: check-added-large-files  # no >500KB files in git
      - id: detect-private-key        # no private keys
      - id: check-merge-conflict
      - id: end-of-file-fixer

  - repo: https://github.com/Yelp/detect-secrets
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  - repo: https://github.com/PyCQA/bandit
    hooks:
      - id: bandit
        args: ['-ll']

  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff  # catches security-relevant lint issues
```

### 11.2 Branch protection

The `main` branch requires:

- At least one review (self-review with AI pair, documented in commit message)
- All CI checks passing (including security scans)
- No direct pushes to `main`

### 11.3 Security-sensitive files

Files that require extra care, listed in `.gitignore` and `.gitleaksignore`:

```
.env
.env.local
.env.production
*.pem
*.key
*.cert
secrets/
.secrets.baseline
```

---

## 12. Phase A vs Phase B Security Delta

Some security controls are pragmatically lighter in Phase A (free tier, portfolio project) than Phase B (production). Explicit acknowledgment of the gap:

| Control | Phase A | Phase B |
|---|---|---|
| Secret management | Env vars in Cloud Run + Vercel | HashiCorp Vault with dynamic secrets |
| Internal service auth | Shared service key in env var | mTLS with short-lived certs |
| Database credentials | Static connection string | Dynamic Vault-issued per-request credentials |
| Penetration testing | Manual (builder-conducted) | Third-party professional pentest |
| Security monitoring | Basic alerting on error rate spikes | SIEM with behavioral analytics |
| Vulnerability management | Dependabot + manual review | Automated remediation + SLA on critical CVEs |
| Audit log analysis | Manual review on incident | Automated anomaly detection |

The Phase A controls are sufficient for a portfolio-traffic application where the builder is the primary user. Before opening to real users at scale, Phase B controls are necessary.

---

## 13. Open Security Questions

| # | Question | Resolution deadline |
|---|---|---|
| 1 | Should the Cloudflare WAF use the managed OWASP ruleset or a custom ruleset? Recommendation: managed OWASP, then customize | Phase 10 |
| 2 | Should anonymous users' rate limits be enforced by IP hash or by session token? Recommendation: both (IP hash for overall cap, session token for session-level cap) | Phase 0 |
| 3 | Is PBKDF2 the right KDF for per-user document keys or should we use Argon2? Recommendation: Argon2id for stronger security if the iteration time budget permits | Phase 6 |
| 4 | Should access tokens be JWTs or opaque tokens? JWTs are stateless (chosen for Phase A); opaque tokens allow revocation without a shared revocation list | Phase A confirmed JWT; reconsider for Phase B |
| 5 | Should the security audit (`SECURITY_AUDIT.md`) be published in full or with sensitive details redacted? Recommendation: publish with attack techniques shown but specific vulnerable versions redacted | Phase 10 |

---

## 14. Document History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | [Date] | [You] | Approved baseline |

---

## 15. Related Documents

- **Document 2** — TRD (security architecture overview)
- **Document 7** — Safety & Responsible AI (AI-specific threat model, prompt injection)
- **Document 8** — Data Architecture (data retention, encryption at storage layer)
- **Document 9** — API Specification (auth headers, error codes)
- **Document 11** — Deployment & Infrastructure (network topology, cloud config)

— end of Document 10 —
