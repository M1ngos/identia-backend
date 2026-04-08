# Biometric Identity Platform

A plug-and-play identity verification system that enables applications to enroll and verify users using biometrics (face, fingerprint) and identity documents (e.g., passports, national IDs).

It abstracts the complexity of biometric processing behind simple APIs and SDKs.

---

## Goals

- Provide a simple API for identity enrollment and verification
- Support multiple biometric modalities (face, fingerprint, documents)
- Ensure secure, scalable, and privacy-aware identity handling
- Offer easy integration via lightweight SDKs

---

## Quick Start

### 1. Prerequisites

- Python 3.12+
- PostgreSQL 15+ (with pgvector extension)
- [uv](https://github.com/astral-sh/uv) package manager

### 2. Clone & Setup

```bash
# Clone the repository
git clone <repository-url>
cd biometric-identity-sdk

# Create virtual environment
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate     # Windows

# Install dependencies
uv sync
```

### 3. Database Setup

```bash
# Create PostgreSQL database
psql -U postgres -c "CREATE DATABASE biometric_sdk;"

# Enable pgvector extension (required for embedding similarity search)
psql -U postgres -d biometric_sdk -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run database migrations
uv run alembic upgrade head
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Required settings in `.env`**:
```env
SECRET_KEY=your-secure-random-string
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/biometric_sdk
```

**Optional settings**:
```env
DEBUG=false
DEFAULT_CONFIDENCE_THRESHOLD=0.85
RATE_LIMIT_PER_MINUTE=60
```

### 5. Run

```bash
# Development mode (with auto-reload)
uv run fastapi dev main.py

# Production mode
uv run fastapi run main.py
```

The API will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Database Migrations

We use [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations.

### Migration Commands

```bash
# Run pending migrations
uv run alembic upgrade head

# Create a new migration (after model changes)
uv run alembic revision --autogenerate -m "Description of changes"

# Create empty migration
uv run alembic revision -m "Description"

# Show current migration
uv run alembic current

# Show migration history
uv run alembic history

# Downgrade one migration
uv run alembic downgrade -1

# Downgrade to specific revision
uv run alembic downgrade <revision>

# Upgrade to specific revision
uv run alembic upgrade <revision>
```

### Migration Workflow

1. Make changes to SQLAlchemy models in `src/models/`
2. Generate migration: `uv run alembic revision --autogenerate -m "Add field"`
3. Review generated migration in `alembic/versions/`
4. Apply: `uv run alembic upgrade head`

---

## Development

### Project Structure

```
biometric-identity-sdk/
├── src/
│   ├── api/
│   │   └── v1/
│   │       └── health.py       # Health check endpoints
│   ├── core/
│   │   ├── config.py          # Settings & configuration
│   │   ├── database.py        # Async SQLAlchemy setup
│   │   ├── dependencies.py    # FastAPI dependencies
│   │   └── exceptions.py      # Custom exceptions
│   ├── models/
│   │   ├── user.py            # User model
│   │   ├── embedding.py       # Biometric embedding model
│   │   └── audit.py           # Audit log model
│   ├── schemas/
│   │   ├── common.py          # Shared schemas & enums
│   │   ├── enroll.py          # Enrollment request/response
│   │   └── verify.py          # Verification request/response
│   └── main.py                # FastAPI application
├── alembic/
│   ├── env.py                 # Alembic configuration
│   ├── versions/              # Migration files
│   └── script.py.mako         # Migration template
├── tests/                     # Test files
├── docs/                      # Documentation
├── pyproject.toml             # Project configuration
├── alembic.ini                # Alembic settings
├── .env.example               # Environment template
└── README.md
```

### Available Scripts

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Lint code
uv run ruff check .

# Auto-fix lint issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type check
uv run mypy src/

# Run all checks
uv run ruff check . && uv run mypy src/ && uv run pytest

# Database migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "Description"
```

---

## Database Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `User` | User identity records | `external_id`, `created_at`, `is_active` |
| `Embedding` | Biometric embeddings | `user_id`, `biometric_type`, `embedding_vector`, `model_version` |
| `AuditLog` | Security audit trail | `action`, `success`, `confidence_score`, `ip_address` |

**Security**: Raw biometric data is NEVER stored — only embeddings (feature vectors).

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/api/v1/health` | GET | Health check |
| `/api/v1/ready` | GET | Readiness check |
| `/api/v1/enroll` | POST | Enroll biometric |
| `/api/v1/verify` | POST | Verify biometric |

---

## Core Features

| Feature | Description |
|---------|-------------|
| Face-based identity verification | Biometric face matching |
| Document parsing | MRZ/OCR for passports and IDs |
| Embedding-based matching | Vector search via pgvector |
| Liveness detection | Anti-spoofing measures |
| Configurable thresholds | Customizable confidence scores |
| Modular architecture | Swappable ML models |

---

## Security Principles

- **Never store raw biometric data** — only embeddings
- **Encrypt** sensitive data at rest and in transit
- **Authenticate** all requests with JWT/API keys
- **Audit log** all identity operations (no PII)
- **Rate limit** sensitive endpoints

---

## Supported Identity Sources

| Source | Status |
|--------|--------|
| Face images | ✅ Primary |
| Fingerprints | ✅ Extensible |
| Passports (MRZ/NFC) | ✅ Supported |
| National IDs (OCR) | ✅ Supported |

---

## Documentation

- [Phase 1: Foundation](docs/phase-1-foundation.md)
- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [Agent Guidelines](AGENTS.md)

---

## Future Improvements

- Multi-modal fusion (face + fingerprint + document)
- Advanced liveness detection
- On-device inference SDK
- On-premise deployment
- Additional regional ID formats
