"""Biometric embedding extraction and similarity service.

This module provides a pluggable stub implementation that can be swapped
for a real ML model (DeepFace, InsightFace, FaceNet, etc.) later.
"""

from __future__ import annotations

import hashlib
import struct

from src.core.config import settings
from src.core.exceptions import InvalidImageError

# Magic-byte signatures for supported image formats
_JPEG_MAGIC: bytes = b"\xff\xd8\xff"
_PNG_MAGIC: bytes = b"\x89PNG\r\n\x1a\n"


def _validate_image_format(image_bytes: bytes, biometric_type: str) -> None:
    """Raise InvalidImageError if the image header doesn't match expected format."""
    if biometric_type == "face":
        if not image_bytes.startswith((_JPEG_MAGIC, _PNG_MAGIC)):
            raise InvalidImageError("Face biometric data must be a valid JPEG or PNG image")
    # fingerprint / document types: any binary data accepted (real model validates)


def serialize_embedding(vector: list[float]) -> bytes:
    """Pack a float list to big-endian float32 bytes.

    Uses struct format ``>Nf`` (big-endian, N 32-bit floats) to avoid a numpy
    dependency.  Each float occupies exactly 4 bytes.
    """
    n = len(vector)
    return struct.pack(f">{n}f", *vector)


def deserialize_embedding(data: bytes) -> list[float]:
    """Unpack big-endian float32 bytes back to a float list."""
    n = len(data) // 4  # float32 = 4 bytes
    unpacked = struct.unpack(f">{n}f", data)
    return [float(v) for v in unpacked]


class EmbeddingService:
    """Pluggable biometric embedding extractor.

    The current implementation is a *deterministic stub* that derives a
    512-dimensional unit vector from image bytes via SHAKE-256.  The same
    image always produces the same embedding, making tests reproducible.

    **Production upgrade path**: replace ``_extract_raw_embedding`` with a
    call to DeepFace / InsightFace / your preferred model.  Keep the
    ``serialize_embedding`` / ``deserialize_embedding`` helpers and the
    ``compute_similarity`` method unchanged.

    Model versions
    ~~~~~~~~~~~~~~
    stub-v0.1 — SHA-256-based deterministic stub (current)
    """

    MODEL_VERSION: str = "stub-v0.1"
    DIMENSION: int = settings.EMBEDDING_DIMENSION  # 512 by default

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def extract(self, image_bytes: bytes, biometric_type: str) -> list[float]:
        """Extract a biometric embedding from raw image bytes.

        Args:
            image_bytes: Raw (decoded) image data — JPEG or PNG for face type.
            biometric_type: One of ``"face"``, ``"fingerprint"``, ``"document"``.

        Returns:
            L2-normalised embedding vector of length :attr:`DIMENSION`.

        Raises:
            InvalidImageError: Empty data, or format unsupported for ``face``.
        """
        if not image_bytes:
            raise InvalidImageError("Empty image data provided")
        _validate_image_format(image_bytes, biometric_type)
        return self._extract_raw_embedding(image_bytes)

    def compute_similarity(
        self,
        embedding_a: list[float],
        embedding_b: list[float],
    ) -> float:
        """Return the cosine similarity between two embedding vectors.

        Args:
            embedding_a: First embedding (any L2 norm).
            embedding_b: Second embedding (any L2 norm).

        Returns:
            Score in ``[0.0, 1.0]`` — 1.0 = identical direction,
            0.0 = orthogonal or opposite (treated as no match).

        Raises:
            ValueError: If the two vectors have different lengths.
        """
        if len(embedding_a) != len(embedding_b):
            raise ValueError(
                f"Embedding dimension mismatch: {len(embedding_a)} vs {len(embedding_b)}"
            )

        # Explicit float casts ensure mypy infers float (not Any) from sum()
        dot: float = float(sum(a * b for a, b in zip(embedding_a, embedding_b, strict=False)))
        norm_a: float = float(sum(a * a for a in embedding_a)) ** 0.5
        norm_b: float = float(sum(b * b for b in embedding_b)) ** 0.5

        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0

        raw_sim: float = dot / (norm_a * norm_b)
        # Clamp to [0, 1] — negative cosine similarity (opposing vectors) → 0
        return max(0.0, min(1.0, raw_sim))

    # ------------------------------------------------------------------ #
    # Internal stub — replace with real ML inference
    # ------------------------------------------------------------------ #

    def _extract_raw_embedding(self, image_bytes: bytes) -> list[float]:
        """Deterministic stub: SHAKE-256 → unsigned ints → L2-normalised floats.

        SHAKE-256 outputs ``DIMENSION × 4`` bytes, unpacked as unsigned 32-bit
        integers, then divided by their L2 norm to produce a unit vector.
        """
        n_bytes = self.DIMENSION * 4  # 512 dims × 4 bytes/float32 = 2048 bytes
        h = hashlib.shake_256(image_bytes)
        raw: bytes = h.digest(n_bytes)

        unpacked = struct.unpack(f">{self.DIMENSION}I", raw)
        floats: list[float] = [float(v) for v in unpacked]

        norm = sum(f * f for f in floats) ** 0.5
        if norm < 1e-10:
            raise InvalidImageError("Could not derive a valid embedding from the image")

        return [f / norm for f in floats]


# ---------------------------------------------------------------------------
# Module-level singleton + FastAPI dependency helper
# ---------------------------------------------------------------------------

embedding_service: EmbeddingService = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    """FastAPI dependency that returns the module-level singleton."""
    return embedding_service
