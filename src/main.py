from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse

from src.api.v1.auth import router as auth_router
from src.api.v1.enroll import router as enroll_router
from src.api.v1.health import router as health_router
from src.api.v1.verify import router as verify_router
from src.core.config import settings
from src.core.exceptions import BiometricSDKError, get_http_exception


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.db_initialized = False

    with suppress(Exception):
        from src.core.database import close_db, init_db

        await init_db()
        app.state.db_initialized = True

    yield

    if app.state.db_initialized:
        with suppress(Exception):
            from src.core.database import close_db

            await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A plug-and-play identity verification system using biometrics",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


@app.exception_handler(BiometricSDKError)
async def biometric_exception_handler(
    request: Request,
    exc: BiometricSDKError,
) -> JSONResponse:
    http_exc = get_http_exception(exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=http_exc.detail,
        headers=http_exc.headers,
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred" if not settings.DEBUG else str(exc),
        },
    )


app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(enroll_router, prefix=settings.API_V1_PREFIX)
app.include_router(verify_router, prefix=settings.API_V1_PREFIX)


@app.middleware("http")
async def limit_body_size(
    request: Request, call_next: RequestResponseEndpoint
) -> StarletteResponse:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "code": "REQUEST_TOO_LARGE",
                "message": (
                    f"Request body exceeds maximum allowed size of "
                    f"{settings.MAX_REQUEST_BODY_BYTES} bytes"
                ),
            },
        )
    return await call_next(request)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
