"""Registration service integration tests for Flask routes."""

import pytest
from unittest.mock import Mock
from registration_service import create_app


@pytest.fixture
def app():
    """Create test app with mocked clients."""
    app = create_app()
    app.config["TESTING"] = True

    # Mock user client
    mock_user_client = Mock()
    mock_user_client.get_user.return_value = (200, {"id": "1", "role": "attendee"})
    app.config["user_client"] = mock_user_client

    # Mock event client
    mock_event_client = Mock()
    mock_event_client.get_event.return_value = (200, {"id": "2", "status": "published", "capacity": 10, "price": 149.00})
    app.config["event_client"] = mock_event_client

    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


def make_reg_payload(user_id="1", event_id="2"):
    return {"user_id": user_id, "event_id": event_id}


class TestRoutes:
    """Test Flask routes."""

    @pytest.mark.req("REQ-REG-B09")
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "registration-service"

    @pytest.mark.req("REQ-REG-B06")
    def test_create_registration_success(self, client):
        response = client.post("/api/v1/registrations", json=make_reg_payload())
        assert response.status_code == 201
        assert response.headers.get("Location")
        data = response.get_json()
        assert data["user_id"] == "1"
        assert data["event_id"] == "2"
        assert data["status"] == "confirmed"
        assert data["amount"] == 149.00

    @pytest.mark.req("REQ-REG-B01")
    def test_create_registration_missing_fields(self, client):
        response = client.post("/api/v1/registrations", json={"user_id": "1"})
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.req("REQ-REG-B01")
    def test_create_registration_user_not_found(self, client, app):
        from registration_service.client import ReferenceNotFoundError
        app.config["user_client"].get_user.side_effect = ReferenceNotFoundError("Not found")

        response = client.post("/api/v1/registrations", json=make_reg_payload())
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "REFERENCE_NOT_FOUND"

    @pytest.mark.req("REQ-REG-B02")
    def test_create_registration_event_not_found(self, client, app):
        from registration_service.client import ReferenceNotFoundError
        app.config["event_client"].get_event.side_effect = ReferenceNotFoundError("Not found")

        response = client.post("/api/v1/registrations", json=make_reg_payload())
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "REFERENCE_NOT_FOUND"

    @pytest.mark.req("REQ-REG-B03")
    def test_create_registration_event_not_published(self, client, app):
        app.config["event_client"].get_event.return_value = (200, {"id": "2", "status": "draft", "capacity": 10, "price": 149.00})

        response = client.post("/api/v1/registrations", json=make_reg_payload())
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "EVENT_NOT_OPEN"

    @pytest.mark.req("REQ-REG-B04")
    def test_create_registration_already_registered(self, client):
        client.post("/api/v1/registrations", json=make_reg_payload())
        response = client.post("/api/v1/registrations", json=make_reg_payload())
        assert response.status_code == 409
        data = response.get_json()
        assert data["error"]["code"] == "ALREADY_REGISTERED"

    @pytest.mark.req("REQ-REG-B05")
    def test_create_registration_event_full(self, client, app):
        app.config["event_client"].get_event.return_value = (200, {"id": "2", "status": "published", "capacity": 1, "price": 149.00})

        response = client.post("/api/v1/registrations", json=make_reg_payload())
        assert response.status_code == 201

        response = client.post("/api/v1/registrations", json=make_reg_payload("3", "2"))
        assert response.status_code == 409
        data = response.get_json()
        assert data["error"]["code"] == "EVENT_FULL"

    @pytest.mark.req("REQ-REG-B09")
    def test_create_registration_dependency_unavailable(self, client, app):
        from registration_service.client import DependencyUnavailableError
        app.config["user_client"].get_user.side_effect = DependencyUnavailableError("Unavailable")

        response = client.post("/api/v1/registrations", json=make_reg_payload())
        assert response.status_code == 503
        data = response.get_json()
        assert data["error"]["code"] == "DEPENDENCY_UNAVAILABLE"

    @pytest.mark.req("REQ-REG-B05")
    def test_list_registrations(self, client):
        for i in range(3):
            client.post("/api/v1/registrations", json=make_reg_payload(str(i), "2"))

        response = client.get("/api/v1/registrations?page=1&page_size=2")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    @pytest.mark.req("REQ-REG-B04")
    def test_list_registrations_filters(self, client):
        client.post("/api/v1/registrations", json=make_reg_payload("1", "2"))
        client.post("/api/v1/registrations", json=make_reg_payload("2", "3"))

        response = client.get("/api/v1/registrations?user_id=1")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1

    @pytest.mark.req("REQ-REG-B08")
    def test_stats_endpoint(self, client):
        client.post("/api/v1/registrations", json=make_reg_payload())

        response = client.get("/api/v1/registrations/stats?event_id=2")
        assert response.status_code == 200
        data = response.get_json()
        assert data["event_id"] == "2"
        assert data["capacity"] == 10
        assert data["confirmed"] == 1
        assert data["available"] == 9

    @pytest.mark.req("REQ-REG-B08")
    def test_stats_event_not_found(self, client, app):
        from registration_service.client import ReferenceNotFoundError
        app.config["event_client"].get_event.side_effect = ReferenceNotFoundError("Not found")

        response = client.get("/api/v1/registrations/stats?event_id=999")
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.req("REQ-REG-B08")
    def test_stats_missing_event_id(self, client):
        response = client.get("/api/v1/registrations/stats")
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.req("REQ-REG-B07")
    def test_get_registration(self, client):
        create_resp = client.post("/api/v1/registrations", json=make_reg_payload())
        reg_id = create_resp.get_json()["id"]

        response = client.get(f"/api/v1/registrations/{reg_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == reg_id

    @pytest.mark.req("REQ-REG-B07")
    def test_get_registration_not_found(self, client):
        response = client.get("/api/v1/registrations/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.req("REQ-REG-B07")
    def test_put_registration_not_allowed(self, client):
        response = client.put("/api/v1/registrations/123")
        assert response.status_code == 405
        data = response.get_json()
        assert data["error"]["code"] == "METHOD_NOT_ALLOWED"

    @pytest.mark.req("REQ-REG-B07")
    def test_patch_registration_success(self, client):
        create_resp = client.post("/api/v1/registrations", json=make_reg_payload())
        reg_id = create_resp.get_json()["id"]

        response = client.patch(f"/api/v1/registrations/{reg_id}", json={"status": "cancelled"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "cancelled"

    @pytest.mark.req("REQ-REG-B07")
    def test_patch_registration_invalid_transition(self, client):
        create_resp = client.post("/api/v1/registrations", json=make_reg_payload())
        reg_id = create_resp.get_json()["id"]

        # Cancel it
        client.patch(f"/api/v1/registrations/{reg_id}", json={"status": "cancelled"})
        # Try to re-confirm
        response = client.patch(f"/api/v1/registrations/{reg_id}", json={"status": "confirmed"})
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_STATUS_TRANSITION"

    @pytest.mark.req("REQ-REG-B07")
    def test_patch_registration_not_found(self, client):
        response = client.patch("/api/v1/registrations/00000000-0000-0000-0000-000000000000", json={"status": "cancelled"})
        assert response.status_code == 404

    @pytest.mark.req("REQ-REG-B07")
    def test_patch_registration_invalid_status(self, client):
        create_resp = client.post("/api/v1/registrations", json=make_reg_payload())
        reg_id = create_resp.get_json()["id"]

        response = client.patch(f"/api/v1/registrations/{reg_id}", json={"status": "invalid"})
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.req("REQ-REG-B05")
    def test_delete_registration(self, client):
        create_resp = client.post("/api/v1/registrations", json=make_reg_payload())
        reg_id = create_resp.get_json()["id"]

        response = client.delete(f"/api/v1/registrations/{reg_id}")
        assert response.status_code == 204

        get_resp = client.get(f"/api/v1/registrations/{reg_id}")
        assert get_resp.status_code == 404

    @pytest.mark.req("REQ-REG-B05")
    def test_delete_registration_not_found(self, client):
        response = client.delete("/api/v1/registrations/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    @pytest.mark.req("REQ-REG-B01")
    def test_malformed_json(self, client):
        response = client.post("/api/v1/registrations", data="{invalid json", content_type="application/json")
        assert response.status_code == 400
