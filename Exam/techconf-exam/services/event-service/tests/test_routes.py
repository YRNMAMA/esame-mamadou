"""Event service integration tests for Flask routes."""

import pytest
import json
from unittest.mock import Mock, patch
from event_service import create_app


@pytest.fixture
def app():
    """Create test app with mocked user client."""
    app = create_app()
    app.config["TESTING"] = True

    # Mock user client
    mock_user_client = Mock()
    mock_user_client.get_user.return_value = (200, {"id": "1", "role": "organizer"})
    app.config["user_client"] = mock_user_client

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    with app.test_client() as client:
        yield client


def make_event_payload(organizer_id="1", **overrides):
    """Create event payload with defaults."""
    payload = {
        "title": "TechConf 2026",
        "organizer_id": organizer_id,
        "venue": "Auditorium Roma",
        "city": "Roma",
        "start_date": "2026-10-15",
        "end_date": "2026-10-16",
        "capacity": 100,
        "price": 149.00,
        "status": "draft",
    }
    payload.update(overrides)
    return payload


class TestRoutes:
    """Test Flask routes."""

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "event-service"

    def test_create_event_success(self, client):
        payload = make_event_payload()
        response = client.post("/api/v1/events", json=payload)
        assert response.status_code == 201
        assert response.headers.get("Location")
        data = response.get_json()
        assert data["title"] == "TechConf 2026"
        assert data["status"] == "draft"
        assert data["organizer_id"] == "1"
        assert "id" in data

    def test_create_event_missing_required(self, client):
        payload = {"title": "Event"}
        response = client.post("/api/v1/events", json=payload)
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_create_event_invalid_dates(self, client):
        payload = make_event_payload(start_date="2026-10-16", end_date="2026-10-15")
        response = client.post("/api/v1/events", json=payload)
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_create_event_organizer_not_found(self, client, app):
        app.config["user_client"].get_user.side_effect = Exception("REFERENCE_NOT_FOUND")
        from event_service.client import ReferenceNotFoundError
        app.config["user_client"].get_user.side_effect = ReferenceNotFoundError("Not found")

        payload = make_event_payload()
        response = client.post("/api/v1/events", json=payload)
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "REFERENCE_NOT_FOUND"

    def test_create_event_invalid_organizer_role(self, client, app):
        app.config["user_client"].get_user.return_value = (200, {"id": "1", "role": "attendee"})

        payload = make_event_payload()
        response = client.post("/api/v1/events", json=payload)
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_ORGANIZER"

    def test_create_event_dependency_unavailable(self, client, app):
        from event_service.client import DependencyUnavailableError
        app.config["user_client"].get_user.side_effect = DependencyUnavailableError("Unavailable")

        payload = make_event_payload()
        response = client.post("/api/v1/events", json=payload)
        assert response.status_code == 503
        data = response.get_json()
        assert data["error"]["code"] == "DEPENDENCY_UNAVAILABLE"

    def test_list_events(self, client):
        # Create a few events
        for i in range(3):
            client.post("/api/v1/events", json=make_event_payload(title=f"Event {i}"))

        response = client.get("/api/v1/events?page=1&page_size=2")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    def test_list_events_status_filter(self, client):
        client.post("/api/v1/events", json=make_event_payload(title="Draft Event", status="draft"))
        client.post("/api/v1/events", json=make_event_payload(title="Published Event", status="published"))

        response = client.get("/api/v1/events?status=published")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "published"

    def test_list_events_city_filter(self, client):
        client.post("/api/v1/events", json=make_event_payload(city="Roma"))
        client.post("/api/v1/events", json=make_event_payload(city="Milano"))

        response = client.get("/api/v1/events?city=roma")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["items"][0]["city"] == "Roma"

    def test_get_event_success(self, client):
        create_resp = client.post("/api/v1/events", json=make_event_payload())
        event_id = create_resp.get_json()["id"]

        response = client.get(f"/api/v1/events/{event_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == event_id

    def test_get_event_not_found(self, client):
        response = client.get("/api/v1/events/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"]["code"] == "NOT_FOUND"

    def test_put_event_success(self, client):
        create_resp = client.post("/api/v1/events", json=make_event_payload())
        event_id = create_resp.get_json()["id"]

        payload = make_event_payload(title="Updated Event", capacity=200)
        response = client.put(f"/api/v1/events/{event_id}", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["title"] == "Updated Event"
        assert data["capacity"] == 200

    def test_put_event_not_found(self, client):
        payload = make_event_payload()
        response = client.put("/api/v1/events/00000000-0000-0000-0000-000000000000", json=payload)
        assert response.status_code == 404

    def test_put_event_organizer_not_found(self, client, app):
        create_resp = client.post("/api/v1/events", json=make_event_payload())
        event_id = create_resp.get_json()["id"]

        from event_service.client import ReferenceNotFoundError
        app.config["user_client"].get_user.side_effect = ReferenceNotFoundError("Not found")

        payload = make_event_payload()
        response = client.put(f"/api/v1/events/{event_id}", json=payload)
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "REFERENCE_NOT_FOUND"

    def test_patch_event_success(self, client):
        create_resp = client.post("/api/v1/events", json=make_event_payload())
        event_id = create_resp.get_json()["id"]

        response = client.patch(f"/api/v1/events/{event_id}", json={"status": "published"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "published"

    def test_patch_event_invalid_transition(self, client):
        create_resp = client.post("/api/v1/events", json=make_event_payload(status="published"))
        event_id = create_resp.get_json()["id"]

        response = client.patch(f"/api/v1/events/{event_id}", json={"status": "draft"})
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_STATUS_TRANSITION"

    def test_patch_event_not_found(self, client):
        response = client.patch("/api/v1/events/00000000-0000-0000-0000-000000000000", json={"title": "New"})
        assert response.status_code == 404

    def test_patch_event_invalid_dates(self, client):
        create_resp = client.post("/api/v1/events", json=make_event_payload())
        event_id = create_resp.get_json()["id"]

        response = client.patch(f"/api/v1/events/{event_id}", json={"start_date": "2026-10-16", "end_date": "2026-10-15"})
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_delete_event_success(self, client):
        create_resp = client.post("/api/v1/events", json=make_event_payload())
        event_id = create_resp.get_json()["id"]

        response = client.delete(f"/api/v1/events/{event_id}")
        assert response.status_code == 204

        get_resp = client.get(f"/api/v1/events/{event_id}")
        assert get_resp.status_code == 404

    def test_delete_event_not_found(self, client):
        response = client.delete("/api/v1/events/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_malformed_json(self, client):
        response = client.post("/api/v1/events", data="{invalid json", content_type="application/json")
        assert response.status_code == 400

    def test_method_not_allowed(self, client):
        response = client.post("/api/v1/events/123")
        assert response.status_code == 405