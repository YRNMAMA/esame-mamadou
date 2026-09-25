"""Event service unit tests."""

import pytest
import tempfile
import os
import requests
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from event_service.models import (
    Event,
    EventCreate,
    EventUpdate,
    validate_event_create,
    validate_event_update,
    validate_status_transition,
    create_event,
    update_event,
    list_events,
)
from event_service.repository import (
    MemoryEventRepository,
    JsonEventRepository,
    SqliteEventRepository,
    create_event_repository,
)
from event_service.config import Config
from event_service.client import UserServiceClient, ReferenceNotFoundError, DependencyUnavailableError


class TestValidation:
    """Test validation functions."""

    def test_valid_event_create(self):
        data = EventCreate(
            title="TechConf 2026",
            organizer_id="123e4567-e89b-12d3-a456-426614174000",
            venue="Auditorium Roma",
            city="Roma",
            start_date="2026-10-15",
            end_date="2026-10-16",
            capacity=100,
            price=149.00,
        )
        errors = validate_event_create(data)
        assert errors == []

    def test_missing_title(self):
        data = EventCreate(title="", organizer_id="1", venue="A", city="Roma", start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        errors = validate_event_create(data)
        assert "title is required" in errors

    def test_title_too_short(self):
        data = EventCreate(title="Ab", organizer_id="1", venue="A", city="Roma", start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        errors = validate_event_create(data)
        assert "title must be between 3 and 120 characters" in errors

    def test_title_too_long(self):
        data = EventCreate(title="x" * 121, organizer_id="1", venue="A", city="Roma", start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        errors = validate_event_create(data)
        assert "title must be between 3 and 120 characters" in errors

    def test_missing_organizer(self):
        data = EventCreate(title="Event", organizer_id="", venue="A", city="Roma", start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        errors = validate_event_create(data)
        assert "organizer_id is required" in errors

    def test_invalid_dates(self):
        data = EventCreate(title="Event", organizer_id="1", venue="A", city="Roma", start_date="invalid", end_date="2026-10-16", capacity=10, price=0)
        errors = validate_event_create(data)
        assert "start_date must be in YYYY-MM-DD format" in errors

    def test_end_before_start(self):
        data = EventCreate(title="Event", organizer_id="1", venue="A", city="Roma", start_date="2026-10-16", end_date="2026-10-15", capacity=10, price=0)
        errors = validate_event_create(data)
        assert "end_date must be on or after start_date" in errors

    def test_invalid_capacity(self):
        data = EventCreate(title="Event", organizer_id="1", venue="A", city="Roma", start_date="2026-10-15", end_date="2026-10-16", capacity=0, price=0)
        errors = validate_event_create(data)
        assert "capacity must be an integer between 1 and 10000" in errors

    def test_negative_price(self):
        data = EventCreate(title="Event", organizer_id="1", venue="A", city="Roma", start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=-10)
        errors = validate_event_create(data)
        assert "price must be a number >= 0" in errors

    def test_invalid_status(self):
        data = EventCreate(title="Event", organizer_id="1", venue="A", city="Roma", start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0, status="invalid")
        errors = validate_event_create(data)
        assert any("status must be one of" in e for e in errors)

    def test_valid_statuses(self):
        for status in ["draft", "published", "cancelled"]:
            data = EventCreate(title="Event", organizer_id="1", venue="A", city="Roma", start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0, status=status)
            errors = validate_event_create(data)
            assert errors == [], f"Failed for status {status}"

    def test_validate_event_update(self):
        data = EventUpdate(title="New Title", price=199.00)
        errors = validate_event_update(data)
        assert errors == []

    def test_update_invalid_dates(self):
        data = EventUpdate(start_date="2026-10-16", end_date="2026-10-15")
        errors = validate_event_update(data)
        assert "end_date must be on or after start_date" in errors

    def test_validate_status_transition(self):
        # Valid transitions
        assert validate_status_transition("draft", "published") is True
        assert validate_status_transition("draft", "cancelled") is True
        assert validate_status_transition("published", "cancelled") is True
        assert validate_status_transition("draft", "draft") is True

        # Invalid transitions
        assert validate_status_transition("published", "draft") is False
        assert validate_status_transition("cancelled", "published") is False
        assert validate_status_transition("cancelled", "draft") is False


class TestMemoryRepository:
    """Test in-memory repository."""

    @pytest.fixture
    def repo(self):
        return MemoryEventRepository()

    def test_create_and_get(self, repo):
        event = Event(
            id="test-id",
            title="TechConf",
            organizer_id="1",
            venue="Auditorium",
            city="Roma",
            start_date="2026-10-15",
            end_date="2026-10-16",
            capacity=100,
            price=149.00,
            status="draft",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        created = repo.create(event)
        assert created.id == "test-id"

        retrieved = repo.get_by_id("test-id")
        assert retrieved is not None
        assert retrieved.title == "TechConf"

    def test_list_events_pagination(self, repo):
        for i in range(5):
            event = Event(id=str(i), title=f"Event{i}", organizer_id="1", venue="V", city="Roma",
                          start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
                          status="draft", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
            repo.create(event)

        result = repo.list_users(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_list_events_status_filter(self, repo):
        event1 = Event(id="1", title="Event1", organizer_id="1", venue="V", city="Roma",
                       start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
                       status="draft", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        event2 = Event(id="2", title="Event2", organizer_id="1", venue="V", city="Roma",
                       start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
                       status="published", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(event1)
        repo.create(event2)

        result = repo.list_users(page=1, page_size=10, status="published")
        assert result["total"] == 1
        item = result["items"][0]
        status = item.status if hasattr(item, "status") else item["status"]
        assert status == "published"

    def test_list_events_city_filter(self, repo):
        event = Event(id="1", title="Event", organizer_id="1", venue="V", city="Roma",
                      start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
                      status="draft", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(event)

        result = repo.list_users(page=1, page_size=10, city="ROMA")
        assert result["total"] == 1
        item = result["items"][0]
        city = item.city if hasattr(item, "city") else item["city"]
        assert city == "Roma"

    def test_update_event(self, repo):
        event = Event(id="1", title="Event", organizer_id="1", venue="V", city="Roma",
                      start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
                      status="draft", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(event)

        updated = repo.update("1", EventUpdate(title="New Title", status="published"))
        assert updated is not None
        assert updated.title == "New Title"
        assert updated.status == "published"
        assert updated.updated_at > "2026-01-01T00:00:00Z"

    def test_update_nonexistent(self, repo):
        updated = repo.update("nonexistent", EventUpdate(title="New"))
        assert updated is None

    def test_delete_event(self, repo):
        event = Event(id="1", title="Event", organizer_id="1", venue="V", city="Roma",
                      start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
                      status="draft", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(event)
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False


class TestJsonRepository:
    """Test JSON file repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return JsonEventRepository(tmp_path)

    def test_create_and_get(self, repo):
        event = Event(
            id="test-id",
            title="TechConf",
            organizer_id="1",
            venue="Auditorium",
            city="Roma",
            start_date="2026-10-15",
            end_date="2026-10-16",
            capacity=100,
            price=149.00,
            status="draft",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        created = repo.create(event)
        assert created.id == "test-id"

        retrieved = repo.get_by_id("test-id")
        assert retrieved is not None
        assert retrieved.title == "TechConf"

    def test_persistence_across_instances(self, tmp_path):
        repo1 = JsonEventRepository(tmp_path)
        event = Event(id="1", title="Event", organizer_id="1", venue="V", city="Roma",
                      start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
                      status="draft", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo1.create(event)

        repo2 = JsonEventRepository(tmp_path)
        retrieved = repo2.get_by_id("1")
        assert retrieved is not None
        assert retrieved.title == "Event"


class TestSqliteRepository:
    """Test SQLite repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return SqliteEventRepository(tmp_path)

    def test_create_and_get(self, repo):
        event = Event(
            id="test-id",
            title="TechConf",
            organizer_id="1",
            venue="Auditorium",
            city="Roma",
            start_date="2026-10-15",
            end_date="2026-10-16",
            capacity=100,
            price=149.00,
            status="draft",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        created = repo.create(event)
        assert created.id == "test-id"

        retrieved = repo.get_by_id("test-id")
        assert retrieved is not None
        assert retrieved.title == "TechConf"

    def test_persistence_across_instances(self, tmp_path):
        repo1 = SqliteEventRepository(tmp_path)
        event = Event(id="1", title="Event", organizer_id="1", venue="V", city="Roma",
                      start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
                      status="draft", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo1.create(event)

        repo2 = SqliteEventRepository(tmp_path)
        retrieved = repo2.get_by_id("1")
        assert retrieved is not None
        assert retrieved.title == "Event"


class TestBusinessLogic:
    """Test business logic functions with mocked user client."""

    @pytest.fixture
    def repo(self):
        return MemoryEventRepository()

    @pytest.fixture
    def user_client(self):
        client = Mock(spec=UserServiceClient)
        client.get_user.return_value = (200, {"id": "1", "role": "organizer"})
        return client

    def test_create_event_success(self, repo, user_client):
        data = EventCreate(
            title="TechConf 2026",
            organizer_id="1",
            venue="Auditorium Roma",
            city="Roma",
            start_date="2026-10-15",
            end_date="2026-10-16",
            capacity=100,
            price=149.00,
        )
        event = create_event(data, repo, user_client)
        assert event.id is not None
        assert event.title == "TechConf 2026"
        assert event.status == "draft"

    def test_create_event_organizer_not_found(self, repo, user_client):
        user_client.get_user.side_effect = ReferenceNotFoundError("Not found")
        data = EventCreate(title="Event", organizer_id="1", venue="V", city="Roma",
                           start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        with pytest.raises(ValueError, match="REFERENCE_NOT_FOUND"):
            create_event(data, repo, user_client)

    def test_create_event_invalid_organizer_role(self, repo, user_client):
        user_client.get_user.return_value = (200, {"id": "1", "role": "attendee"})
        data = EventCreate(title="Event", organizer_id="1", venue="V", city="Roma",
                           start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        with pytest.raises(ValueError, match="INVALID_ORGANIZER"):
            create_event(data, repo, user_client)

    def test_create_event_dependency_unavailable(self, repo, user_client):
        user_client.get_user.side_effect = DependencyUnavailableError("Unavailable")
        data = EventCreate(title="Event", organizer_id="1", venue="V", city="Roma",
                           start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        with pytest.raises(ValueError, match="DEPENDENCY_UNAVAILABLE"):
            create_event(data, repo, user_client)

    def test_update_event_status_transition(self, repo, user_client):
        # Create event
        data = EventCreate(title="Event", organizer_id="1", venue="V", city="Roma",
                           start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        event = create_event(data, repo, user_client)

        # Valid transition draft -> published
        updated = update_event(event.id, EventUpdate(status="published"), repo, user_client)
        assert updated.status == "published"

        # Valid transition published -> cancelled
        updated = update_event(event.id, EventUpdate(status="cancelled"), repo, user_client)
        assert updated.status == "cancelled"

        # Invalid transition cancelled -> published
        with pytest.raises(ValueError, match="INVALID_STATUS_TRANSITION"):
            update_event(event.id, EventUpdate(status="published"), repo, user_client)

    def test_update_event_organizer_change(self, repo, user_client):
        data = EventCreate(title="Event", organizer_id="1", venue="V", city="Roma",
                           start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        event = create_event(data, repo, user_client)

        # Change organizer to valid one
        user_client.get_user.return_value = (200, {"id": "2", "role": "organizer"})
        updated = update_event(event.id, EventUpdate(organizer_id="2"), repo, user_client)
        assert updated.organizer_id == "2"

    def test_update_event_invalid_organizer(self, repo, user_client):
        data = EventCreate(title="Event", organizer_id="1", venue="V", city="Roma",
                           start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0)
        event = create_event(data, repo, user_client)

        user_client.get_user.return_value = (200, {"id": "2", "role": "attendee"})
        with pytest.raises(ValueError, match="INVALID_ORGANIZER"):
            update_event(event.id, EventUpdate(organizer_id="2"), repo, user_client)


class TestConfig:
    """Test configuration."""

    def test_default_config(self):
        with patch.dict(os.environ, {"PORT": "5002"}, clear=True):
            cfg = Config()
            assert cfg.port == 5002
            assert cfg.storage_backend == "memory"

    def test_custom_config(self):
        with patch.dict(os.environ, {"PORT": "8080", "STORAGE_BACKEND": "json", "DATA_DIR": "/tmp/data", "USER_SERVICE_URL": "http://localhost:5001"}, clear=True):
            cfg = Config()
            assert cfg.port == 8080
            assert cfg.storage_backend == "json"
            assert str(cfg.data_dir).endswith("/tmp/data")
            assert cfg.user_service_url == "http://localhost:5001"

    def test_invalid_storage_backend(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "invalid"}, clear=True):
            with pytest.raises(ValueError, match="Invalid STORAGE_BACKEND"):
                Config()

    def test_create_repository_factory(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "memory"}, clear=True):
            cfg = Config()
            repo = create_event_repository(cfg)
            assert isinstance(repo, MemoryEventRepository)

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"STORAGE_BACKEND": "json", "DATA_DIR": tmpdir}, clear=True):
                cfg = Config()
                repo = create_event_repository(cfg)
                assert isinstance(repo, JsonEventRepository)

            with patch.dict(os.environ, {"STORAGE_BACKEND": "sqlite", "DATA_DIR": tmpdir}, clear=True):
                cfg = Config()
                repo = create_event_repository(cfg)
                assert isinstance(repo, SqliteEventRepository)


class TestClient:
    """Test user service client."""

    def test_client_creation(self):
        client = UserServiceClient("http://localhost:5001")
        assert client.base_url == "http://localhost:5001"

    def test_get_user_success(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5001/api/v1/users/123",
                     json={"id": "123", "role": "organizer"}, status=200)
            client = UserServiceClient("http://localhost:5001")
            status, user = client.get_user("123")
            assert status == 200
            assert user["role"] == "organizer"

    def test_get_user_not_found(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5001/api/v1/users/123",
                     status=404)
            client = UserServiceClient("http://localhost:5001")
            with pytest.raises(ReferenceNotFoundError):
                client.get_user("123")

    def test_get_user_unavailable(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5001/api/v1/users/123",
                     status=500)
            client = UserServiceClient("http://localhost:5001")
            with pytest.raises(DependencyUnavailableError):
                client.get_user("123")

    def test_get_user_timeout(self):
        import responses
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, "http://localhost:5001/api/v1/users/123",
                     body=requests.Timeout())
            client = UserServiceClient("http://localhost:5001")
            with pytest.raises(DependencyUnavailableError):
                client.get_user("123")


class TestContractValidation:
    """Test contract validation for each endpoint."""

    def test_event_schema(self):
        event = Event(
            id="123e4567-e89b-12d3-a456-426614174000",
            title="TechConf 2026",
            organizer_id="123e4567-e89b-12d3-a456-426614174000",
            venue="Auditorium Roma",
            city="Roma",
            start_date="2026-10-15",
            end_date="2026-10-16",
            capacity=100,
            price=149.00,
            status="draft",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        data = event.to_dict()
        assert "id" in data
        assert "title" in data
        assert "organizer_id" in data
        assert "venue" in data
        assert "city" in data
        assert "start_date" in data
        assert "end_date" in data
        assert "capacity" in data
        assert "price" in data
        assert "status" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["status"] in ["draft", "published", "cancelled"]

    def test_event_page_schema(self):
        repo = MemoryEventRepository()
        result = repo.list_users(1, 20, None, None)
        assert "items" in result
        assert "page" in result
        assert "page_size" in result
        assert "total" in result


# ---------------------------------------------------------------------------
# Additional tests for JSON and SQLite repositories (coverage ≥ 80%)
# ---------------------------------------------------------------------------

class TestJsonRepositoryExtended:
    """Extended tests for JSON event repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return JsonEventRepository(tmp_path)

    def _make_event(self, event_id: str, title: str = "Event", status: str = "draft", city: str = "Roma") -> Event:
        return Event(
            id=event_id, title=title, organizer_id="1", venue="V", city=city,
            start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
            status=status, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        )

    def test_list_events_pagination(self, repo):
        for i in range(5):
            repo.create(self._make_event(str(i), title=f"Event{i}"))

        result = repo.list_users(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 2

    def test_list_events_status_filter(self, repo):
        repo.create(self._make_event("1", title="Draft Event", status="draft"))
        repo.create(self._make_event("2", title="Published Event", status="published"))

        result = repo.list_users(page=1, page_size=10, status="published")
        assert result["total"] == 1
        item = result["items"][0]
        st = item.status if hasattr(item, "status") else item["status"]
        assert st == "published"

    def test_list_events_city_filter(self, repo):
        repo.create(self._make_event("1", city="Roma"))
        repo.create(self._make_event("2", city="Milano"))

        result = repo.list_users(page=1, page_size=10, city="roma")
        assert result["total"] == 1
        item = result["items"][0]
        c = item.city if hasattr(item, "city") else item["city"]
        assert c == "Roma"

    def test_update_event(self, repo):
        repo.create(self._make_event("1"))

        updated = repo.update("1", EventUpdate(title="New Title", status="published"))
        assert updated is not None
        assert updated.title == "New Title"
        assert updated.status == "published"
        assert updated.updated_at > "2026-01-01T00:00:00Z"

    def test_update_nonexistent(self, repo):
        updated = repo.update("nonexistent", EventUpdate(title="New"))
        assert updated is None

    def test_update_all_fields(self, repo):
        repo.create(self._make_event("1"))

        updated = repo.update("1", EventUpdate(
            title="Updated",
            description="A description",
            organizer_id="2",
            venue="New Venue",
            city="Milano",
            start_date="2026-11-01",
            end_date="2026-11-02",
            capacity=200,
            price=50.0,
            status="published",
        ))
        assert updated is not None
        assert updated.title == "Updated"
        assert updated.city == "Milano"
        assert updated.capacity == 200

    def test_delete_event(self, repo):
        repo.create(self._make_event("1"))
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False

    def test_list_empty(self, repo):
        result = repo.list_users(page=1, page_size=10)
        assert result["total"] == 0
        assert result["items"] == []

    def test_list_second_page(self, repo):
        for i in range(4):
            repo.create(self._make_event(str(i), title=f"Event{i}"))

        result = repo.list_users(page=2, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 4


class TestSqliteRepositoryExtended:
    """Extended tests for SQLite event repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return SqliteEventRepository(tmp_path)

    def _make_event(self, event_id: str, title: str = "Event", status: str = "draft", city: str = "Roma") -> Event:
        return Event(
            id=event_id, title=title, organizer_id="1", venue="V", city=city,
            start_date="2026-10-15", end_date="2026-10-16", capacity=10, price=0,
            status=status, created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z",
        )

    def test_list_events_pagination(self, repo):
        for i in range(5):
            repo.create(self._make_event(str(i), title=f"Event{i}"))

        result = repo.list_users(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_list_events_status_filter(self, repo):
        repo.create(self._make_event("1", title="Draft Event", status="draft"))
        repo.create(self._make_event("2", title="Published Event", status="published"))

        result = repo.list_users(page=1, page_size=10, status="published")
        assert result["total"] == 1

    def test_list_events_city_filter(self, repo):
        repo.create(self._make_event("1", city="Roma"))
        repo.create(self._make_event("2", city="Milano"))

        result = repo.list_users(page=1, page_size=10, city="ROMA")
        assert result["total"] == 1

    def test_update_event(self, repo):
        repo.create(self._make_event("1"))

        updated = repo.update("1", EventUpdate(title="New Title", status="published"))
        assert updated is not None
        assert updated.title == "New Title"
        assert updated.status == "published"

    def test_update_nonexistent(self, repo):
        updated = repo.update("nonexistent", EventUpdate(title="New"))
        assert updated is None

    def test_update_all_fields(self, repo):
        repo.create(self._make_event("1"))

        updated = repo.update("1", EventUpdate(
            title="Updated",
            description="A description",
            organizer_id="2",
            venue="New Venue",
            city="Milano",
            start_date="2026-11-01",
            end_date="2026-11-02",
            capacity=200,
            price=50.0,
            status="published",
        ))
        assert updated is not None
        assert updated.title == "Updated"
        assert updated.capacity == 200

    def test_delete_event(self, repo):
        repo.create(self._make_event("1"))
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False

    def test_list_empty(self, repo):
        result = repo.list_users(page=1, page_size=10)
        assert result["total"] == 0
        assert result["items"] == []

    def test_list_second_page(self, repo):
        for i in range(4):
            repo.create(self._make_event(str(i), title=f"Event{i}"))

        result = repo.list_users(page=2, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 4


# Every test has exactly one requirement marker. Keeping the mapping explicit makes
# traceability reviewable without coupling unrelated tests to a class-level marker.
_REQUIREMENT_TRACEABILITY = {
    TestValidation: {
        "test_valid_event_create": "REQ-EVT-B03",
        "test_missing_title": "REQ-EVT-B03",
        "test_title_too_short": "REQ-EVT-B03",
        "test_title_too_long": "REQ-EVT-B03",
        "test_missing_organizer": "REQ-EVT-B01",
        "test_invalid_dates": "REQ-EVT-B03",
        "test_end_before_start": "REQ-EVT-B03",
        "test_invalid_capacity": "REQ-EVT-B03",
        "test_negative_price": "REQ-EVT-B03",
        "test_invalid_status": "REQ-EVT-B04",
        "test_valid_statuses": "REQ-EVT-B04",
        "test_validate_event_update": "REQ-EVT-B03",
        "test_update_invalid_dates": "REQ-EVT-B03",
        "test_validate_status_transition": "REQ-EVT-B04",
    },
    TestMemoryRepository: {
        "test_create_and_get": "REQ-EVT-B04",
        "test_list_events_pagination": "REQ-EVT-B06",
        "test_list_events_status_filter": "REQ-EVT-B06",
        "test_list_events_city_filter": "REQ-EVT-B06",
        "test_update_event": "REQ-EVT-B04",
        "test_update_nonexistent": "REQ-EVT-B04",
        "test_delete_event": "REQ-EVT-B04",
    },
    TestJsonRepository: {
        "test_create_and_get": "REQ-EVT-B04",
        "test_persistence_across_instances": "REQ-EVT-B04",
    },
    TestSqliteRepository: {
        "test_create_and_get": "REQ-EVT-B04",
        "test_persistence_across_instances": "REQ-EVT-B04",
    },
    TestBusinessLogic: {
        "test_create_event_success": "REQ-EVT-B01",
        "test_create_event_organizer_not_found": "REQ-EVT-B01",
        "test_create_event_invalid_organizer_role": "REQ-EVT-B02",
        "test_create_event_dependency_unavailable": "REQ-EVT-B05",
        "test_update_event_status_transition": "REQ-EVT-B04",
        "test_update_event_organizer_change": "REQ-EVT-B01",
        "test_update_event_invalid_organizer": "REQ-EVT-B02",
    },
    TestConfig: {
        "test_default_config": "REQ-EVT-B05",
        "test_custom_config": "REQ-EVT-B05",
        "test_invalid_storage_backend": "REQ-EVT-B06",
        "test_create_repository_factory": "REQ-EVT-B06",
    },
    TestClient: {
        "test_client_creation": "REQ-EVT-B01",
        "test_get_user_success": "REQ-EVT-B01",
        "test_get_user_not_found": "REQ-EVT-B01",
        "test_get_user_unavailable": "REQ-EVT-B05",
        "test_get_user_timeout": "REQ-EVT-B05",
    },
    TestContractValidation: {
        "test_event_schema": "REQ-EVT-B04",
        "test_event_page_schema": "REQ-EVT-B06",
    },
    TestJsonRepositoryExtended: {
        "test_list_events_pagination": "REQ-EVT-B06",
        "test_list_events_status_filter": "REQ-EVT-B06",
        "test_list_events_city_filter": "REQ-EVT-B06",
        "test_update_event": "REQ-EVT-B04",
        "test_update_nonexistent": "REQ-EVT-B04",
        "test_update_all_fields": "REQ-EVT-B03",
        "test_delete_event": "REQ-EVT-B04",
        "test_list_empty": "REQ-EVT-B06",
        "test_list_second_page": "REQ-EVT-B06",
    },
    TestSqliteRepositoryExtended: {
        "test_list_events_pagination": "REQ-EVT-B06",
        "test_list_events_status_filter": "REQ-EVT-B06",
        "test_list_events_city_filter": "REQ-EVT-B06",
        "test_update_event": "REQ-EVT-B04",
        "test_update_nonexistent": "REQ-EVT-B04",
        "test_update_all_fields": "REQ-EVT-B03",
        "test_delete_event": "REQ-EVT-B04",
        "test_list_empty": "REQ-EVT-B06",
        "test_list_second_page": "REQ-EVT-B06",
    },
}

for _test_class, _test_requirements in _REQUIREMENT_TRACEABILITY.items():
    for _test_name, _requirement_id in _test_requirements.items():
        setattr(
            _test_class,
            _test_name,
            pytest.mark.req(_requirement_id)(getattr(_test_class, _test_name)),
        )
