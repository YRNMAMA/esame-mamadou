"""Registration service unit tests."""

import pytest
import tempfile
import os
import requests
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from registration_service.models import (
    Registration,
    RegistrationCreate,
    RegistrationPatch,
    RegistrationStats,
    validate_registration_create,
    validate_registration_patch,
    validate_status_transition,
    create_registration,
    update_registration,
    get_stats,
    list_registrations,
)
from registration_service.repository import (
    MemoryRegistrationRepository,
    JsonRegistrationRepository,
    SqliteRegistrationRepository,
    create_registration_repository,
)
from registration_service.config import Config
from registration_service.client import (
    UserServiceClient,
    EventServiceClient,
    ReferenceNotFoundError,
    DependencyUnavailableError,
)


class TestValidation:
    """Test validation functions."""

    def test_valid_registration_create(self):
        data = RegistrationCreate(user_id="1", event_id="2")
        errors = validate_registration_create(data)
        assert errors == []

    def test_missing_user_id(self):
        data = RegistrationCreate(user_id="", event_id="2")
        errors = validate_registration_create(data)
        assert "user_id is required" in errors

    def test_missing_event_id(self):
        data = RegistrationCreate(user_id="1", event_id="")
        errors = validate_registration_create(data)
        assert "event_id is required" in errors

    def test_validate_registration_patch(self):
        data = RegistrationPatch(status="cancelled")
        errors = validate_registration_patch(data)
        assert errors == []

    def test_invalid_status(self):
        data = RegistrationPatch(status="invalid")
        errors = validate_registration_patch(data)
        assert any("status must be one of" in e for e in errors)

    def test_validate_status_transition(self):
        # Valid transitions
        assert validate_status_transition("confirmed", "cancelled") is True
        assert validate_status_transition("confirmed", "confirmed") is True

        # Invalid transitions
        assert validate_status_transition("cancelled", "confirmed") is False
        assert validate_status_transition("cancelled", "cancelled") is True


