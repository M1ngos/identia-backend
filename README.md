# Biometric Identity Platform

> A FastAPI-based identity verification system for enrolling and verifying users with face and fingerprint biometrics.

It abstracts biometric processing behind simple REST APIs: enroll a user once, verify them on every subsequent request.

---

## Goals

- Provide a simple API for identity enrollment and verification
- Support multiple biometric modalities (face, fingerprint)
- Ensure secure, scalable, and privacy-aware identity handling
- Ship a swappable embedding layer so real ML models can replace the stub with no API changes

---

## Quick Start

### 1. Prerequisites

- Python 3.12+
- PostgreSQL 15+
- [uv](https://github.com/astral-sh/uv) package manager

> **Note**: PostgreSQL's `pgvector` extension is **not required**. Biometric embeddings are stored as serialized `float32` bytes (`LargeBinary`) and cosine similarity is computed in Python.

### 2. Clone & Setup

```bash
git clone <repository-url>
cd biometric-identity-sdk

uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

uv sync
```

### 3. Database Setup

```bash
# Create PostgreSQL database
psql -U postgres -c "CREATE DATABASE biometric_sdk;"

# Run database migrations
uv run alembic upgrade head
```

### 4. Configure Environment

```bash
cp .env.example .env
```

**Required settings in `.env`**:
```env
SECRET_KEY=your-secure-random-string-32-chars-minimum
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/biometric_sdk
```

**Optional settings**:
```env
DEBUG=false
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEFAULT_CONFIDENCE_THRESHOLD=0.85
ENROLL_RATE_LIMIT_PER_MINUTE=10
```

### 5. Run

```bash
# Development mode (with auto-reload)
uv run fastapi dev main.py

# Production mode
uv run fastapi run main.py
```

The API will be available at `http://localhost:8000`

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Authentication

All enrollment and verification endpoints require a JWT Bearer token. The flow is:

```
API Key (bsk_live_...) → POST /auth/token → JWT (30 min) → Protected endpoints
```

### Step 1: Bootstrap your first API key

The `POST /api/v1/auth/api-keys` endpoint requires an existing JWT, so the very first API key must be seeded directly via the service layer. Run this once:

```python
# seed_key.py — run once, then delete this file
import asyncio
from src.core.database import get_db
from src.services.auth_service import create_api_key

async def seed() -> None:
    async for db in get_db():
        key_model, plaintext = await create_api_key(
            db,
            owner_id="your-app-id",   # any string identifier for this key's owner
            label="primary",
            expires_at=None,           # or pass a datetime for key expiry
        )
        await db.commit()
        print(f"API key (save this — shown once): {plaintext}")

asyncio.run(seed())
```

```bash
uv run python seed_key.py
# API key (save this — shown once): bsk_live_...
```

### Step 2: Exchange the API key for a JWT

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "bsk_live_..."}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

JWTs expire after 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`). Re-exchange your API key to get a fresh token.

### Step 3: Use the JWT on all protected endpoints

```bash
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl http://localhost:8000/api/v1/enroll \
  -H "Authorization: Bearer $TOKEN" \
  ...
```

### Managing API keys (requires JWT)

```bash
# Create additional keys
curl -s -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"label": "ci-pipeline", "expires_in_days": 90}'

# List your keys (plaintext is never returned after initial creation)
curl -s http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer $TOKEN"

# Revoke a key
curl -s -X DELETE http://localhost:8000/api/v1/auth/api-keys/<key_id> \
  -H "Authorization: Bearer $TOKEN"
```

**Security details**:
- API keys are prefixed with `bsk_live_` and stored as bcrypt hashes — plaintext is never persisted
- JWTs are signed with HS256
- Rate limiter: `POST /auth/token` is capped at **20 requests/min per IP**
- Rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) are returned on every rate-limited endpoint

---

## API Usage

### Enroll a biometric

```bash
IMAGE_B64=$(base64 -w0 photo.jpg)

curl -s -X POST http://localhost:8000/api/v1/enroll \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"user_abc123\",
    \"biometric_type\": \"face\",
    \"biometric_data\": \"$IMAGE_B64\",
    \"confidence_threshold\": 0.85
  }"
