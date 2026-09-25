"""Resilience integration test for registration-service — run separately."""

import os
import socket
import subprocess
import sys
import time

import pytest
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRATION_SERVICE_DIR = os.path.join(BASE_DIR, "registration-service")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def wait_for_health(base_url: str, timeout: float = 10.0) -> bool:
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


@pytest.mark.req("REQ-REG-B09")
def test_create_registration_dependency_unavailable():
    """registration-service with USER_SERVICE_URL on a closed port → 503."""
    closed_port = find_free_port()
    event_closed_port = find_free_port()
    reg_port = find_free_port()

    env = {
        **os.environ,
        "PORT": str(reg_port),
        "STORAGE_BACKEND": "memory",
        "USER_SERVICE_URL": f"http://127.0.0.1:{closed_port}",
        "EVENT_SERVICE_URL": f"http://127.0.0.1:{event_closed_port}",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "registration_service"],
        cwd=REGISTRATION_SERVICE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{reg_port}"
    try:
        if not wait_for_health(url):
            proc.terminate()
            proc.wait()
            pytest.fail(f"isolated registration-service did not start on port {reg_port}")

        resp = requests.post(
            f"{url}/api/v1/registrations",
            json={"user_id": "any-user-id", "event_id": "any-event-id"},
            timeout=10,
        )
        assert resp.status_code == 503, resp.text
        assert resp.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    finally:
        proc.terminate()
        proc.wait()
