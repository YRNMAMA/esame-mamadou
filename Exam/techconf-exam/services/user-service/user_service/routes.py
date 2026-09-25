"""User service HTTP routes."""

from flask import Blueprint, request, jsonify
from werkzeug.exceptions import BadRequest

from techconf_common import (
    error_response,
    parse_pagination_params,
    VALIDATION_ERROR,
    NOT_FOUND,
    CONFLICT,
    EMAIL_ALREADY_EXISTS,
    MALFORMED_JSON,
)

from user_service.models import (
    UserCreate,
    UserUpdate,
    User,
    validate_user_create,
    validate_user_update,
    create_user,
    update_user,
    list_users,
)

bp = Blueprint("users", __name__, url_prefix="/api/v1/users")


def get_repository():
    """Get repository from app config."""
    from flask import current_app
    return current_app.config["repository"]


@bp.route("", methods=["POST"])
def create_user_endpoint():
    """Create a new user."""
    try:
        data = request.get_json()
        if data is None:
            return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)
    except BadRequest:
        return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)

    user_create = UserCreate(
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        email=data.get("email", ""),
        company=data.get("company"),
        role=data.get("role", "attendee"),
    )

    errors = validate_user_create(user_create)
    if errors:
        return error_response(VALIDATION_ERROR, "Validation failed", {"fields": errors}, status=422)

    try:
        user = create_user(user_create, get_repository())
    except ValueError as e:
        if str(e) == "EMAIL_ALREADY_EXISTS":
            return error_response(EMAIL_ALREADY_EXISTS, "Email already exists", status=409)
        raise

    response = jsonify(user.to_dict())
    response.status_code = 201
    response.headers["Location"] = f"/api/v1/users/{user.id}"
    return response


@bp.route("", methods=["GET"])
def list_users_endpoint():
    """List users with pagination and filters."""
    page, page_size = parse_pagination_params(request.args)
    role = request.args.get("role")
    email = request.args.get("email")

    result = list_users(page, page_size, role, email, get_repository())

    # Convert User objects to dicts
    result["items"] = [item.to_dict() if hasattr(item, "to_dict") else item for item in result["items"]]
    return jsonify(result)


@bp.route("/<user_id>", methods=["GET"])
def get_user_endpoint(user_id: str):
    """Get a user by ID."""
    user = get_repository().get_by_id(user_id)
    if not user:
        return error_response(NOT_FOUND, "User not found", status=404)
    return jsonify(user.to_dict())


@bp.route("/<user_id>", methods=["PUT"])
def replace_user_endpoint(user_id: str):
    """Replace a user (full update)."""
    try:
        data = request.get_json()
        if data is None:
            return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)
    except BadRequest:
        return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)

    # All fields required for PUT
    required = ["first_name", "last_name", "email"]
    missing = [f for f in required if f not in data or not data[f]]
    if missing:
        return error_response(VALIDATION_ERROR, "Missing required fields", {"fields": missing}, status=422)

    user_create = UserCreate(
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["email"],
        company=data.get("company"),
        role=data.get("role", "attendee"),
    )

    errors = validate_user_create(user_create)
    if errors:
        return error_response(VALIDATION_ERROR, "Validation failed", {"fields": errors}, status=422)

    # Check if user exists
    existing = get_repository().get_by_id(user_id)
    if not existing:
        return error_response(NOT_FOUND, "User not found", status=404)

    try:
        # For PUT, we delete and recreate with same ID
        repo = get_repository()
        repo.delete(user_id)

        now = existing.created_at
        from datetime import datetime, timezone
        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        from user_service.models import User
        user = User(
            id=user_id,
            first_name=user_create.first_name.strip(),
            last_name=user_create.last_name.strip(),
            email=user_create.email.lower(),
            company=user_create.company.strip() if user_create.company else None,
            role=user_create.role,
            created_at=now,
            updated_at=updated_at,
        )

        # Check email uniqueness
        if repo.get_by_email(user.email) and repo.get_by_email(user.email).id != user_id:
            return error_response(EMAIL_ALREADY_EXISTS, "Email already exists", status=409)

        repo.create(user)
    except ValueError as e:
        if str(e) == "EMAIL_ALREADY_EXISTS":
            return error_response(EMAIL_ALREADY_EXISTS, "Email already exists", status=409)
        raise

    return jsonify(user.to_dict())


@bp.route("/<user_id>", methods=["PATCH"])
def patch_user_endpoint(user_id: str):
    """Partially update a user."""
    try:
        data = request.get_json()
        if data is None:
            return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)
    except BadRequest:
        return error_response(MALFORMED_JSON, "Malformed JSON body", status=400)

    user_update = UserUpdate(
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        email=data.get("email"),
        company=data.get("company"),
        role=data.get("role"),
    )

    errors = validate_user_update(user_update)
    if errors:
        return error_response(VALIDATION_ERROR, "Validation failed", {"fields": errors}, status=422)

    try:
        user = update_user(user_id, user_update, get_repository())
    except ValueError as e:
        if str(e) == "EMAIL_ALREADY_EXISTS":
            return error_response(EMAIL_ALREADY_EXISTS, "Email already exists", status=409)
        if str(e) == "VALIDATION_ERROR":
            return error_response(VALIDATION_ERROR, "Validation failed", status=422)
        raise

    if not user:
        return error_response(NOT_FOUND, "User not found", status=404)

    return jsonify(user.to_dict())


@bp.route("/<user_id>", methods=["DELETE"])
def delete_user_endpoint(user_id: str):
    """Delete a user."""
    deleted = get_repository().delete(user_id)
    if not deleted:
        return error_response(NOT_FOUND, "User not found", status=404)
    return "", 204