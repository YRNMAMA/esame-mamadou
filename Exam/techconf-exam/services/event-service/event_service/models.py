"""Event domain models and validation."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from techconf_common import VALIDATION_ERROR
from event_service.client import ReferenceNotFoundError, DependencyUnavailableError

# Date format: YYYY-MM-DD
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_STATUSES = {"draft", "published", "cancelled"}
VALID_TRANSITIONS = {
    "draft": {"published", "cancelled"},
    "published": {"cancelled"},
    "cancelled": set(),
}


@dataclass
class Event:
    """Event domain model."""
    id: str
    title: str
    organizer_id: str
    venue: str
    city: str
    start_date: str
    end_date: str
    capacity: int
    price: float
    status: str
    created_at: str
    updated_at: str
    description: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "organizer_id": self.organizer_id,
            "venue": self.venue,
            "city": self.city,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "capacity": self.capacity,
            "price": self.price,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class EventCreate:
    """Event creation request."""
    title: str
    organizer_id: str
    venue: str
    city: str
    start_date: str
    end_date: str
    capacity: int
    price: float
    description: Optional[str] = None
    status: str = "draft"


@dataclass
class EventUpdate:
    """Event update request (all optional)."""
    title: Optional[str] = None
    description: Optional[str] = None
    organizer_id: Optional[str] = None
    venue: Optional[str] = None
    city: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    capacity: Optional[int] = None
    price: Optional[float] = None
    status: Optional[str] = None


def validate_event_create(data: EventCreate) -> list[str]:
    """Validate event creation data. Returns list of error messages."""
    errors = []

    if not data.title or not data.title.strip():
        errors.append("title is required")
    elif len(data.title) < 3 or len(data.title) > 120:
        errors.append("title must be between 3 and 120 characters")

    if not data.organizer_id:
        errors.append("organizer_id is required")

    if not data.venue or not data.venue.strip():
        errors.append("venue is required")
    elif len(data.venue) > 100:
        errors.append("venue must be at most 100 characters")

    if not data.city or not data.city.strip():
        errors.append("city is required")
    elif len(data.city) > 60:
        errors.append("city must be at most 60 characters")

    if not data.start_date:
        errors.append("start_date is required")
    elif not DATE_REGEX.match(data.start_date):
        errors.append("start_date must be in YYYY-MM-DD format")

    if not data.end_date:
        errors.append("end_date is required")
    elif not DATE_REGEX.match(data.end_date):
        errors.append("end_date must be in YYYY-MM-DD format")

    # Validate end_date >= start_date
    if data.start_date and data.end_date and DATE_REGEX.match(data.start_date) and DATE_REGEX.match(data.end_date):
        if data.end_date < data.start_date:
            errors.append("end_date must be on or after start_date")

    if not isinstance(data.capacity, int) or data.capacity < 1 or data.capacity > 10000:
        errors.append("capacity must be an integer between 1 and 10000")

    if not isinstance(data.price, (int, float)) or data.price < 0:
        errors.append("price must be a number >= 0")

    if data.description is not None and len(data.description) > 2000:
        errors.append("description must be at most 2000 characters")

    if data.status not in VALID_STATUSES:
        errors.append(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")

    return errors


def validate_event_update(data: EventUpdate) -> list[str]:
    """Validate event update data. Returns list of error messages."""
    errors = []

    if data.title is not None:
        if not data.title.strip():
            errors.append("title cannot be empty")
        elif len(data.title) < 3 or len(data.title) > 120:
            errors.append("title must be between 3 and 120 characters")

    if data.venue is not None:
        if not data.venue.strip():
            errors.append("venue cannot be empty")
        elif len(data.venue) > 100:
            errors.append("venue must be at most 100 characters")

    if data.city is not None:
        if not data.city.strip():
            errors.append("city cannot be empty")
        elif len(data.city) > 60:
            errors.append("city must be at most 60 characters")

    if data.start_date is not None:
        if not DATE_REGEX.match(data.start_date):
            errors.append("start_date must be in YYYY-MM-DD format")

    if data.end_date is not None:
        if not DATE_REGEX.match(data.end_date):
            errors.append("end_date must be in YYYY-MM-DD format")

    # Validate end_date >= start_date if both provided
    if data.start_date and data.end_date:
        if data.end_date < data.start_date:
            errors.append("end_date must be on or after start_date")

    if data.capacity is not None:
        if not isinstance(data.capacity, int) or data.capacity < 1 or data.capacity > 10000:
            errors.append("capacity must be an integer between 1 and 10000")

    if data.price is not None:
        if not isinstance(data.price, (int, float)) or data.price < 0:
            errors.append("price must be a number >= 0")

    if data.description is not None and len(data.description) > 2000:
        errors.append("description must be at most 2000 characters")

    if data.status is not None and data.status not in VALID_STATUSES:
        errors.append(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")

    return errors


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """Check if status transition is valid (REQ-EVT-B04)."""
    if current_status == new_status:
        return True
    return new_status in VALID_TRANSITIONS.get(current_status, set())


def create_event(data: EventCreate, repository, user_client) -> Event:
    """Create a new event with business rules applied."""
    # Validate organizer exists and has role=organizer (REQ-EVT-B01, REQ-EVT-B02)
    try:
        status_code, user = user_client.get_user(data.organizer_id)
        if user.get("role") != "organizer":
            raise ValueError("INVALID_ORGANIZER")
    except ReferenceNotFoundError:
        raise ValueError("REFERENCE_NOT_FOUND")
    except DependencyUnavailableError:
        raise ValueError("DEPENDENCY_UNAVAILABLE")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event = Event(
        id=str(uuid4()),
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        organizer_id=data.organizer_id,
        venue=data.venue.strip(),
        city=data.city.strip(),
        start_date=data.start_date,
        end_date=data.end_date,
        capacity=data.capacity,
        price=float(data.price),
        status=data.status,
        created_at=now,
        updated_at=now,
    )

    return repository.create(event)


def update_event(event_id: str, data: EventUpdate, repository, user_client) -> Optional[Event]:
    """Update an existing event with business rules applied."""
    # Validate
    errors = validate_event_update(data)
    if errors:
        raise ValueError("VALIDATION_ERROR")

    # Check if event exists
    existing = repository.get_by_id(event_id)
    if not existing:
        return None

    # Validate status transition (REQ-EVT-B04)
    if data.status is not None:
        if not validate_status_transition(existing.status, data.status):
            raise ValueError("INVALID_STATUS_TRANSITION")

    # If organizer_id is being changed, validate new organizer
    if data.organizer_id is not None and data.organizer_id != existing.organizer_id:
        try:
            status_code, user = user_client.get_user(data.organizer_id)
            if user.get("role") != "organizer":
                raise ValueError("INVALID_ORGANIZER")
        except ReferenceNotFoundError:
            raise ValueError("REFERENCE_NOT_FOUND")
        except DependencyUnavailableError:
            raise ValueError("DEPENDENCY_UNAVAILABLE")

    # Validate date constraint if dates are being changed
    start_date = data.start_date if data.start_date is not None else existing.start_date
    end_date = data.end_date if data.end_date is not None else existing.end_date
    if end_date < start_date:
        raise ValueError("VALIDATION_ERROR")

    return repository.update(event_id, data)


def list_events(page: int, page_size: int, status: Optional[str], city: Optional[str], repository) -> dict:
    """List events with filters (REQ-EVT-B06)."""
    return repository.list_users(page, page_size, status, city)