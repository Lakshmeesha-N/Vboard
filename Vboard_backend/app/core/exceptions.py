class VboardError(Exception):
    """Base exception for Vboard application errors."""

    pass


class AppError(VboardError):
    """Base application error with a safe client-facing message and HTTP status code."""

    def __init__(
        self,
        message: str = "Application error",
        status_code: int = 400,
    ):
        self.status_code = status_code
        super().__init__(message)


class InvalidRequestError(AppError):
    """Raised when request parameters or payload are invalid (400)."""

    def __init__(
        self,
        message: str = "Invalid request parameter",
        status_code: int = 400,
    ):
        super().__init__(message=message, status_code=status_code)


class InvalidAudioError(AppError):
    """Raised when audio payload is invalid, unsupported, or too large (400, 413)."""

    def __init__(
        self,
        message: str = "Invalid or unsupported audio payload",
        status_code: int = 400,
    ):
        super().__init__(message=message, status_code=status_code)


class RateLimitedError(AppError):
    """Raised when Meta API rate limit is encountered (HTTP 429)."""

    def __init__(
        self,
        message: str = "Meta API rate limit exceeded",
        status_code: int = 429,
    ):
        super().__init__(message=message, status_code=status_code)


class MetaApiError(VboardError):
    """Raised when Meta API returns 500 or other unexpected status codes."""

    def __init__(
        self,
        message: str = "Meta API request failed",
        status_code: int | None = None,
    ):
        self.status_code = status_code
        super().__init__(message)
