"""Event service HTTP routes."""

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
    INVALID_ORGANIZER,
    INVALID_STATUS_TRANSITION,
    MALFORMED_JSON,
)

from event_service.models import (
    EventCreate,
    EventUpdate,
    validate_event_create,
    validate_event_update,
    create_event,
    update_event,
    list_events,
)
from event_service.client import (
    create_user_service_client,
    ReferenceNotFoundError,
    DependencyUnavailableError,
)

bp = Blueprint("events", __name__, url_prefix="/api/v1/events")


def get_repository():
    """Get repository from app config."""
    from flask import current_app
    return current_app.config["repository"]


def get_user_client():
    """Get user service client from app config."""
    from flask import current_app
    return current_app.config["user_client"]


@bp.route("", methods=["POST"])
def create_event_endpoint():
    """Create a new event."""
    try:
        data = request.get_json()
        if data is None:
            return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)
    except BadRequest:
        return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)

    event_create = EventCreate(
        title=data.get("title", ""),
        description=data.get("description"),
        organizer_id=data.get("organizer_id", ""),
        venue=data.get("venue", ""),
        city=data.get("city", ""),
        start_date=data.get("start_date", ""),
        end_date=data.get("end_date", ""),
        capacity=data.get("capacity", 0),
        price=data.get("price", 0.0),
        status=data.get("status", "draft"),
    )

    errors = validate_event_create(event_create)
    if errors:
        return error_response(VALIDATION_ERROR, "Validation failed", {"fields": errors}, status=422)

    try:
        event = create_event(event_create, get_repository(), get_user_client())
    except ValueError as e:
        if str(e) == "REFERENCE_NOT_FOUND":
            return error_response(REFERENCE_NOT_FOUND, "Organizer not found", status=422)
        if str(e) == "INVALID_ORGANIZER":
            return error_response(INVALID_ORGANIZER, "Organizer must have role=organizer", status=422)
        if str(e) == "DEPENDENCY_UNAVAILABLE":
            return error_response(DEPENDENCY_UNAVAILABLE, "User service unavailable", status=503)
        raise

    response = jsonify(event.to_dict())
    response.status_code = 201
    response.headers["Location"] = f"/api/v1/events/{event.id}"
    return response


@bp.route("", methods=["GET"])
def list_events_endpoint():
    """List events with pagination and filters."""
    page, page_size = parse_pagination_params(request.args)
    status = request.args.get("status")
    city = request.args.get("city")

    result = list_events(page, page_size, status, city, get_repository())

    # Convert Event objects to dicts
    result["items"] = [item.to_dict() if hasattr(item, "to_dict") else item for item in result["items"]]
    return jsonify(result)


@bp.route("/<event_id>", methods=["GET"])
def get_event_endpoint(event_id: str):
    """Get an event by ID."""
    event = get_repository().get_by_id(event_id)
    if not event:
        return error_response(NOT_FOUND, "Event not found", status=404)
    return jsonify(event.to_dict())


@bp.route("/<event_id>", methods=["PUT"])
def replace_event_endpoint(event_id: str):
    """Replace an event (full update)."""
    try:
        data = request.get_json()
        if data is None:
            return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)
    except BadRequest:
        return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)

    required = ["title", "organizer_id", "venue", "city", "start_date", "end_date", "capacity", "price"]
    missing = [f for f in required if f not in data or data[f] is None or data[f] == ""]
    if missing:
        return error_response(VALIDATION_ERROR, "Missing required fields", {"fields": missing}, status=422)

    event_create = EventCreate(
        title=data["title"],
        description=data.get("description"),
        organizer_id=data["organizer_id"],
        venue=data["venue"],
        city=data["city"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        capacity=data["capacity"],
        price=data["price"],
        status=data.get("status", "draft"),
    )

    errors = validate_event_create(event_create)
    if errors:
        return error_response(VALIDATION_ERROR, "Validation failed", {"fields": errors}, status=422)

    existing = get_repository().get_by_id(event_id)
    if not existing:
        return error_response(NOT_FOUND, "Event not found", status=404)

    try:
        repo = get_repository()
        repo.delete(event_id)

        now = existing.created_at
        from datetime import datetime, timezone
        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        from event_service.models import Event
        event = Event(
            id=event_id,
            title=event_create.title.strip(),
            description=event_create.description.strip() if event_create.description else None,
            organizer_id=event_create.organizer_id,
            venue=event_create.venue.strip(),
            city=event_create.city.strip(),
            start_date=event_create.start_date,
            end_date=event_create.end_date,
            capacity=event_create.capacity,
            price=float(event_create.price),
            status=event_create.status,
            created_at=now,
            updated_at=updated_at,
        )

        # Validate organizer
        user_client = get_user_client()
        try:
            status_code, user = user_client.get_user(event.organizer_id)
            if user.get("role") != "organizer":
                return error_response(INVALID_ORGANIZER, "Organizer must have role=organizer", status=422)
        except ReferenceNotFoundError:
            return error_response(REFERENCE_NOT_FOUND, "Organizer not found", status=422)
        except DependencyUnavailableError:
            return error_response(DEPENDENCY_UNAVAILABLE, "User service unavailable", status=503)

        repo.create(event)
    except ValueError as e:
        if str(e) == "REFERENCE_NOT_FOUND":
            return error_response(REFERENCE_NOT_FOUND, "Organizer not found", status=422)
        if str(e) == "INVALID_ORGANIZER":
            return error_response(INVALID_ORGANIZER, "Organizer must have role=organizer", status=422)
        if str(e) == "DEPENDENCY_UNAVAILABLE":
            return error_response(DEPENDENCY_UNAVAILABLE, "User service unavailable", status=503)
        raise

    return jsonify(event.to_dict())


@bp.route("/<event_id>", methods=["PATCH"])
def patch_event_endpoint(event_id: str):
    """Partially update an event."""
    try:
        data = request.get_json()
        if data is None:
            return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)
    except BadRequest:
        return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)

    event_update = EventUpdate(
        title=data.get("title"),
        description=data.get("description"),
        organizer_id=data.get("organizer_id"),
        venue=data.get("venue"),
        city=data.get("city"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        capacity=data.get("capacity"),
        price=data.get("price"),
        status=data.get("status"),
    )

    errors = validate_event_update(event_update)
    if errors:
        return error_response(VALIDATION_ERROR, "Validation failed", {"fields": errors}, status=422)

    try:
        event = update_event(event_id, event_update, get_repository(), get_user_client())
    except ValueError as e:
        if str(e) == "VALIDATION_ERROR":
            return error_response(VALIDATION_ERROR, "Validation failed", status=422)
        if str(e) == "REFERENCE_NOT_FOUND":
            return error_response(REFERENCE_NOT_FOUND, "Organizer not found", status=422)
        if str(e) == "INVALID_ORGANIZER":
            return error_response(INVALID_ORGANIZER, "Organizer must have role=organizer", status=422)
        if str(e) == "INVALID_STATUS_TRANSITION":
            return error_response(INVALID_STATUS_TRANSITION, "Invalid status transition", status=422)
        if str(e) == "DEPENDENCY_UNAVAILABLE":
            return error_response(DEPENDENCY_UNAVAILABLE, "User service unavailable", status=503)
        raise

    if not event:
        return error_response(NOT_FOUND, "Event not found", status=404)

    return jsonify(event.to_dict())


@bp.route("/<event_id>", methods=["DELETE"])
def delete_event_endpoint(event_id: str):
    """Delete an event."""
    deleted = get_repository().delete(event_id)
    if not deleted:
        return error_response(NOT_FOUND, "Event not found", status=404)
    return "", 204