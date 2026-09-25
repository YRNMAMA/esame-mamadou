"""Shared HTTP client for inter-service calls."""

import os
import requests
from typing import Any, Optional
from urllib.parse import urljoin

from .errors import REFERENCE_NOT_FOUND, DEPENDENCY_UNAVAILABLE, error_response


DEFAULT_TIMEOUT = 2.0  # seconds


class ServiceClient:
    """Thin wrapper around requests for calling other services."""

    def __init__(self, base_url: str, service_name: str):
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.session = requests.Session()

    def _handle_response(self, resp: requests.Response, path: str) -> dict:
        """Handle response, raise appropriate exceptions for error statuses."""
        if resp.status_code == 404:
            raise ReferenceNotFoundError(f"{self.service_name} returned 404 for {path}")
        if resp.status_code >= 500 or resp.status_code == 0:
            raise DependencyUnavailableError(f"{self.service_name} unavailable: {resp.status_code}")
        try:
            return resp.json()
        except ValueError:
            return {}

    def get(self, path: str, params: dict = None) -> tuple[int, dict]:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        try:
            resp = self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise DependencyUnavailableError(f"{self.service_name} connection failed: {e}")
        return resp.status_code, self._handle_response(resp, path)

    def post(self, path: str, json: dict = None) -> tuple[int, dict]:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        try:
            resp = self.session.post(url, json=json, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise DependencyUnavailableError(f"{self.service_name} connection failed: {e}")
        return resp.status_code, self._handle_response(resp, path)


class ReferenceNotFoundError(Exception):
    """Raised when a dependency returns 404."""
    pass


class DependencyUnavailableError(Exception):
    """Raised when a dependency is unreachable or returns 5xx."""
    pass


def get_service_url(service_name: str, default_port: int) -> str:
    """Get service URL from env var or use default."""
    env_var = f"{service_name.upper().replace('-', '_')}_SERVICE_URL"
    return os.environ.get(env_var, f"http://localhost:{default_port}")