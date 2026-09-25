"""Shared error response formatting."""

from flask import jsonify


def error_response(code: str, message: str, details: dict = None, status: int = 400):
    """Return a standardized error response tuple (response, status_code)."""
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {}
        }
    }
    return jsonify(payload), status


# Common error codes
VALIDATION_ERROR = "VALIDATION_ERROR"
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
REFERENCE_NOT_FOUND = "REFERENCE_NOT_FOUND"
DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
INVALID_ORGANIZER = "INVALID_ORGANIZER"
EVENT_NOT_OPEN = "EVENT_NOT_OPEN"
ALREADY_REGISTERED = "ALREADY_REGISTERED"
EVENT_FULL = "EVENT_FULL"
MALFORMED_JSON = "MALFORMED_JSON"
METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
NOT_REGISTERED = "NOT_REGISTERED"
FEEDBACK_ALREADY_EXISTS = "FEEDBACK_ALREADY_EXISTS"