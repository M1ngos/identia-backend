# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development server (auto-reload)
uv run fastapi dev main.py

# Tests
uv run pytest
uv run pytest tests/test_api.py -v          # specific file
uv run pytest -k "test_enroll" -v           # by name pattern
uv run pytest --cov=src --cov-report=html   # with coverage

# Lint / format / typecheck
uv run ruff check .
uv run ruff check --fix .
uv run ruff format .
uv run mypy src/

# Run all checks
uv run ruff check . && uv run mypy src/ && uv run pytest

# Database migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "Description"
uv run alembic downgrade -1
uv run alembic current
```

## Architecture

**FastAPI async service** backed by PostgreSQL with pgvector for biometric embedding similarity search. Uses SQLAlchemy async ORM with Alembic migrations.

### Entry Point Flow
`main.py` (project root) → imports `src/main.py` FastAPI app → `lifespan` initializes DB via `src/core/database.py` → routers registered under `settings.API_V1_PREFIX` (`/api/v1`).

### Key Layers

- **`src/core/config.py`** — `Settings` via `pydantic-settings` with `.env` file. Access via `settings` singleton. Key config: `DATABASE_URL`, `SECRET_KEY`, `DEFAULT_CONFIDENCE_THRESHOLD`, `EMBEDDING_DIMENSION`.
- **`src/core/database.py`** — Async SQLAlchemy engine + `async_session_maker`. `Base` (declarative base) imported by all models. `get_db()` is the FastAPI dependency for sessions (auto-commit/rollback).
- **`src/core/exceptions.py`** — Domain exception hierarchy rooted at `BiometricSDKError`. `get_http_exception()` maps them to HTTP status codes. The app-level handler in `src/main.py` calls this for uniform error responses (`{"code": "...", "message": "..."}`).
- **`src/models/`** — SQLAlchemy ORM models: `User` (external_id as the caller-supplied key), `Embedding` (stores serialized embedding vectors as `LargeBinary`; **never raw biometric data**), `AuditLog`.
- **`src/schemas/`** — Pydantic v2 request/response models. `BiometricType` enum (`face`, `fingerprint`, `document`). `biometric_data` fields are Base64-encoded and validated on input.
- **`src/api/v1/`** — APIRouter modules. Currently only `health.py` (stubs for `/health`, `/ready`). New endpoints (`/enroll`, `/verify`) are planned here.
- **`src/services/`** — Business logic layer (empty; to be implemented).

### Data Model Notes
- `User.external_id` is the caller-controlled identifier (your system's user ID); internal `id` is a UUID primary key.
- `Embedding.embedding_vector` is `LargeBinary` — the pgvector similarity search is planned but not yet wired.
- `AuditLog` links to `User` and tracks all enrollment/verify/delete actions with `confidence_score` and `ip_address`.

### Adding New Endpoints
1. Create route file in `src/api/v1/`
2. Add service logic in `src/services/`
3. Register router in `src/main.py` with `app.include_router(..., prefix=settings.API_V1_PREFIX)`
4. Raise domain exceptions from `src/core/exceptions.py` — they map automatically to HTTP responses

## Code Style
- Python 3.12+, strict mypy, ruff line-length 100
- Always use type hints; use `X | None` union syntax (not `Optional[X]`)
- Pydantic v2 patterns: `ConfigDict`, `model_validator`, `field_validator` with `@classmethod`
- Async throughout — all route handlers and DB calls must be `async def`
