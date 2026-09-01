"""Domain-level exceptions, translated to HTTP responses at the API boundary."""


class DomainError(Exception):
    """Base class for all domain-level errors."""

    code = "DOMAIN_ERROR"
    status_code = 400


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    status_code = 400


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"
    status_code = 401


class ForbiddenError(DomainError):
    code = "FORBIDDEN"
    status_code = 403


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(DomainError):
    code = "CONFLICT"
    status_code = 409
