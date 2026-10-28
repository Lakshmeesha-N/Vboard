class VboardError(Exception):
    """Base exception for Vboard application errors."""
    pass


class InvalidAudioError(VboardError):
    """Raised when audio payload is invalid, unsupported, or too large (400, 413)."""

    def __init__(self, message: str = "Invalid or unsupported audio payload"):
        super().__init__(message)


class RateLimitedError(VboardError):
    """Raised when Meta API rate limit is encountered (HTTP 429)."""

    def __init__(self, message: str = "Meta API rate limit exceeded"):
        super().__init__(message)


class MetaApiError(VboardError):
    """Raised when Meta API returns 500 or other unexpected status codes."""

    def __init__(
        self,
        message: str = "Meta API request failed",
        status_code: int | None = None,
    ):
        self.status_code = status_code
        super().__init__(message)
