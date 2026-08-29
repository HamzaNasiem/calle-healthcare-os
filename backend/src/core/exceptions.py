from typing import Any


class APIException(Exception):
    """
    Custom API exception. Call as:
        raise APIException("ERROR_CODE", "Human readable message.", 400)
    Which is the order used throughout the codebase.
    """
    def __init__(
        self,
        error_code: str,       # e.g. "AUTH_INVALID_CREDENTIALS"
        message: str,          # e.g. "Invalid email or password."
        status_code: int = 400, # HTTP status code
        details: Any | None = None
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or []
        super().__init__(self.message)

class ResourceNotFoundException(APIException):
    def __init__(self, message: str = "The requested resource was not found.", details: Any | None = None):
        super().__init__(error_code="NOT_FOUND", message=message, status_code=404, details=details)

class UnauthorizedException(APIException):
    def __init__(self, message: str = "Invalid or expired authentication token.", details: Any | None = None):
        super().__init__(error_code="UNAUTHORIZED", message=message, status_code=401, details=details)

class ForbiddenException(APIException):
    def __init__(self, message: str = "You do not have permission to perform this action.", details: Any | None = None):
        super().__init__(error_code="FORBIDDEN", message=message, status_code=403, details=details)

class ValidationException(APIException):
    def __init__(self, message: str = "Validation error.", details: Any | None = None):
        super().__init__(error_code="VALIDATION_ERROR", message=message, status_code=422, details=details)

class RateLimitException(APIException):
    def __init__(self, message: str = "Too many requests. Please try again later.", details: Any | None = None):
        super().__init__(error_code="RATE_LIMIT_EXCEEDED", message=message, status_code=429, details=details)

class ServerErrorException(APIException):
    def __init__(self, message: str = "An unexpected error occurred.", details: Any | None = None):
        super().__init__(error_code="INTERNAL_ERROR", message=message, status_code=500, details=details)