```

```json
{
  "enrollment_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_abc123",
  "biometric_type": "face",
  "embedding_dimension": 512,
  "model_version": "stub-v0.1",
  "created_at": "2026-04-09T10:30:00Z",
  "message": "Enrollment successful"
}
```

- Returns `409 Conflict` if an active enrollment already exists for that `(user_id, biometric_type)` pair
- Use `PUT /api/v1/enroll/{user_id}/{biometric_type}` to replace an existing enrollment
- Face data must be a valid JPEG or PNG (magic bytes are validated); fingerprint accepts any binary payload
- Maximum biometric payload: **5 MB** (base64-encoded); maximum request body: **10 MB**
- Rate limit: **10 enrollments/min per IP**

### Verify a biometric (1:1)

```bash
curl -s -X POST http://localhost:8000/api/v1/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"user_abc123\",
    \"biometric_type\": \"face\",
    \"biometric_data\": \"$IMAGE_B64\",
    \"confidence_threshold\": 0.85,
    \"return_score\": true
  }"
```

```json
{
  "verified": true,
  "confidence_score": 0.9741,
  "threshold": 0.85,
  "user_id": "user_abc123",
  "biometric_type": "face",
  "model_version": "stub-v0.1",
  "timestamp": "2026-04-09T10:31:00Z",
  "liveness_check_passed": null
}
```

- `verified: false` is returned when `confidence_score < threshold` — no error is raised
- `liveness_check_passed` is `null` in the current implementation (future phase)
- Rate limit: **30 verifications/min per IP**

### Batch verify (1:N)

Match a single probe image against up to 100 enrolled users in one request:

```bash
curl -s -X POST http://localhost:8000/api/v1/verify/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_ids\": [\"user_abc123\", \"user_def456\", \"user_ghi789\"],
    \"biometric_type\": \"face\",
    \"biometric_data\": \"$IMAGE_B64\",
    \"confidence_threshold\": 0.85
  }"
```

```json
{
  "results": [
    {"user_id": "user_abc123", "verified": true,  "confidence_score": 0.9741},
    {"user_id": "user_def456", "verified": false, "confidence_score": 0.3102},
    {"user_id": "user_ghi789", "verified": false, "confidence_score": 0.0}
  ],
  "biometric_type": "face",
  "model_version": "stub-v0.1",
  "timestamp": "2026-04-09T10:32:00Z"
}
```

Users with no enrollment return `verified: false, confidence_score: 0.0` rather than raising an error. All results are audit-logged.

---

## API Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|--------|----------|------|------------|-------------|
| `GET` | `/` | — | — | Service info |
| `GET` | `/api/v1/health` | — | — | Health check |
| `GET` | `/api/v1/ready` | — | — | Readiness check (DB connectivity) |
| `POST` | `/api/v1/auth/token` | API key in body | 20/min | Exchange API key for JWT |
| `POST` | `/api/v1/auth/api-keys` | JWT | — | Create a new API key |
| `GET` | `/api/v1/auth/api-keys` | JWT | — | List your API keys |
| `DELETE` | `/api/v1/auth/api-keys/{key_id}` | JWT | — | Revoke an API key |
| `POST` | `/api/v1/enroll` | JWT | 10/min | Enroll a new biometric |
| `PUT` | `/api/v1/enroll/{user_id}/{biometric_type}` | JWT | 10/min | Replace an existing enrollment |
| `DELETE` | `/api/v1/enroll/{user_id}/{biometric_type}` | JWT | 10/min | Revoke an enrollment |
| `GET` | `/api/v1/enroll/{user_id}` | JWT | — | List active enrollments for a user |
| `POST` | `/api/v1/verify` | JWT | 30/min | 1:1 biometric verification |
| `POST` | `/api/v1/verify/batch` | JWT | 30/min | 1:N batch verify (up to 100 users) |

---

## Database Migrations

We use [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations.

### Migration Commands

```bash
# Run pending migrations
uv run alembic upgrade head

# Create a new migration (after model changes)
uv run alembic revision --autogenerate -m "Description of changes"

# Show current migration state
uv run alembic current

# Show migration history
uv run alembic history

