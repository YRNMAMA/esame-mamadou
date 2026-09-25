"""TechConf shared utilities."""

from .errors import (
    error_response,
    VALIDATION_ERROR,
    NOT_FOUND,
    CONFLICT,
    REFERENCE_NOT_FOUND,
    DEPENDENCY_UNAVAILABLE,
    INVALID_STATUS_TRANSITION,
    EMAIL_ALREADY_EXISTS,
    INVALID_ORGANIZER,
    EVENT_NOT_OPEN,
    ALREADY_REGISTERED,
    EVENT_FULL,
    MALFORMED_JSON,
    METHOD_NOT_ALLOWED,
    NOT_REGISTERED,
    FEEDBACK_ALREADY_EXISTS,
)
from .pagination import paginate, parse_pagination_params
from .http_client import ServiceClient, get_service_url, ReferenceNotFoundError, DependencyUnavailableError

__all__ = [
    "error_response",
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "CONFLICT",
    "REFERENCE_NOT_FOUND",
    "DEPENDENCY_UNAVAILABLE",
    "INVALID_STATUS_TRANSITION",
    "EMAIL_ALREADY_EXISTS",
    "INVALID_ORGANIZER",
    "EVENT_NOT_OPEN",
    "ALREADY_REGISTERED",
    "EVENT_FULL",
    "MALFORMED_JSON",
    "METHOD_NOT_ALLOWED",
    "NOT_REGISTERED",
    "FEEDBACK_ALREADY_EXISTS",
    "paginate",
    "parse_pagination_params",
    "ServiceClient",
    "get_service_url",
    "ReferenceNotFoundError",
    "DependencyUnavailableError",
]