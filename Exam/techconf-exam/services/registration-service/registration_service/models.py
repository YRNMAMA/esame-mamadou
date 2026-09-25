"""Registration domain models and validation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from techconf_common import VALIDATION_ERROR
from registration_service.client import ReferenceNotFoundError, DependencyUnavailableError

VALID_STATUSES = {"confirmed", "cancelled"}
VALID_TRANSITIONS = {
    "confirmed": {"cancelled"},
    "cancelled": set(),
}


@dataclass
class Registration:
    """Registration domain model."""
    id: str
    user_id: str
    event_id: str
    amount: float
    status: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_id": self.event_id,
            "amount": self.amount,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class RegistrationCreate:
    """Registration creation request."""
    user_id: str
    event_id: str


@dataclass
class RegistrationPatch:
    """Registration update request."""
    status: str


@dataclass
class RegistrationStats:
    """Registration statistics response."""
    event_id: str
    capacity: int
    confirmed: int
    available: int


def validate_registration_create(data: RegistrationCreate) -> list[str]:
    """Validate registration creation data."""
    errors = []
    if not data.user_id:
        errors.append("user_id is required")
    if not data.event_id:
        errors.append("event_id is required")
    return errors


def validate_registration_patch(data: RegistrationPatch) -> list[str]:
    """Validate registration patch data."""
    errors = []
    if data.status not in VALID_STATUSES:
        errors.append(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
    return errors


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """Check if status transition is valid (REQ-REG-B07)."""
    if current_status == new_status:
        return True
    return new_status in VALID_TRANSITIONS.get(current_status, set())


def create_registration(data: RegistrationCreate, repository, user_client, event_client) -> Registration:
    """Create a new registration with business rules applied."""
    # Validate user exists (REQ-REG-B01)
    try:
        user_client.get_user(data.user_id)
    except ReferenceNotFoundError:
        raise ValueError("REFERENCE_NOT_FOUND")
    except DependencyUnavailableError:
        raise ValueError("DEPENDENCY_UNAVAILABLE")

    # Validate event exists and is published (REQ-REG-B02, REQ-REG-B03)
    try:
        status_code, event = event_client.get_event(data.event_id)
    except ReferenceNotFoundError:
        raise ValueError("REFERENCE_NOT_FOUND")
    except DependencyUnavailableError:
        raise ValueError("DEPENDENCY_UNAVAILABLE")

    if event.get("status") != "published":
        raise ValueError("EVENT_NOT_OPEN")

    # Check for existing confirmed registration (REQ-REG-B04)
    existing = repository.get_by_user_and_event(data.user_id, data.event_id)
    if existing and existing.status == "confirmed":
        raise ValueError("ALREADY_REGISTERED")

    # Check capacity (REQ-REG-B05)
    confirmed_count = repository.count_confirmed_for_event(data.event_id)
    if confirmed_count >= event.get("capacity", 0):
        raise ValueError("EVENT_FULL")

    # Set amount from event price (REQ-REG-B06)
    amount = float(event.get("price", 0))

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    registration = Registration(
        id=str(uuid4()),
        user_id=data.user_id,
        event_id=data.event_id,
        amount=amount,
        status="confirmed",
        created_at=now,
        updated_at=now,
    )

    return repository.create(registration)


def update_registration(reg_id: str, data: RegistrationPatch, repository) -> Optional[Registration]:
    """Update registration status with business rules applied."""
    errors = validate_registration_patch(data)
    if errors:
        raise ValueError("VALIDATION_ERROR")

    # Check if registration exists
    existing = repository.get_by_id(reg_id)
    if not existing:
        return None

    # Validate status transition (REQ-REG-B07)
    if not validate_status_transition(existing.status, data.status):
        raise ValueError("INVALID_STATUS_TRANSITION")

    return repository.update_status(reg_id, data.status)


def get_stats(event_id: str, repository, event_client) -> RegistrationStats:
    """Get registration stats for an event (REQ-REG-B08)."""
    # Verify event exists
    try:
        event_client.get_event(event_id)
    except ReferenceNotFoundError:
        raise ValueError("NOT_FOUND")
    except DependencyUnavailableError:
        raise ValueError("DEPENDENCY_UNAVAILABLE")

    confirmed = repository.count_confirmed_for_event(event_id)
    # We need to get capacity from event-service, but for stats we can use the event we already fetched
    # For simplicity, we'll get it again
    status_code, event = event_client.get_event(event_id)
    capacity = event.get("capacity", 0)

    return RegistrationStats(
        event_id=event_id,
        capacity=capacity,
        confirmed=confirmed,
        available=capacity - confirmed,
    )


def list_registrations(page: int, page_size: int, user_id: Optional[str], event_id: Optional[str], status: Optional[str], repository) -> dict:
    """List registrations with filters."""
    return repository.list_registrations(page, page_size, user_id, event_id, status)