"""User service configuration."""

import os
from pathlib import Path


class Config:
    """Application configuration from environment variables."""

    def __init__(self):
        self.port = int(os.environ.get("PORT", "5001"))
        self.storage_backend = os.environ.get("STORAGE_BACKEND", "memory").lower()
        self.data_dir = Path(os.environ.get("DATA_DIR", "./data")).resolve()

        # Service URLs for inter-service communication
        self.user_service_url = os.environ.get("USER_SERVICE_URL", f"http://localhost:{self.port}")
        self.event_service_url = os.environ.get("EVENT_SERVICE_URL", "http://localhost:5002")
        self.registration_service_url = os.environ.get("REGISTRATION_SERVICE_URL", "http://localhost:5003")
        self.feedback_service_url = os.environ.get("FEEDBACK_SERVICE_URL", "http://localhost:5004")
        self.notification_service_url = os.environ.get("NOTIFICATION_SERVICE_URL", "http://localhost:5005")

        self.validate()

    def validate(self):
        """Validate required configuration."""
        if self.storage_backend not in ("memory", "json", "sqlite"):
            raise ValueError(f"Invalid STORAGE_BACKEND: {self.storage_backend}. Must be 'memory', 'json', or 'sqlite'")
        if self.storage_backend in ("json", "sqlite"):
            self.data_dir.mkdir(parents=True, exist_ok=True)


config = Config()