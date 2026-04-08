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

## Core Features

| Feature | Description |
|---------|-------------|
| Face-based identity verification | Biometric face matching with high accuracy |
| Document parsing | MRZ/OCR for passports and national IDs |
| Embedding-based matching | Vector search for fast similarity comparison |
| Liveness detection | Spoofing prevention with anti-presentation attacks |
| Configurable thresholds | Customizable confidence scoring |
| Modular architecture | Swappable ML models and components |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                    │
│                   /enroll    /verify                        │
└──────────────────────────┬────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐
│  ML Services  │  │   Database    │  │   Encrypted Storage   │
│  (Embeddings) │  │ (PostgreSQL + │  │   (Documents/Raw)     │
│               │  │   pgvector)   │  │                       │
└───────────────┘  └───────────────┘  └───────────────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
              ┌─────────────────────────┐
              │    Cache (Redis)        │
              │  Session & Performance  │
              └─────────────────────────┘
```

### Components

- **API Layer**: FastAPI service exposing `/enroll` and `/verify` endpoints
- **ML Services**: Feature extraction using pretrained models
- **Database**: PostgreSQL + pgvector for storing embeddings and metadata
- **Cache**: Redis for session and performance optimization
- **Storage**: Optional encrypted storage for documents/raw inputs
- **Workers**: Async processing for heavy ML tasks

---

## Workflow

### Enroll

1. Capture biometric + optional document
2. Extract features (embeddings)
3. Store templates linked to a user identity

### Verify

1. Capture new biometric sample
2. Extract features
3. Compare against stored templates
4. Return confidence score and decision

---

## SDK

Client SDKs wrap API calls into simple methods:

```python
# Python SDK
from biometric_sdk import BiometricClient

client = BiometricClient(api_key="your-key")
client.enroll(user_id="user123", biometric_data=image_bytes)
client.verify(biometric_data=image_bytes)
```

**Supported languages**: Python, Kotlin, JavaScript (extendable)

---

## Security Principles

- **Never store raw biometric data** — only embeddings
- **Encrypt** sensitive data at rest and in transit
- **Authenticate** all requests with JWT/OAuth
- **Audit log** all identity operations (no PII in logs)
- **Liveness detection** to prevent spoofing attacks

---

## Supported Identity Sources

| Source | Status |
|--------|--------|
| Face images | ✅ Primary |
| Fingerprints | ✅ Extensible |
| Passports (MRZ/NFC) | ✅ Supported |
| National IDs (OCR) | ✅ Supported |

---

## Non-Goals (initially)

- No full identity governance system
- No manual identity review workflows
- No hardware-specific fingerprint drivers (abstracted later)

---

## Future Improvements

- Multi-modal fusion (face + fingerprint + document scoring)
- Advanced liveness detection (active challenges)
- On-device inference SDK
- On-premise deployment mode
- Additional regional ID formats

---

## Quick Start

```bash
# Install dependencies
uv sync

# Run the server
uv run fastapi dev main.py
```

---

This system provides a **unified, secure, and extensible** way to manage digital identity using biometrics and documents, exposed through simple APIs and SDKs that can be integrated into any application.
