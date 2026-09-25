"""Integration tests for registration-service using real subprocesses."""

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
REGISTRATION_SERVICE_DIR = os.path.join(BASE_DIR, "registration-service")


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
    """Start event-service on a free port, yield its base URL, then terminate."""
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


@pytest.fixture(scope="module")
def registration_service_url(user_service_url, event_service_url):
    """Start registration-service, yield its base URL, then terminate."""
    port = find_free_port()
    env = {
        **os.environ,
        "PORT": str(port),
        "STORAGE_BACKEND": "memory",
        "USER_SERVICE_URL": user_service_url,
        "EVENT_SERVICE_URL": event_service_url,
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "registration_service"],
        cwd=REGISTRATION_SERVICE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    if not wait_for_health(url):
        proc.terminate()
        proc.wait()
        pytest.fail(f"registration-service did not start on port {port}")
    yield url
    proc.terminate()
    proc.wait()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_organizer(user_url: str) -> dict:
    payload = {
        "first_name": "Alice",
        "last_name": "Organizer",
        "email": f"organizer_{time.time_ns()}@example.com",
        "role": "organizer",
    }
    resp = requests.post(f"{user_url}/api/v1/users", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_attendee(user_url: str) -> dict:
    payload = {
        "first_name": "Bob",
        "last_name": "Attendee",
        "email": f"attendee_{time.time_ns()}@example.com",
        "role": "attendee",
    }
    resp = requests.post(f"{user_url}/api/v1/users", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_published_event(user_url: str, event_url: str) -> dict:
    """Create an organizer, then a published event. Returns the event dict."""
    organizer = create_organizer(user_url)
    payload = {
        "title": "Registration Test Conference",
        "organizer_id": organizer["id"],
        "venue": "Auditorium Roma",
        "city": "Roma",
        "start_date": "2026-10-15",
        "end_date": "2026-10-16",
        "capacity": 100,
        "price": 49.0,
        "status": "published",
    }
    resp = requests.post(f"{event_url}/api/v1/events", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_create_registration_success(user_service_url, event_service_url, registration_service_url):
    """Create a registration for a published event → 201, status=confirmed, amount=event.price."""
    event = create_published_event(user_service_url, event_service_url)
    attendee = create_attendee(user_service_url)

    resp = requests.post(
        f"{registration_service_url}/api/v1/registrations",
        json={"user_id": attendee["id"], "event_id": event["id"]},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["user_id"] == attendee["id"]
    assert data["event_id"] == event["id"]
    assert data["status"] == "confirmed"
    assert data["amount"] == event["price"]
    assert "id" in data
    assert "Location" in resp.headers


def test_create_registration_user_not_found(event_service_url, registration_service_url, user_service_url):
    """Non-existent user_id → 422 REFERENCE_NOT_FOUND."""
    event = create_published_event(user_service_url, event_service_url)
    resp = requests.post(
        f"{registration_service_url}/api/v1/registrations",
        json={
            "user_id": "00000000-0000-0000-0000-000000000000",
            "event_id": event["id"],
        },
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "REFERENCE_NOT_FOUND"

