"""User domain models and validation."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_ROLES = {"attendee", "speaker", "organizer"}


@dataclass
class User:
    """User domain model."""
    id: str
    first_name: str
    last_name: str
    email: str
    role: str
    created_at: str
    updated_at: str
    company: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "company": self.company,
            "role": self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class UserCreate:
    """User creation request."""
    first_name: str
    last_name: str
    email: str
    company: Optional[str] = None
    role: str = "attendee"


@dataclass
class UserUpdate:
    """User update request (all optional)."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None


def validate_user_create(data: UserCreate) -> list[str]:
    """Validate user creation data. Returns list of error messages."""
    errors = []

    if not data.first_name or not data.first_name.strip():
        errors.append("first_name is required")
    elif len(data.first_name) > 50:
        errors.append("first_name must be at most 50 characters")

    if not data.last_name or not data.last_name.strip():
        errors.append("last_name is required")
    elif len(data.last_name) > 50:
        errors.append("last_name must be at most 50 characters")

    if not data.email or not data.email.strip():
        errors.append("email is required")
    elif not EMAIL_REGEX.match(data.email):
        errors.append("email must be a valid email address")

    if data.company is not None and len(data.company) > 100:
        errors.append("company must be at most 100 characters")

    if data.role not in VALID_ROLES:
        errors.append(f"role must be one of: {', '.join(sorted(VALID_ROLES))}")

    return errors


def validate_user_update(data: UserUpdate) -> list[str]:
    """Validate user update data. Returns list of error messages."""
    errors = []

    if data.first_name is not None:
        if not data.first_name.strip():
            errors.append("first_name cannot be empty")
        elif len(data.first_name) > 50:
            errors.append("first_name must be at most 50 characters")

    if data.last_name is not None:
        if not data.last_name.strip():
            errors.append("last_name cannot be empty")
        elif len(data.last_name) > 50:
            errors.append("last_name must be at most 50 characters")

    if data.email is not None:
        if not data.email.strip():
            errors.append("email cannot be empty")
        elif not EMAIL_REGEX.match(data.email):
            errors.append("email must be a valid email address")

    if data.company is not None and len(data.company) > 100:
        errors.append("company must be at most 100 characters")

    if data.role is not None and data.role not in VALID_ROLES:
        errors.append(f"role must be one of: {', '.join(sorted(VALID_ROLES))}")

    return errors


def normalize_email(email: str) -> str:
    """Normalize email to lowercase."""
    return email.strip().lower()


def create_user(data: UserCreate, repository) -> User:
    """Create a new user with business rules applied."""
    # Normalize email (REQ-USR-B02)
    normalized_email = normalize_email(data.email)

    # Check uniqueness (REQ-USR-B01)
    existing = repository.get_by_email(normalized_email)
    if existing:
        raise ValueError("EMAIL_ALREADY_EXISTS")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    user = User(
        id=str(uuid4()),
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        email=normalized_email,
        company=data.company.strip() if data.company else None,
        role=data.role,
        created_at=now,
        updated_at=now,
    )

    return repository.create(user)


def update_user(user_id: str, data: UserUpdate, repository) -> Optional[User]:
    """Update an existing user with business rules applied."""
    # Validate
    errors = validate_user_update(data)
    if errors:
        raise ValueError("VALIDATION_ERROR")

    # Normalize email if provided (REQ-USR-B02)
    if data.email is not None:
        data.email = normalize_email(data.email)

    return repository.update(user_id, data)


def list_users(page: int, page_size: int, role: Optional[str], email: Optional[str], repository) -> dict:
    """List users with filters (REQ-USR-B03)."""
    return repository.list_users(page, page_size, role, email)