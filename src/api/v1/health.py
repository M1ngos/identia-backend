from fastapi import APIRouter

from src.schemas.common import HealthResponse, ReadyResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        200: {"description": "Service is healthy"},
    },
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="biometric-identity-sdk",
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"},
    },
)
async def readiness_check() -> ReadyResponse:
    return ReadyResponse(
        status="ready",
        database="connected",
    )