# Downgrade one migration
uv run alembic downgrade -1
```

### Migration Workflow

1. Make changes to SQLAlchemy models in `src/models/`
2. Generate migration: `uv run alembic revision --autogenerate -m "Add field"`
3. Review the generated file in `alembic/versions/`
4. Apply: `uv run alembic upgrade head`

**Current migrations**:
- `001_initial.py` — `users`, `embeddings`, `audit_logs` tables
- `002_add_api_keys.py` — `api_keys` table

---

## Development

### Project Structure

```
biometric-identity-sdk/
├── main.py                    # Entry point (imports src.main.app)
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/
│       ├── 001_initial.py     # users, embeddings, audit_logs
│       └── 002_add_api_keys.py
├── src/
│   ├── api/v1/
│   │   ├── auth.py            # Auth endpoints
│   │   ├── enroll.py          # Enrollment endpoints
│   │   ├── health.py          # Health / readiness
│   │   └── verify.py          # Verification endpoints
│   ├── core/
│   │   ├── config.py          # pydantic-settings configuration
│   │   ├── database.py        # Async SQLAlchemy engine + session
│   │   ├── dependencies.py    # CurrentUserID, DBSession, APIKey
│   │   ├── exceptions.py      # Custom exception hierarchy
│   │   └── rate_limit.py      # Sliding-window in-memory rate limiter
│   ├── models/
│   │   ├── api_key.py
│   │   ├── audit.py
│   │   ├── base.py
│   │   ├── embedding.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── common.py
│   │   ├── enroll.py
│   │   └── verify.py
│   ├── services/
│   │   ├── audit_service.py
│   │   ├── auth_service.py
│   │   ├── embedding_service.py
│   │   ├── enrollment_service.py
│   │   └── verification_service.py
│   └── main.py                # FastAPI app factory
└── tests/
    ├── conftest.py
    ├── test_auth.py            # 10 tests
    ├── test_enroll.py          # 11 tests
    ├── test_health.py          # 2 tests
    ├── test_rate_limit.py      # 5 tests
    └── test_verify.py          # 9 tests
```

### Available Scripts

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Lint
uv run ruff check .

# Auto-fix lint issues
uv run ruff check --fix .

# Format
uv run ruff format .

# Type check
uv run mypy src/

# Run all checks
uv run ruff check . && uv run mypy src/ && uv run pytest

# Run migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "Description"
```

---

## Database Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `User` | User identity records | `external_id`, `created_at`, `is_active` |
| `Embedding` | Biometric embeddings | `user_id`, `biometric_type`, `embedding_vector`, `model_version`, `embedding_dimension` |
| `AuditLog` | Security audit trail | `action`, `success`, `confidence_score`, `ip_address` |
| `ApiKey` | API key credentials | `key_prefix`, `key_hash`, `owner_id`, `label`, `expires_at`, `last_used_at` |

**Privacy**: Raw biometric data is **never stored**. Only 512-dimensional float32 embeddings (serialized as `LargeBinary`) are persisted.

---

## Core Features

| Feature | Status | Notes |
|---------|--------|-------|
| Face biometric enrollment & verification | ✅ Built | JPEG/PNG validated via magic bytes |
| Fingerprint enrollment & verification | ✅ Built | Binary payload, no format restriction |
| API key authentication | ✅ Built | `bsk_live_` prefix, bcrypt-hashed |
| JWT authorization | ✅ Built | HS256, configurable expiry |
| Sliding-window rate limiting | ✅ Built | Per-IP, in-memory, with response headers |
| 1:N batch verification | ✅ Built | Up to 100 users per request |
| Audit logging | ✅ Built | All enroll/verify/update/delete operations |
| Pluggable embedding model | ✅ Built | Stub (SHAKE-256); swap `_extract_raw_embedding` for real ML |
| Cosine similarity scoring | ✅ Built | Pure Python, no pgvector dependency |
| Configurable confidence thresholds | ✅ Built | Per-request override, global default |
| Liveness detection | 🔲 Planned | `liveness_check_passed` field reserved in response |
| Document biometrics (MRZ/OCR/NFC) | 🔲 Planned | `document` type accepted by API; no processing yet |
| pgvector similarity search | 🔲 Planned | Current: Python cosine sim; future: DB-level ANN |

---

## Security Principles

- **Never store raw biometric data** — only 512-dim embeddings
- **Encrypt** sensitive data at rest and in transit
- **Authenticate** all identity endpoints with JWT
- **Audit log** every operation (no PII — only UUIDs, action type, confidence score, IP)
- **Rate limit** token issuance, enrollment, and verification endpoints
- **Hash API keys** with bcrypt — plaintext is shown exactly once at creation

---

## Supported Biometric Types

| Type | Accepted Format | Status |
|------|----------------|--------|
| `face` | JPEG, PNG (magic bytes validated) | ✅ Supported |
| `fingerprint` | Any binary payload | ✅ Supported |
| `document` | Any binary payload | 🔲 Stub only — no MRZ/OCR/NFC processing |

---

## Documentation

- [Phase 1: Foundation](docs/phase-1-foundation.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Agent Guidelines](AGENTS.md)

---

## Future Improvements

- Real ML embedding model (DeepFace, InsightFace, or FaceNet) replacing the SHAKE-256 stub
- pgvector-backed approximate nearest-neighbour search for large-scale 1:N matching
- Liveness detection (anti-spoofing)
- Document biometrics: MRZ parsing, OCR, NFC chip reading
- Multi-modal fusion (face + fingerprint)
- On-premise deployment guide
- Additional regional ID formats
