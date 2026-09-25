"""Service clients for registration-service."""

import requests
from techconf_common import REFERENCE_NOT_FOUND, DEPENDENCY_UNAVAILABLE, get_service_url
from registration_service.config import config


class UserServiceClient:
    """Client for calling user-service."""

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or get_service_url("user", 5001)).rstrip("/")
        self.session = requests.Session()
        self.timeout = 2.0

    def get_user(self, user_id: str) -> tuple[int, dict]:
        """Get user by ID."""
        url = f"{self.base_url}/api/v1/users/{user_id}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            raise DependencyUnavailableError(f"user-service connection failed: {e}")

        if resp.status_code == 404:
            raise ReferenceNotFoundError(f"User {user_id} not found")
        if resp.status_code >= 500:
            raise DependencyUnavailableError(f"user-service returned {resp.status_code}")

        try:
            return resp.status_code, resp.json()
        except ValueError:
            return resp.status_code, {}


class EventServiceClient:
    """Client for calling event-service."""

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or get_service_url("event", 5002)).rstrip("/")
        self.session = requests.Session()
        self.timeout = 2.0

    def get_event(self, event_id: str) -> tuple[int, dict]:
        """Get event by ID."""
        url = f"{self.base_url}/api/v1/events/{event_id}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            raise DependencyUnavailableError(f"event-service connection failed: {e}")

        if resp.status_code == 404:
            raise ReferenceNotFoundError(f"Event {event_id} not found")
        if resp.status_code >= 500:
            raise DependencyUnavailableError(f"event-service returned {resp.status_code}")

        try:
            return resp.status_code, resp.json()
        except ValueError:
            return resp.status_code, {}


class ReferenceNotFoundError(Exception):
    """Raised when a service returns 404."""
    pass


class DependencyUnavailableError(Exception):
    """Raised when a service is unavailable."""
    pass


def create_user_service_client() -> UserServiceClient:
    return UserServiceClient(config.user_service_url)


def create_event_service_client() -> EventServiceClient:
    return EventServiceClient(config.event_service_url)