class TestMemoryRepository:
    """Test in-memory repository."""

    @pytest.fixture
    def repo(self):
        return MemoryRegistrationRepository()

    def test_create_and_get(self, repo):
        reg = Registration(
            id="test-id",
            user_id="1",
            event_id="2",
            amount=149.00,
            status="confirmed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        created = repo.create(reg)
        assert created.id == "test-id"

        retrieved = repo.get_by_id("test-id")
        assert retrieved is not None
        assert retrieved.amount == 149.00

    def test_get_by_user_and_event(self, repo):
        reg = Registration(id="1", user_id="1", event_id="2", amount=100, status="confirmed",
                           created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(reg)

        found = repo.get_by_user_and_event("1", "2")
        assert found is not None
        assert found.id == "1"

        not_found = repo.get_by_user_and_event("1", "3")
        assert not_found is None

    def test_list_registrations_pagination(self, repo):
        for i in range(5):
            reg = Registration(id=str(i), user_id="1", event_id="2", amount=100, status="confirmed",
                               created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
            repo.create(reg)

        result = repo.list_registrations(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_list_registrations_filters(self, repo):
        reg1 = Registration(id="1", user_id="1", event_id="2", amount=100, status="confirmed",
                            created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        reg2 = Registration(id="2", user_id="2", event_id="3", amount=100, status="cancelled",
                            created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(reg1)
        repo.create(reg2)

        result = repo.list_registrations(page=1, page_size=10, user_id="1")
        assert result["total"] == 1

        result = repo.list_registrations(page=1, page_size=10, status="cancelled")
        assert result["total"] == 1

    def test_update_status(self, repo):
        reg = Registration(id="1", user_id="1", event_id="2", amount=100, status="confirmed",
                           created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(reg)

        updated = repo.update_status("1", "cancelled")
        assert updated is not None
        assert updated.status == "cancelled"
        assert updated.updated_at > "2026-01-01T00:00:00Z"

    def test_update_status_nonexistent(self, repo):
        updated = repo.update_status("nonexistent", "cancelled")
        assert updated is None

    def test_delete(self, repo):
        reg = Registration(id="1", user_id="1", event_id="2", amount=100, status="confirmed",
                           created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(reg)
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False

    def test_count_confirmed_for_event(self, repo):
        for i in range(3):
            reg = Registration(id=str(i), user_id=str(i), event_id="2", amount=100,
                               status="confirmed" if i < 2 else "cancelled",
                               created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
            repo.create(reg)

        count = repo.count_confirmed_for_event("2")
        assert count == 2


class TestJsonRepository:
    """Test JSON file repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return JsonRegistrationRepository(tmp_path)

    def test_create_and_get(self, repo):
        reg = Registration(id="1", user_id="1", event_id="2", amount=100, status="confirmed",
                           created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(reg)
        retrieved = repo.get_by_id("1")
        assert retrieved is not None
        assert retrieved.amount == 100

    def test_persistence_across_instances(self, tmp_path):
        repo1 = JsonRegistrationRepository(tmp_path)
        reg = Registration(id="1", user_id="1", event_id="2", amount=100, status="confirmed",
                           created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo1.create(reg)

        repo2 = JsonRegistrationRepository(tmp_path)
        retrieved = repo2.get_by_id("1")
        assert retrieved is not None


class TestSqliteRepository:
    """Test SQLite repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return SqliteRegistrationRepository(tmp_path)

    def test_create_and_get(self, repo):
        reg = Registration(id="1", user_id="1", event_id="2", amount=100, status="confirmed",
                           created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(reg)
        retrieved = repo.get_by_id("1")
        assert retrieved is not None
        assert retrieved.amount == 100

    def test_persistence_across_instances(self, tmp_path):
        repo1 = SqliteRegistrationRepository(tmp_path)
        reg = Registration(id="1", user_id="1", event_id="2", amount=100, status="confirmed",
                           created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo1.create(reg)

        repo2 = SqliteRegistrationRepository(tmp_path)
        retrieved = repo2.get_by_id("1")
        assert retrieved is not None


class TestBusinessLogic:
    """Test business logic functions with mocked clients."""

    @pytest.fixture
    def repo(self):
        return MemoryRegistrationRepository()

    @pytest.fixture
    def user_client(self):
        client = Mock(spec=UserServiceClient)
        client.get_user.return_value = (200, {"id": "1", "role": "attendee"})
        return client

    @pytest.fixture
    def event_client(self):
        client = Mock(spec=EventServiceClient)
        client.get_event.return_value = (200, {"id": "2", "status": "published", "capacity": 10, "price": 149.00})
        return client

    def test_create_registration_success(self, repo, user_client, event_client):
        data = RegistrationCreate(user_id="1", event_id="2")
        reg = create_registration(data, repo, user_client, event_client)
        assert reg.id is not None
        assert reg.status == "confirmed"
        assert reg.amount == 149.00

    def test_create_registration_user_not_found(self, repo, user_client, event_client):
        user_client.get_user.side_effect = ReferenceNotFoundError("Not found")
        data = RegistrationCreate(user_id="1", event_id="2")
        with pytest.raises(ValueError, match="REFERENCE_NOT_FOUND"):
            create_registration(data, repo, user_client, event_client)

    def test_create_registration_event_not_found(self, repo, user_client, event_client):
        event_client.get_event.side_effect = ReferenceNotFoundError("Not found")
        data = RegistrationCreate(user_id="1", event_id="2")
        with pytest.raises(ValueError, match="REFERENCE_NOT_FOUND"):
            create_registration(data, repo, user_client, event_client)

    def test_create_registration_event_not_published(self, repo, user_client, event_client):
        event_client.get_event.return_value = (200, {"id": "2", "status": "draft", "capacity": 10, "price": 149.00})
        data = RegistrationCreate(user_id="1", event_id="2")
        with pytest.raises(ValueError, match="EVENT_NOT_OPEN"):
            create_registration(data, repo, user_client, event_client)

    def test_create_registration_already_registered(self, repo, user_client, event_client):
        data = RegistrationCreate(user_id="1", event_id="2")
        create_registration(data, repo, user_client, event_client)
        with pytest.raises(ValueError, match="ALREADY_REGISTERED"):
            create_registration(data, repo, user_client, event_client)

    def test_create_registration_event_full(self, repo, user_client, event_client):
        event_client.get_event.return_value = (200, {"id": "2", "status": "published", "capacity": 1, "price": 149.00})
        data1 = RegistrationCreate(user_id="1", event_id="2")
        data2 = RegistrationCreate(user_id="3", event_id="2")
        create_registration(data1, repo, user_client, event_client)
        with pytest.raises(ValueError, match="EVENT_FULL"):
            create_registration(data2, repo, user_client, event_client)

    def test_create_registration_dependency_unavailable(self, repo, user_client, event_client):
        user_client.get_user.side_effect = DependencyUnavailableError("Unavailable")
        data = RegistrationCreate(user_id="1", event_id="2")
        with pytest.raises(ValueError, match="DEPENDENCY_UNAVAILABLE"):
            create_registration(data, repo, user_client, event_client)

    def test_update_registration_status(self, repo, user_client, event_client):
        data = RegistrationCreate(user_id="1", event_id="2")
        reg = create_registration(data, repo, user_client, event_client)

        updated = update_registration(reg.id, RegistrationPatch(status="cancelled"), repo)
        assert updated is not None
        assert updated.status == "cancelled"

    def test_update_registration_invalid_transition(self, repo, user_client, event_client):
        data = RegistrationCreate(user_id="1", event_id="2")
        reg = create_registration(data, repo, user_client, event_client)
        # Cancel it
        update_registration(reg.id, RegistrationPatch(status="cancelled"), repo)
        # Try to re-confirm
        with pytest.raises(ValueError, match="INVALID_STATUS_TRANSITION"):
            update_registration(reg.id, RegistrationPatch(status="confirmed"), repo)

    def test_update_registration_not_found(self, repo, user_client, event_client):
        updated = update_registration("nonexistent", RegistrationPatch(status="cancelled"), repo)
        assert updated is None

    def test_get_stats(self, repo, user_client, event_client):
        data = RegistrationCreate(user_id="1", event_id="2")
        create_registration(data, repo, user_client, event_client)

        stats = get_stats("2", repo, event_client)
        assert stats.event_id == "2"
        assert stats.capacity == 10
        assert stats.confirmed == 1
        assert stats.available == 9

    def test_get_stats_event_not_found(self, repo, user_client, event_client):
        event_client.get_event.side_effect = ReferenceNotFoundError("Not found")
        with pytest.raises(ValueError, match="NOT_FOUND"):
            get_stats("2", repo, event_client)

    def test_list_registrations(self, repo, user_client, event_client):
        for i in range(3):
            create_registration(RegistrationCreate(user_id=str(i), event_id="2"), repo, user_client, event_client)

        result = list_registrations(1, 2, None, "2", None, repo)
        assert len(result["items"]) == 2
        assert result["total"] == 3


class TestConfig:
    """Test configuration."""

    def test_default_config(self):
        with patch.dict(os.environ, {"PORT": "5003"}, clear=True):
            cfg = Config()
            assert cfg.port == 5003
            assert cfg.storage_backend == "memory"

    def test_custom_config(self):
        with patch.dict(os.environ, {"PORT": "8080", "STORAGE_BACKEND": "json", "DATA_DIR": "/tmp/data",
                                     "USER_SERVICE_URL": "http://localhost:5001", "EVENT_SERVICE_URL": "http://localhost:5002"}, clear=True):
            cfg = Config()
            assert cfg.port == 8080
            assert cfg.storage_backend == "json"
            assert str(cfg.data_dir).endswith("/tmp/data")

    def test_invalid_storage_backend(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "invalid"}, clear=True):
            with pytest.raises(ValueError, match="Invalid STORAGE_BACKEND"):
                Config()

    def test_create_repository_factory(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "memory"}, clear=True):
            cfg = Config()
            repo = create_registration_repository(cfg)
            assert isinstance(repo, MemoryRegistrationRepository)

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"STORAGE_BACKEND": "json", "DATA_DIR": tmpdir}, clear=True):
                cfg = Config()
                repo = create_registration_repository(cfg)
                assert isinstance(repo, JsonRegistrationRepository)

            with patch.dict(os.environ, {"STORAGE_BACKEND": "sqlite", "DATA_DIR": tmpdir}, clear=True):
                cfg = Config()
                repo = create_registration_repository(cfg)
                assert isinstance(repo, SqliteRegistrationRepository)


class TestClients:
    """Test service clients."""

    def test_user_client_creation(self):
        client = UserServiceClient("http://localhost:5001")
        assert client.base_url == "http://localhost:5001"

    def test_event_client_creation(self):
        client = EventServiceClient("http://localhost:5002")
        assert client.base_url == "http://localhost:5002"

    def test_user_client_get_user_success(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5001/api/v1/users/123",
                     json={"id": "123", "role": "attendee"}, status=200)
            client = UserServiceClient("http://localhost:5001")
            status, user = client.get_user("123")
            assert status == 200
            assert user["role"] == "attendee"

    def test_user_client_get_user_not_found(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5001/api/v1/users/123", status=404)
            client = UserServiceClient("http://localhost:5001")
            with pytest.raises(ReferenceNotFoundError):
                client.get_user("123")

    def test_user_client_get_user_unavailable(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5001/api/v1/users/123", status=500)
            client = UserServiceClient("http://localhost:5001")
            with pytest.raises(DependencyUnavailableError):
                client.get_user("123")

    def test_event_client_get_event_success(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5002/api/v1/events/123",
                     json={"id": "123", "status": "published", "capacity": 10, "price": 149.00}, status=200)
            client = EventServiceClient("http://localhost:5002")
            status, event = client.get_event("123")
            assert status == 200
            assert event["status"] == "published"

    def test_event_client_get_event_not_found(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5002/api/v1/events/123", status=404)
            client = EventServiceClient("http://localhost:5002")
            with pytest.raises(ReferenceNotFoundError):
                client.get_event("123")


class TestContractValidation:
    """Test contract validation for each endpoint."""

    def test_registration_schema(self):
        reg = Registration(
            id="123e4567-e89b-12d3-a456-426614174000",
            user_id="123e4567-e89b-12d3-a456-426614174000",
            event_id="123e4567-e89b-12d3-a456-426614174001",
            amount=149.00,
            status="confirmed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        data = reg.to_dict()
        assert "id" in data
        assert "user_id" in data
        assert "event_id" in data
        assert "amount" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["status"] in ["confirmed", "cancelled"]

    def test_registration_page_schema(self):
        repo = MemoryRegistrationRepository()
        result = repo.list_registrations(1, 20, None, None, None)
        assert "items" in result
        assert "page" in result
        assert "page_size" in result
        assert "total" in result

    def test_registration_stats_schema(self):
        stats = RegistrationStats(event_id="1", capacity=10, confirmed=5, available=5)
        assert stats.event_id == "1"
        assert stats.capacity == 10
        assert stats.confirmed == 5
        assert stats.available == 5


# ---------------------------------------------------------------------------
# Additional tests for JSON and SQLite repositories (coverage ≥ 80%)
# ---------------------------------------------------------------------------

class TestJsonRepositoryExtended:
    """Extended tests for JSON registration repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return JsonRegistrationRepository(tmp_path)

    def _make_reg(self, reg_id: str, user_id: str = "1", event_id: str = "2",
                  status: str = "confirmed") -> Registration:
        return Registration(
            id=reg_id, user_id=user_id, event_id=event_id, amount=100.0,
            status=status, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        )

    def test_list_registrations_pagination(self, repo):
        for i in range(5):
            repo.create(self._make_reg(str(i), user_id=str(i)))

        result = repo.list_registrations(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 2

    def test_list_registrations_user_filter(self, repo):
        repo.create(self._make_reg("1", user_id="u1"))
        repo.create(self._make_reg("2", user_id="u2"))

        result = repo.list_registrations(page=1, page_size=10, user_id="u1")
        assert result["total"] == 1

    def test_list_registrations_event_filter(self, repo):
        repo.create(self._make_reg("1", event_id="e1"))
        repo.create(self._make_reg("2", event_id="e2"))

        result = repo.list_registrations(page=1, page_size=10, event_id="e1")
        assert result["total"] == 1

    def test_list_registrations_status_filter(self, repo):
        repo.create(self._make_reg("1", status="confirmed"))
        repo.create(self._make_reg("2", user_id="2", status="cancelled"))

        result = repo.list_registrations(page=1, page_size=10, status="cancelled")
        assert result["total"] == 1

    def test_update_status(self, repo):
        repo.create(self._make_reg("1"))

        updated = repo.update_status("1", "cancelled")
        assert updated is not None
        assert updated.status == "cancelled"
        assert updated.updated_at > "2026-01-01T00:00:00Z"

    def test_update_status_nonexistent(self, repo):
        updated = repo.update_status("nonexistent", "cancelled")
        assert updated is None

    def test_delete(self, repo):
        repo.create(self._make_reg("1"))
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False

    def test_count_confirmed_for_event(self, repo):
        repo.create(self._make_reg("1", user_id="u1", event_id="e1", status="confirmed"))
        repo.create(self._make_reg("2", user_id="u2", event_id="e1", status="confirmed"))
        repo.create(self._make_reg("3", user_id="u3", event_id="e1", status="cancelled"))
        repo.create(self._make_reg("4", user_id="u4", event_id="e2", status="confirmed"))

        count = repo.count_confirmed_for_event("e1")
        assert count == 2

    def test_get_by_user_and_event(self, repo):
        repo.create(self._make_reg("1", user_id="u1", event_id="e1"))
        found = repo.get_by_user_and_event("u1", "e1")
        assert found is not None
        assert found.id == "1"

        not_found = repo.get_by_user_and_event("u1", "e99")
        assert not_found is None

    def test_list_second_page(self, repo):
        for i in range(4):
            repo.create(self._make_reg(str(i), user_id=str(i)))

        result = repo.list_registrations(page=2, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 4


class TestSqliteRepositoryExtended:
    """Extended tests for SQLite registration repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return SqliteRegistrationRepository(tmp_path)

    def _make_reg(self, reg_id: str, user_id: str = "1", event_id: str = "2",
                  status: str = "confirmed") -> Registration:
        return Registration(
            id=reg_id, user_id=user_id, event_id=event_id, amount=100.0,
            status=status, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        )

    def test_list_registrations_pagination(self, repo):
        for i in range(5):
            repo.create(self._make_reg(str(i), user_id=str(i)))

        result = repo.list_registrations(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_list_registrations_user_filter(self, repo):
        repo.create(self._make_reg("1", user_id="u1"))
        repo.create(self._make_reg("2", user_id="u2"))

        result = repo.list_registrations(page=1, page_size=10, user_id="u1")
        assert result["total"] == 1

    def test_list_registrations_event_filter(self, repo):
        repo.create(self._make_reg("1", event_id="e1"))
        repo.create(self._make_reg("2", user_id="2", event_id="e2"))

        result = repo.list_registrations(page=1, page_size=10, event_id="e1")
        assert result["total"] == 1

    def test_list_registrations_status_filter(self, repo):
        repo.create(self._make_reg("1", status="confirmed"))
        repo.create(self._make_reg("2", user_id="2", status="cancelled"))

        result = repo.list_registrations(page=1, page_size=10, status="cancelled")
        assert result["total"] == 1

    def test_update_status(self, repo):
        repo.create(self._make_reg("1"))

        updated = repo.update_status("1", "cancelled")
        assert updated is not None
        assert updated.status == "cancelled"
        assert updated.updated_at > "2026-01-01T00:00:00Z"

    def test_update_status_nonexistent(self, repo):
        updated = repo.update_status("nonexistent", "cancelled")
        assert updated is None

    def test_delete(self, repo):
        repo.create(self._make_reg("1"))
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False

    def test_count_confirmed_for_event(self, repo):
        repo.create(self._make_reg("1", user_id="u1", event_id="e1", status="confirmed"))
        repo.create(self._make_reg("2", user_id="u2", event_id="e1", status="confirmed"))
        repo.create(self._make_reg("3", user_id="u3", event_id="e1", status="cancelled"))
        repo.create(self._make_reg("4", user_id="u4", event_id="e2", status="confirmed"))

        count = repo.count_confirmed_for_event("e1")
        assert count == 2

    def test_get_by_user_and_event(self, repo):
        repo.create(self._make_reg("1", user_id="u1", event_id="e1"))
        found = repo.get_by_user_and_event("u1", "e1")
        assert found is not None
        assert found.id == "1"

        not_found = repo.get_by_user_and_event("u1", "e99")
        assert not_found is None

    def test_list_second_page(self, repo):
        for i in range(4):
            repo.create(self._make_reg(str(i), user_id=str(i)))

        result = repo.list_registrations(page=2, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 4


# A single, behavior-specific requirement marker is attached to every test below.
# Keeping this registry centralized makes omissions and duplicate trace links easy
# to validate without changing the test names used by the existing suite.
_REQUIREMENT_TRACEABILITY = {
    TestValidation: {
        "test_valid_registration_create": "REQ-REG-B01",
        "test_missing_user_id": "REQ-REG-B01",
        "test_missing_event_id": "REQ-REG-B02",
        "test_validate_registration_patch": "REQ-REG-B07",
        "test_invalid_status": "REQ-REG-B07",
        "test_validate_status_transition": "REQ-REG-B07",
    },
    TestMemoryRepository: {
        "test_create_and_get": "REQ-REG-B06",
        "test_get_by_user_and_event": "REQ-REG-B04",
        "test_list_registrations_pagination": "REQ-REG-B05",
        "test_list_registrations_filters": "REQ-REG-B07",
        "test_update_status": "REQ-REG-B07",
        "test_update_status_nonexistent": "REQ-REG-B07",
        "test_delete": "REQ-REG-B05",
        "test_count_confirmed_for_event": "REQ-REG-B05",
    },
    TestJsonRepository: {
        "test_create_and_get": "REQ-REG-B06",
        "test_persistence_across_instances": "REQ-REG-B06",
    },
    TestSqliteRepository: {
        "test_create_and_get": "REQ-REG-B06",
        "test_persistence_across_instances": "REQ-REG-B06",
    },
    TestBusinessLogic: {
        "test_create_registration_success": "REQ-REG-B06",
        "test_create_registration_user_not_found": "REQ-REG-B01",
        "test_create_registration_event_not_found": "REQ-REG-B02",
        "test_create_registration_event_not_published": "REQ-REG-B03",
        "test_create_registration_already_registered": "REQ-REG-B04",
        "test_create_registration_event_full": "REQ-REG-B05",
        "test_create_registration_dependency_unavailable": "REQ-REG-B09",
        "test_update_registration_status": "REQ-REG-B07",
        "test_update_registration_invalid_transition": "REQ-REG-B07",
        "test_update_registration_not_found": "REQ-REG-B07",
        "test_get_stats": "REQ-REG-B08",
        "test_get_stats_event_not_found": "REQ-REG-B08",
        "test_list_registrations": "REQ-REG-B05",
    },
    TestConfig: {
        "test_default_config": "REQ-REG-B09",
        "test_custom_config": "REQ-REG-B09",
        "test_invalid_storage_backend": "REQ-REG-B09",
        "test_create_repository_factory": "REQ-REG-B05",
    },
    TestClients: {
        "test_user_client_creation": "REQ-REG-B01",
        "test_event_client_creation": "REQ-REG-B02",
        "test_user_client_get_user_success": "REQ-REG-B01",
        "test_user_client_get_user_not_found": "REQ-REG-B01",
        "test_user_client_get_user_unavailable": "REQ-REG-B09",
        "test_event_client_get_event_success": "REQ-REG-B02",
        "test_event_client_get_event_not_found": "REQ-REG-B02",
    },
    TestContractValidation: {
        "test_registration_schema": "REQ-REG-B06",
        "test_registration_page_schema": "REQ-REG-B05",
        "test_registration_stats_schema": "REQ-REG-B08",
    },
    TestJsonRepositoryExtended: {
        "test_list_registrations_pagination": "REQ-REG-B05",
        "test_list_registrations_user_filter": "REQ-REG-B04",
        "test_list_registrations_event_filter": "REQ-REG-B05",
        "test_list_registrations_status_filter": "REQ-REG-B07",
        "test_update_status": "REQ-REG-B07",
        "test_update_status_nonexistent": "REQ-REG-B07",
        "test_delete": "REQ-REG-B05",
        "test_count_confirmed_for_event": "REQ-REG-B05",
        "test_get_by_user_and_event": "REQ-REG-B04",
        "test_list_second_page": "REQ-REG-B05",
    },
    TestSqliteRepositoryExtended: {
        "test_list_registrations_pagination": "REQ-REG-B05",
        "test_list_registrations_user_filter": "REQ-REG-B04",
        "test_list_registrations_event_filter": "REQ-REG-B05",
        "test_list_registrations_status_filter": "REQ-REG-B07",
        "test_update_status": "REQ-REG-B07",
        "test_update_status_nonexistent": "REQ-REG-B07",
        "test_delete": "REQ-REG-B05",
        "test_count_confirmed_for_event": "REQ-REG-B05",
        "test_get_by_user_and_event": "REQ-REG-B04",
        "test_list_second_page": "REQ-REG-B05",
    },
}

for _test_class, _test_requirements in _REQUIREMENT_TRACEABILITY.items():
    for _test_name, _requirement_id in _test_requirements.items():
        _test = getattr(_test_class, _test_name)
        setattr(_test_class, _test_name, pytest.mark.req(_requirement_id)(_test))

del _test_class, _test_requirements, _test_name, _requirement_id, _test
