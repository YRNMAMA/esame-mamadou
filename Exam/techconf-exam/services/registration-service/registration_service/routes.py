"""Registration service HTTP routes."""

from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest

from techconf_common import (
    error_response,
    parse_pagination_params,
    VALIDATION_ERROR,
    NOT_FOUND,
    CONFLICT,
    REFERENCE_NOT_FOUND,
    DEPENDENCY_UNAVAILABLE,
    EVENT_NOT_OPEN,
    ALREADY_REGISTERED,
    EVENT_FULL,
    INVALID_STATUS_TRANSITION,
    METHOD_NOT_ALLOWED,
    MALFORMED_JSON,
)

from registration_service.models import (
    RegistrationCreate,
    RegistrationPatch,
    validate_registration_create,
    validate_registration_patch,
    create_registration,
    update_registration,
    get_stats,
    list_registrations,
    RegistrationStats,
)
from registration_service.client import (
    create_user_service_client,
    create_event_service_client,
    ReferenceNotFoundError,
    DependencyUnavailableError,
)

bp = Blueprint("registrations", __name__, url_prefix="/api/v1/registrations")


def get_repository():
    from flask import current_app
    return current_app.config["repository"]


def get_user_client():
    from flask import current_app
    return current_app.config["user_client"]


def get_event_client():
    from flask import current_app
    return current_app.config["event_client"]


@bp.route("", methods=["POST"])
def create_registration_endpoint():
    """Create a new registration."""
    try:
        data = request.get_json()
        if data is None:
            return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)
    except BadRequest:
        return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)

    reg_create = RegistrationCreate(
        user_id=data.get("user_id", ""),
        event_id=data.get("event_id", ""),
    )

    errors = validate_registration_create(reg_create)
    if errors:
        return error_response(VALIDATION_ERROR, "Validation failed", {"fields": errors}, status=422)

    try:
        registration = create_registration(reg_create, get_repository(), get_user_client(), get_event_client())
    except ValueError as e:
        if str(e) == "REFERENCE_NOT_FOUND":
            return error_response(REFERENCE_NOT_FOUND, "User or event not found", status=422)
        if str(e) == "EVENT_NOT_OPEN":
            return error_response(EVENT_NOT_OPEN, "Event is not open for registration", status=422)
        if str(e) == "ALREADY_REGISTERED":
            return error_response(ALREADY_REGISTERED, "User already registered for this event", status=409)
        if str(e) == "EVENT_FULL":
            return error_response(EVENT_FULL, "Event has reached capacity", status=409)
        if str(e) == "DEPENDENCY_UNAVAILABLE":
            return error_response(DEPENDENCY_UNAVAILABLE, "Dependency service unavailable", status=503)
        raise

    response = jsonify(registration.to_dict())
    response.status_code = 201
    response.headers["Location"] = f"/api/v1/registrations/{registration.id}"
    return response


@bp.route("", methods=["GET"])
def list_registrations_endpoint():
    """List registrations with pagination and filters."""
    page, page_size = parse_pagination_params(request.args)
    user_id = request.args.get("user_id")
    event_id = request.args.get("event_id")
    status = request.args.get("status")

    result = list_registrations(page, page_size, user_id, event_id, status, get_repository())

    result["items"] = [item.to_dict() if hasattr(item, "to_dict") else item for item in result["items"]]
    return jsonify(result)


@bp.route("/stats", methods=["GET"])
def stats_endpoint():
    """Get registration statistics for an event."""
    event_id = request.args.get("event_id")
    if not event_id:
        return error_response(VALIDATION_ERROR, "event_id is required", status=422)

    try:
        stats = get_stats(event_id, get_repository(), get_event_client())
    except ValueError as e:
        if str(e) == "NOT_FOUND":
            return error_response(NOT_FOUND, "Event not found", status=404)
        if str(e) == "DEPENDENCY_UNAVAILABLE":
            return error_response(DEPENDENCY_UNAVAILABLE, "Event service unavailable", status=503)
        raise

    return jsonify({
        "event_id": stats.event_id,
        "capacity": stats.capacity,
        "confirmed": stats.confirmed,
        "available": stats.available,
    })


@bp.route("/<reg_id>", methods=["GET"])
def get_registration_endpoint(reg_id: str):
    """Get a registration by ID."""
    registration = get_repository().get_by_id(reg_id)
    if not registration:
        return error_response(NOT_FOUND, "Registration not found", status=404)
    return jsonify(registration.to_dict())


@bp.route("/<reg_id>", methods=["PUT"])
def put_registration_endpoint(reg_id: str):
    """PUT not allowed."""
    return error_response(METHOD_NOT_ALLOWED, "Method not allowed", status=405)


@bp.route("/<reg_id>", methods=["PATCH"])
def patch_registration_endpoint(reg_id: str):
    """Update registration status."""
    try:
        data = request.get_json()
        if data is None:
            return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)
    except BadRequest:
        return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)

    reg_patch = RegistrationPatch(status=data.get("status", ""))

    errors = validate_registration_patch(reg_patch)
    if errors:
        return error_response(VALIDATION_ERROR, "Validation failed", {"fields": errors}, status=422)

    try:
        registration = update_registration(reg_id, reg_patch, get_repository())
    except ValueError as e:
        if str(e) == "VALIDATION_ERROR":
            return error_response(VALIDATION_ERROR, "Validation failed", status=422)
        if str(e) == "INVALID_STATUS_TRANSITION":
            return error_response(INVALID_STATUS_TRANSITION, "Invalid status transition", status=422)
        raise

    if not registration:
        return error_response(NOT_FOUND, "Registration not found", status=404)

    return jsonify(registration.to_dict())


@bp.route("/<reg_id>", methods=["DELETE"])
def delete_registration_endpoint(reg_id: str):
    """Delete a registration."""
    deleted = get_repository().delete(reg_id)
    if not deleted:
        return error_response(NOT_FOUND, "Registration not found", status=404)
    return "", 204