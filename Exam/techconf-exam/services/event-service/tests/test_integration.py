"""Integration tests for event-service using real subprocesses."""

import os
import socket
import subprocess
import sys
import time

import pytest
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USER_SERVICE_DIR = os.path.join(BASE_DIR, "user-service")
EVENT_SERVICE_DIR = os.path.join(BASE_DIR, "event-service")


def find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def wait_for_health(base_url: str, timeout: float = 10.0) -> bool:
    """Poll /health until the service responds or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base_url}/health", timeout=1.0)
            if resp.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
def user_service_url():
    """Start user-service on a free port, yield its base URL, then terminate."""
    port = find_free_port()
    env = {
        **os.environ,
        "PORT": str(port),
        "STORAGE_BACKEND": "memory",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "user_service"],
        cwd=USER_SERVICE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    if not wait_for_health(url):
        proc.terminate()
        proc.wait()
        pytest.fail(f"user-service did not start on port {port}")
    yield url
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="module")
def event_service_url(user_service_url):
    """Start event-service on a free port pointing at user_service_url, yield base URL."""
    port = find_free_port()
    env = {
        **os.environ,
        "PORT": str(port),
        "STORAGE_BACKEND": "memory",
        "USER_SERVICE_URL": user_service_url,
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "event_service"],
        cwd=EVENT_SERVICE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    if not wait_for_health(url):
        proc.terminate()
        proc.wait()
        pytest.fail(f"event-service did not start on port {port}")
    yield url
    proc.terminate()
    proc.wait()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_organizer(user_url: str) -> dict:
    """Create an organizer user and return the response body."""
    payload = {
        "first_name": "Alice",
        "last_name": "Organizer",
        "email": f"alice_{time.time_ns()}@example.com",
        "role": "organizer",
    }
    resp = requests.post(f"{user_url}/api/v1/users", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_attendee(user_url: str) -> dict:
    """Create an attendee user and return the response body."""
    payload = {
        "first_name": "Bob",
        "last_name": "Attendee",
        "email": f"bob_{time.time_ns()}@example.com",
        "role": "attendee",
    }
    resp = requests.post(f"{user_url}/api/v1/users", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def event_payload(organizer_id: str, **overrides) -> dict:
    payload = {
        "title": "Integration Test Conference",
        "organizer_id": organizer_id,
        "venue": "Auditorium Roma",
        "city": "Roma",
        "start_date": "2026-10-15",
        "end_date": "2026-10-16",
        "capacity": 100,
        "price": 49.0,
        "status": "draft",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_event_valid_organizer(user_service_url, event_service_url):
    """Create an event with a valid organizer → 201."""
    organizer = create_organizer(user_service_url)
    resp = requests.post(
        f"{event_service_url}/api/v1/events",
        json=event_payload(organizer["id"]),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["organizer_id"] == organizer["id"]
    assert data["status"] == "draft"
    assert "id" in data
    assert "Location" in resp.headers


def test_create_event_organizer_not_found(event_service_url):
    """Use a non-existent organizer_id → 422 REFERENCE_NOT_FOUND."""
    resp = requests.post(
        f"{event_service_url}/api/v1/events",
        json=event_payload("00000000-0000-0000-0000-000000000000"),
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "REFERENCE_NOT_FOUND"


def test_create_event_user_not_organizer(user_service_url, event_service_url):
    """Attendee user cannot be organizer → 422 INVALID_ORGANIZER."""
    attendee = create_attendee(user_service_url)
    resp = requests.post(
        f"{event_service_url}/api/v1/events",
        json=event_payload(attendee["id"]),
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "INVALID_ORGANIZER"


def test_event_dependency_unavailable():
    """event-service with USER_SERVICE_URL pointing at a closed port → 503."""
    # Find a port that has nothing on it
    closed_port = find_free_port()
    event_port = find_free_port()
    env = {
        **os.environ,
        "PORT": str(event_port),
        "STORAGE_BACKEND": "memory",
        "USER_SERVICE_URL": f"http://127.0.0.1:{closed_port}",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "event_service"],
        cwd=EVENT_SERVICE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{event_port}"
    try:
        if not wait_for_health(url):
            pytest.fail(f"isolated event-service did not start on port {event_port}")

        resp = requests.post(
            f"{url}/api/v1/events",
            json=event_payload("some-organizer-id"),
        )
        assert resp.status_code == 503, resp.text
        assert resp.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    finally:
        proc.terminate()
        proc.wait()
