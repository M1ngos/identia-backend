from fastapi import HTTPException, status


class BiometricSDKError(Exception):
    def __init__(self, message: str, code: str) -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class UserNotFoundError(BiometricSDKError):
    def __init__(self, user_id: str) -> None:
        super().__init__(
            message=f"User with ID '{user_id}' not found",
            code="USER_NOT_FOUND",
        )


class UserAlreadyExistsError(BiometricSDKError):
    def __init__(self, external_id: str) -> None:
        super().__init__(
            message=f"User with external ID '{external_id}' already exists",
            code="USER_ALREADY_EXISTS",
        )


class EmbeddingNotFoundError(BiometricSDKError):
    def __init__(self, user_id: str, biometric_type: str) -> None:
        super().__init__(
            message=f"No {biometric_type} embedding found for user '{user_id}'",
            code="EMBEDDING_NOT_FOUND",
        )


class EmbeddingAlreadyExistsError(BiometricSDKError):
    def __init__(self, user_id: str, biometric_type: str) -> None:
        super().__init__(
            message=f"User '{user_id}' already has a {biometric_type} embedding",
            code="EMBEDDING_ALREADY_EXISTS",
        )


class VerificationFailedError(BiometricSDKError):
    def __init__(self, confidence: float, threshold: float) -> None:
        super().__init__(
            message=f"Verification failed: confidence {confidence:.2%} below threshold {threshold:.2%}",
            code="VERIFICATION_FAILED",
        )


class LivenessCheckFailedError(BiometricSDKError):
    def __init__(self, reason: str = "Liveness check did not pass") -> None:
        super().__init__(
            message=reason,
            code="LIVENESS_CHECK_FAILED",
        )


class InvalidImageError(BiometricSDKError):
    def __init__(self, reason: str = "Invalid or unsupported image format") -> None:
        super().__init__(
            message=reason,
            code="INVALID_IMAGE",
        )


class AuthenticationError(BiometricSDKError):
    def __init__(self, reason: str = "Invalid or expired authentication token") -> None:
        super().__init__(
            message=reason,
            code="AUTHENTICATION_ERROR",
        )


class InvalidAPIKeyError(BiometricSDKError):
    def __init__(self, reason: str = "Invalid or revoked API key") -> None:
        super().__init__(
            message=reason,
            code="INVALID_API_KEY",
        )


class RateLimitExceededError(BiometricSDKError):
    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(
            message=f"Rate limit exceeded. Retry after {retry_after} seconds",
            code="RATE_LIMIT_EXCEEDED",
        )


def get_http_exception(exc: BiometricSDKError) -> HTTPException:
    if isinstance(exc, RateLimitExceededError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE_LIMIT_EXCEEDED", "message": exc.message},
            headers={"Retry-After": str(exc.retry_after)},
        )

    exception_map: dict[type[BiometricSDKError], tuple[int, str]] = {
        UserNotFoundError: (status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND"),
        UserAlreadyExistsError: (status.HTTP_409_CONFLICT, "USER_ALREADY_EXISTS"),
        EmbeddingNotFoundError: (status.HTTP_404_NOT_FOUND, "EMBEDDING_NOT_FOUND"),
        EmbeddingAlreadyExistsError: (status.HTTP_409_CONFLICT, "EMBEDDING_ALREADY_EXISTS"),
        VerificationFailedError: (status.HTTP_406_NOT_ACCEPTABLE, "VERIFICATION_FAILED"),
        LivenessCheckFailedError: (status.HTTP_406_NOT_ACCEPTABLE, "LIVENESS_CHECK_FAILED"),
        InvalidImageError: (status.HTTP_400_BAD_REQUEST, "INVALID_IMAGE"),
        AuthenticationError: (status.HTTP_401_UNAUTHORIZED, "AUTHENTICATION_ERROR"),
        InvalidAPIKeyError: (status.HTTP_401_UNAUTHORIZED, "INVALID_API_KEY"),
    }

    for exc_type, (status_code, error_code) in exception_map.items():
        if isinstance(exc, exc_type):
            return HTTPException(
                status_code=status_code,
                detail={
                    "code": error_code,
                    "message": exc.message,
                },
            )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "INTERNAL_ERROR",
            "message": "An internal error occurred",
        },
    )
