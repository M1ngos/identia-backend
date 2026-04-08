# Agent Guidelines for Biometric Identity SDK

## Project Overview

A plug-and-play identity verification system using FastAPI for biometric enrollment and verification (face, fingerprint, documents).

## Environment Setup

- **Python**: 3.12+
- **Package Manager**: `uv`
- **Dependencies**: See `pyproject.toml`

### Virtual Environment
```bash
# Activate existing venv
source .venv/bin/activate

# Create new venv
uv venv

# Install dependencies
uv sync
```

## Development Commands

### Running the Application
```bash
# Standard FastAPI development server (recommended)
uv run fastapi dev main.py

# Or using uvicorn directly
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run with custom host/port
uv run fastapi dev main.py --host 0.0.0.0 --port 8080
```

### Testing
```bash
# Install test dependencies first (add pytest to pyproject.toml if needed)
uv add --dev pytest pytest-asyncio httpx

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_api.py -v

# Run tests matching a pattern
uv run pytest -k "test_enroll" -v

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run tests in watch mode (requires pytest-watch)
uv run ptw  # pytest-watch
```

### Linting & Type Checking
```bash
# Install linting tools
uv add --dev ruff mypy

# Run ruff linter
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Run mypy type checker
uv run mypy src/

# Format code
uv add --dev ruff
uv run ruff format .
```

### Code Quality
```bash
# Run all checks (lint + typecheck + tests)
uv run ruff check . && uv run mypy src/ && uv run pytest

# Sort imports
uv run ruff check --select=I --fix .
```

## Project Structure

```
biometric-identity-sdk/
├── main.py              # FastAPI app entry point
├── pyproject.toml       # Project configuration
├── uv.lock             # Locked dependencies
├── src/                # Source code (create if needed)
│   ├── api/            # API routes
│   ├── core/           # Core functionality
│   ├── models/         # Pydantic models
│   ├── services/       # Business logic
│   └── schemas/        # Request/Response schemas
└── tests/              # Test files
```

## Code Style Guidelines

### Python Version
- Target Python 3.12+
- Use modern syntax (structural pattern matching, `|` union types, etc.)

### Type Hints
- **Always use type hints** for function parameters and return values
- Use `Optional[X]` or `X | None` instead of bare `X`
- Use `list[X]`, `dict[K, V]`, `set[X]` instead of lowercase alternatives
- Avoid `Any` except in truly untyped contexts

```python
# Good
def verify_biometric(user_id: str, sample: bytes) -> VerificationResult:
    ...

# Avoid
def verify_biometric(user_id, sample):
    ...
```

### Imports
- Use absolute imports from package root
- Group imports: stdlib → third-party → local
- Sort alphabetically within groups
- Use `from` imports for submodules

```python
# Standard library
from datetime import datetime
from typing import Optional

# Third-party
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

# Local
from app.models.user import User
from app.schemas import EnrollmentRequest
```

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `BiometricEnrollment`)
- **Functions/methods**: `snake_case` (e.g., `verify_identity`)
- **Variables**: `snake_case` (e.g., `confidence_score`)
- **Constants**: `SCREAMING_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`)
- **Private members**: `_leading_underscore`
- **Type variables**: `PascalCase` (e.g., `T`, `UserModel`)

### Pydantic Models
- Use `BaseModel` from `pydantic`
- Use `Field` for validation and documentation
- Use `ConfigDict` for model configuration
- Prefer `model_validator` over `validator` (Pydantic v2)

```python
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class BiometricEnrollment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    
    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    biometric_type: str = Field(..., pattern="^(face|fingerprint|document)$")
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    created_at: Optional[datetime] = None
```

### FastAPI Patterns
- Use `APIRouter` for grouping routes
- Use `Depends` for dependency injection
- Use `BackgroundTasks` for async operations
- Return appropriate HTTP status codes
- Use `Response` parameter for headers/cookies

```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/v1", tags=["enrollment"])

@router.post("/enroll", status_code=status.HTTP_201_CREATED)
async def enroll_biometric(
    request: EnrollmentRequest,
    current_user: User = Depends(get_current_user),
) -> EnrollmentResponse:
    ...
```

### Error Handling
- Use `HTTPException` for HTTP errors
- Create custom exception classes for domain errors
- Use `try/except` sparingly, prefer validation
- Log errors with appropriate context

```python
from fastapi import HTTPException, status

# In route
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"User {user_id} not found"
)

# Custom exception
class BiometricVerificationError(Exception):
    def __init__(self, message: str, confidence: float):
        self.message = message
        self.confidence = confidence
```

### Async/Await
- Use `async def` for FastAPI route handlers
- Use `await` for I/O operations
- Use `asyncio` for concurrent operations
- Don't mix sync and async code unnecessarily

### Security Considerations
- **Biometric Data**: Never store raw biometric data; store embeddings only
- **Encryption**: Encrypt sensitive data at rest and in transit
- **Authentication**: Use JWT/OAuth for API authentication
- **Validation**: Validate all input rigorously
- **Logging**: Log identity operations for audit trail (no PII in logs)
- **Rate Limiting**: Implement rate limiting on sensitive endpoints

## Testing Guidelines

### Test Structure
```python
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_enroll_endpoint(client: AsyncClient):
    response = await client.post("/enroll", json={
        "user_id": "test_user",
        "biometric_type": "face"
    })
    assert response.status_code == 201
```

### Test File Naming
- `test_*.py` for test files
- `*_test.py` also accepted
- `conftest.py` for shared fixtures

## Documentation

- Use docstrings for modules, classes, and public functions
- Follow Google/NumPy docstring format
- Document parameters and return types in docstrings

```python
def verify_identity(
    user_id: str,
    biometric_sample: bytes,
    threshold: float = 0.85,
) -> bool:
    """Verify user identity using biometric sample.
    
    Args:
        user_id: Unique identifier for the user.
        biometric_sample: Raw or processed biometric data.
        threshold: Minimum confidence score for verification.
    
    Returns:
        True if verification passes, False otherwise.
    """
```

## Git Workflow

- Use conventional commit messages: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Keep commits focused and atomic
- Write meaningful commit descriptions
- Never commit secrets or credentials
- Use `.env` for local environment variables (not committed)

## Common Issues

### Import Errors
If you get import errors, ensure:
1. `.venv` is activated: `source .venv/bin/activate`
2. Dependencies are installed: `uv sync`
3. Python path is set correctly

### Type Checking Failures
- Use `reveal_type()` to debug unknown types
- Add `# type: ignore` only as last resort with comment explaining why
