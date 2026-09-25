"""User service integration tests for Flask routes."""

import pytest
import json
from user_service import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestRoutes:
    """Test Flask routes."""

    @pytest.mark.req("REQ-USR-B02")
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "user-service"

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_create_user_success(self, client):
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "company": "Acme Inc",
            "role": "attendee"
        }
        response = client.post("/api/v1/users", json=payload)
        assert response.status_code == 201
        assert response.headers.get("Location")
        data = response.get_json()
        assert data["email"] == "john@example.com"
        assert data["first_name"] == "John"
        assert data["role"] == "attendee"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_create_user_missing_required(self, client):
        payload = {"first_name": "John"}
        response = client.post("/api/v1/users", json=payload)
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_create_user_invalid_email(self, client):
        payload = {"first_name": "John", "last_name": "Doe", "email": "invalid"}
        response = client.post("/api/v1/users", json=payload)
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_create_user_duplicate_email(self, client):
        payload = {"first_name": "John", "last_name": "Doe", "email": "john@example.com"}
        client.post("/api/v1/users", json=payload)
        response = client.post("/api/v1/users", json=payload)
        assert response.status_code == 409
        data = response.get_json()
        assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_create_user_case_insensitive_email(self, client):
        payload1 = {"first_name": "John", "last_name": "Doe", "email": "john@example.com"}
        payload2 = {"first_name": "Jane", "last_name": "Doe", "email": "JOHN@EXAMPLE.COM"}
        client.post("/api/v1/users", json=payload1)
        response = client.post("/api/v1/users", json=payload2)
        assert response.status_code == 409

    @pytest.mark.req("REQ-USR-B03")
    @pytest.mark.req("REQ-USR-B02")
    def test_list_users(self, client):
        # Create a few users
        for i in range(3):
            client.post("/api/v1/users", json={"first_name": f"User{i}", "last_name": "Test", "email": f"user{i}@example.com"})

        response = client.get("/api/v1/users?page=1&page_size=2")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 2

    @pytest.mark.req("REQ-USR-B03")
    @pytest.mark.req("REQ-USR-B02")
    def test_list_users_role_filter(self, client):
        client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com", "role": "attendee"})
        client.post("/api/v1/users", json={"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com", "role": "organizer"})

        response = client.get("/api/v1/users?role=organizer")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["items"][0]["role"] == "organizer"

    @pytest.mark.req("REQ-USR-B03")
    @pytest.mark.req("REQ-USR-B02")
    def test_list_users_email_filter(self, client):
        client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"})

        response = client.get("/api/v1/users?email=JOHN@EXAMPLE.COM")
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["items"][0]["email"] == "john@example.com"

    @pytest.mark.req("REQ-USR-B02")
    def test_get_user_success(self, client):
        create_resp = client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"})
        user_id = create_resp.get_json()["id"]

        response = client.get(f"/api/v1/users/{user_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["id"] == user_id
        assert data["email"] == "john@example.com"

    @pytest.mark.req("REQ-USR-B02")
    def test_get_user_not_found(self, client):
        response = client.get("/api/v1/users/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.req("REQ-USR-B02")
    def test_put_user_success(self, client):
        create_resp = client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"})
        user_id = create_resp.get_json()["id"]

        payload = {"first_name": "Jane", "last_name": "Smith", "email": "jane@example.com", "role": "organizer"}
        response = client.put(f"/api/v1/users/{user_id}", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["first_name"] == "Jane"
        assert data["email"] == "jane@example.com"
        assert data["role"] == "organizer"

    @pytest.mark.req("REQ-USR-B02")
    def test_put_user_not_found(self, client):
        payload = {"first_name": "Jane", "last_name": "Smith", "email": "jane@example.com"}
        response = client.put("/api/v1/users/00000000-0000-0000-0000-000000000000", json=payload)
        assert response.status_code == 404

    @pytest.mark.req("REQ-USR-B02")
    def test_put_user_missing_required(self, client):
        create_resp = client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"})
        user_id = create_resp.get_json()["id"]

        payload = {"first_name": "Jane"}
        response = client.put(f"/api/v1/users/{user_id}", json=payload)
        assert response.status_code == 422
        data = response.get_json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.req("REQ-USR-B02")
    def test_patch_user_success(self, client):
        create_resp = client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"})
        user_id = create_resp.get_json()["id"]

        response = client.patch(f"/api/v1/users/{user_id}", json={"first_name": "Jane", "role": "organizer"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["first_name"] == "Jane"
        assert data["role"] == "organizer"
        assert data["last_name"] == "Doe"  # unchanged

    @pytest.mark.req("REQ-USR-B02")
    def test_patch_user_not_found(self, client):
        response = client.patch("/api/v1/users/00000000-0000-0000-0000-000000000000", json={"first_name": "Jane"})
        assert response.status_code == 404

    @pytest.mark.req("REQ-USR-B02")
    def test_patch_user_invalid_email(self, client):
        create_resp = client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"})
        user_id = create_resp.get_json()["id"]

        response = client.patch(f"/api/v1/users/{user_id}", json={"email": "invalid"})
        assert response.status_code == 422

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_patch_user_duplicate_email(self, client):
        client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"})
        create_resp = client.post("/api/v1/users", json={"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com"})
        user_id = create_resp.get_json()["id"]

        response = client.patch(f"/api/v1/users/{user_id}", json={"email": "john@example.com"})
        assert response.status_code == 409

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_delete_user_success(self, client):
        create_resp = client.post("/api/v1/users", json={"first_name": "John", "last_name": "Doe", "email": "john@example.com"})
        user_id = create_resp.get_json()["id"]

        response = client.delete(f"/api/v1/users/{user_id}")
        assert response.status_code == 204

        # Verify deleted
        get_resp = client.get(f"/api/v1/users/{user_id}")
        assert get_resp.status_code == 404

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_delete_user_not_found(self, client):
        response = client.delete("/api/v1/users/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_malformed_json(self, client):
        response = client.post("/api/v1/users", data="{invalid json", content_type="application/json")
        assert response.status_code == 400

    @pytest.mark.req("REQ-USR-B01")
    @pytest.mark.req("REQ-USR-B02")
    def test_method_not_allowed(self, client):
        response = client.post("/api/v1/users/123")  # POST on item endpoint
        assert response.status_code == 405