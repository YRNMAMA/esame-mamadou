"""User service unit tests."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from user_service.models import (
    User,
    UserCreate,
    UserUpdate,
    validate_user_create,
    validate_user_update,
    normalize_email,
    create_user,
    update_user,
    list_users,
)
from user_service.repository import (
    MemoryUserRepository,
    JsonUserRepository,
    SqliteUserRepository,
    create_user_repository,
)
from user_service.config import Config


class TestValidation:
    """Test validation functions."""

    def test_valid_user_create(self):
        data = UserCreate(first_name="John", last_name="Doe", email="john@example.com")
        errors = validate_user_create(data)
        assert errors == []

    def test_missing_first_name(self):
        data = UserCreate(first_name="", last_name="Doe", email="john@example.com")
        errors = validate_user_create(data)
        assert "first_name is required" in errors

    def test_first_name_too_long(self):
        data = UserCreate(first_name="x" * 51, last_name="Doe", email="john@example.com")
        errors = validate_user_create(data)
        assert "first_name must be at most 50 characters" in errors

    def test_missing_last_name(self):
        data = UserCreate(first_name="John", last_name="", email="john@example.com")
        errors = validate_user_create(data)
        assert "last_name is required" in errors

    def test_invalid_email(self):
        data = UserCreate(first_name="John", last_name="Doe", email="invalid")
        errors = validate_user_create(data)
        assert "email must be a valid email address" in errors

    def test_valid_emails(self):
        valid_emails = ["john@example.com", "john.doe@test.org", "john+tag@example.co.uk"]
        for email in valid_emails:
            data = UserCreate(first_name="John", last_name="Doe", email=email)
            errors = validate_user_create(data)
            assert errors == [], f"Failed for {email}"

    def test_company_too_long(self):
        data = UserCreate(first_name="John", last_name="Doe", email="john@example.com", company="x" * 101)
        errors = validate_user_create(data)
        assert "company must be at most 100 characters" in errors

    def test_invalid_role(self):
        data = UserCreate(first_name="John", last_name="Doe", email="john@example.com", role="invalid")
        errors = validate_user_create(data)
        assert any("role must be one of" in e for e in errors)

    def test_valid_roles(self):
        for role in ["attendee", "speaker", "organizer"]:
            data = UserCreate(first_name="John", last_name="Doe", email="john@example.com", role=role)
            errors = validate_user_create(data)
            assert errors == [], f"Failed for role {role}"

    def test_normalize_email(self):
        assert normalize_email("JOHN@EXAMPLE.COM") == "john@example.com"
        assert normalize_email("  John@Example.Com  ") == "john@example.com"

    def test_validate_user_update(self):
        data = UserUpdate(first_name="Jane", email="jane@example.com")
        errors = validate_user_update(data)
        assert errors == []

    def test_update_empty_first_name(self):
        data = UserUpdate(first_name="")
        errors = validate_user_update(data)
        assert "first_name cannot be empty" in errors

    def test_update_invalid_email(self):
        data = UserUpdate(email="invalid")
        errors = validate_user_update(data)
        assert "email must be a valid email address" in errors


class TestMemoryRepository:
    """Test in-memory repository."""

    @pytest.fixture
    def repo(self):
        return MemoryUserRepository()

    def test_create_and_get(self, repo):
        user = User(
            id="test-id",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            role="attendee",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        created = repo.create(user)
        assert created.id == "test-id"
        assert created.email == "john@example.com"

        retrieved = repo.get_by_id("test-id")
        assert retrieved is not None
        assert retrieved.email == "john@example.com"

    def test_duplicate_email_raises(self, repo):
        user1 = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        user2 = User(id="2", first_name="Jane", last_name="Doe", email="JOHN@EXAMPLE.COM", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user1)
        with pytest.raises(ValueError, match="EMAIL_ALREADY_EXISTS"):
            repo.create(user2)

    def test_get_by_email_case_insensitive(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)
        assert repo.get_by_email("JOHN@EXAMPLE.COM") is not None
        assert repo.get_by_email("john@example.com") is not None

    def test_list_users_pagination(self, repo):
        for i in range(5):
            user = User(id=str(i), first_name=f"User{i}", last_name="Test", email=f"user{i}@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
            repo.create(user)

        result = repo.list_users(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 2

    def test_list_users_role_filter(self, repo):
        user1 = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        user2 = User(id="2", first_name="Jane", last_name="Doe", email="jane@example.com", role="organizer", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user1)
        repo.create(user2)

        result = repo.list_users(page=1, page_size=10, role="organizer")
        assert result["total"] == 1
        item = result["items"][0]
        role = item.role if hasattr(item, "role") else item["role"]
        assert role == "organizer"

    def test_list_users_email_filter(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)

        result = repo.list_users(page=1, page_size=10, email="JOHN@EXAMPLE.COM")
        assert result["total"] == 1
        item = result["items"][0]
        email = item.email if hasattr(item, "email") else item["email"]
        assert email == "john@example.com"

    def test_update_user(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)

        updated = repo.update("1", UserUpdate(first_name="Jane", role="organizer"))
        assert updated is not None
        assert updated.first_name == "Jane"
        assert updated.role == "organizer"
        assert updated.updated_at > "2026-01-01T00:00:00Z"

    def test_update_nonexistent(self, repo):
        updated = repo.update("nonexistent", UserUpdate(first_name="Jane"))
        assert updated is None

    def test_update_email_uniqueness(self, repo):
        user1 = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        user2 = User(id="2", first_name="Jane", last_name="Doe", email="jane@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user1)
        repo.create(user2)

        with pytest.raises(ValueError, match="EMAIL_ALREADY_EXISTS"):
            repo.update("1", UserUpdate(email="jane@example.com"))

    def test_delete_user(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False


class TestJsonRepository:
    """Test JSON file repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return JsonUserRepository(tmp_path)

    def test_create_and_get(self, repo):
        user = User(
            id="test-id",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            role="attendee",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        created = repo.create(user)
        assert created.id == "test-id"

        retrieved = repo.get_by_id("test-id")
        assert retrieved is not None
        assert retrieved.email == "john@example.com"

    def test_persistence_across_instances(self, tmp_path):
        repo1 = JsonUserRepository(tmp_path)
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo1.create(user)

        repo2 = JsonUserRepository(tmp_path)
        retrieved = repo2.get_by_id("1")
        assert retrieved is not None
        assert retrieved.email == "john@example.com"


class TestSqliteRepository:
    """Test SQLite repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return SqliteUserRepository(tmp_path)

    def test_create_and_get(self, repo):
        user = User(
            id="test-id",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            role="attendee",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        created = repo.create(user)
        assert created.id == "test-id"

        retrieved = repo.get_by_id("test-id")
        assert retrieved is not None
        assert retrieved.email == "john@example.com"

    def test_persistence_across_instances(self, tmp_path):
        repo1 = SqliteUserRepository(tmp_path)
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com", role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo1.create(user)

        repo2 = SqliteUserRepository(tmp_path)
        retrieved = repo2.get_by_id("1")
        assert retrieved is not None
        assert retrieved.email == "john@example.com"


class TestBusinessLogic:
    """Test business logic functions."""

    @pytest.fixture
    def repo(self):
        return MemoryUserRepository()

    def test_create_user_success(self, repo):
        data = UserCreate(first_name="John", last_name="Doe", email="john@example.com")
        user = create_user(data, repo)
        assert user.id is not None
        assert user.email == "john@example.com"
        assert user.first_name == "John"
        assert user.role == "attendee"

    def test_create_user_normalizes_email(self, repo):
        data = UserCreate(first_name="John", last_name="Doe", email="JOHN@EXAMPLE.COM")
        user = create_user(data, repo)
        assert user.email == "john@example.com"

    def test_create_user_duplicate_email(self, repo):
        data = UserCreate(first_name="John", last_name="Doe", email="john@example.com")
        create_user(data, repo)
        with pytest.raises(ValueError, match="EMAIL_ALREADY_EXISTS"):
            create_user(data, repo)

    def test_update_user(self, repo):
        data = UserCreate(first_name="John", last_name="Doe", email="john@example.com")
        user = create_user(data, repo)

        updated = update_user(user.id, UserUpdate(first_name="Jane", role="organizer"), repo)
        assert updated is not None
        assert updated.first_name == "Jane"
        assert updated.role == "organizer"

    def test_update_user_not_found(self, repo):
        updated = update_user("nonexistent", UserUpdate(first_name="Jane"), repo)
        assert updated is None

    def test_list_users(self, repo):
        for i in range(3):
            create_user(UserCreate(first_name=f"User{i}", last_name="Test", email=f"user{i}@example.com"), repo)

        result = list_users(1, 2, None, None, repo)
        assert len(result["items"]) == 2
        assert result["total"] == 3


class TestConfig:
    """Test configuration."""

    def test_default_config(self):
        with patch.dict(os.environ, {"PORT": "5001"}, clear=True):
            cfg = Config()
            assert cfg.port == 5001
            assert cfg.storage_backend == "memory"

    def test_custom_config(self):
        with patch.dict(os.environ, {"PORT": "8080", "STORAGE_BACKEND": "json", "DATA_DIR": "/tmp/data"}, clear=True):
            cfg = Config()
            assert cfg.port == 8080
            assert cfg.storage_backend == "json"
            # On macOS, /tmp is a symlink to /private/tmp
            assert str(cfg.data_dir).endswith("/tmp/data") or str(cfg.data_dir).endswith("/private/tmp/data")

    def test_invalid_storage_backend(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "invalid"}, clear=True):
            with pytest.raises(ValueError, match="Invalid STORAGE_BACKEND"):
                Config()

    def test_create_repository_factory(self):
        with patch.dict(os.environ, {"STORAGE_BACKEND": "memory"}, clear=True):
            cfg = Config()
            repo = create_user_repository(cfg)
            assert isinstance(repo, MemoryUserRepository)

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"STORAGE_BACKEND": "json", "DATA_DIR": tmpdir}, clear=True):
                cfg = Config()
                repo = create_user_repository(cfg)
                assert isinstance(repo, JsonUserRepository)

            with patch.dict(os.environ, {"STORAGE_BACKEND": "sqlite", "DATA_DIR": tmpdir}, clear=True):
                cfg = Config()
                repo = create_user_repository(cfg)
                assert isinstance(repo, SqliteUserRepository)


class TestContractValidation:
    """Test contract validation for each endpoint."""

    def test_user_schema(self):
        """Test that User model matches contract schema."""
        user = User(
            id="123e4567-e89b-12d3-a456-426614174000",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            role="attendee",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        data = user.to_dict()
        assert "id" in data
        assert "first_name" in data
        assert "last_name" in data
        assert "email" in data
        assert "role" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["role"] in ["attendee", "speaker", "organizer"]

    def test_user_page_schema(self):
        """Test that pagination response matches contract."""
        from user_service.repository import MemoryUserRepository
        repo = MemoryUserRepository()
        result = repo.list_users(1, 20, None, None)
        assert "items" in result
        assert "page" in result
        assert "page_size" in result
        assert "total" in result


# ---------------------------------------------------------------------------
# Additional tests for JSON and SQLite repositories (coverage ≥ 80%)
# ---------------------------------------------------------------------------

class TestJsonRepositoryExtended:
    """Extended tests for JSON file repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return JsonUserRepository(tmp_path)

    def test_list_users_pagination(self, repo):
        for i in range(5):
            user = User(id=str(i), first_name=f"User{i}", last_name="Test",
                        email=f"user{i}@example.com", role="attendee",
                        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
            repo.create(user)

        result = repo.list_users(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 2

    def test_list_users_role_filter(self, repo):
        user1 = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                     role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        user2 = User(id="2", first_name="Jane", last_name="Doe", email="jane@example.com",
                     role="organizer", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user1)
        repo.create(user2)

        result = repo.list_users(page=1, page_size=10, role="organizer")
        assert result["total"] == 1
        item = result["items"][0]
        role = item.role if hasattr(item, "role") else item["role"]
        assert role == "organizer"

    def test_list_users_email_filter(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)

        result = repo.list_users(page=1, page_size=10, email="JOHN@EXAMPLE.COM")
        assert result["total"] == 1

    def test_update_user(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)

        updated = repo.update("1", UserUpdate(first_name="Jane", role="organizer"))
        assert updated is not None
        assert updated.first_name == "Jane"
        assert updated.role == "organizer"
        assert updated.updated_at > "2026-01-01T00:00:00Z"

    def test_update_nonexistent(self, repo):
        updated = repo.update("nonexistent", UserUpdate(first_name="Jane"))
        assert updated is None

    def test_update_email_uniqueness(self, repo):
        user1 = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                     role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        user2 = User(id="2", first_name="Jane", last_name="Doe", email="jane@example.com",
                     role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user1)
        repo.create(user2)

        with pytest.raises(ValueError, match="EMAIL_ALREADY_EXISTS"):
            repo.update("1", UserUpdate(email="jane@example.com"))

    def test_delete_user(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False

    def test_get_by_email(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)
        found = repo.get_by_email("JOHN@EXAMPLE.COM")
        assert found is not None
        assert found.id == "1"

    def test_get_by_email_not_found(self, repo):
        found = repo.get_by_email("notexistent@example.com")
        assert found is None

    def test_email_uniqueness_on_create(self, repo):
        user1 = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                     role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        user2 = User(id="2", first_name="Jane", last_name="Doe", email="JOHN@EXAMPLE.COM",
                     role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user1)
        with pytest.raises(ValueError, match="EMAIL_ALREADY_EXISTS"):
            repo.create(user2)


class TestSqliteRepositoryExtended:
    """Extended tests for SQLite repository."""

    @pytest.fixture
    def repo(self, tmp_path):
        return SqliteUserRepository(tmp_path)

    def test_list_users_pagination(self, repo):
        for i in range(5):
            user = User(id=str(i), first_name=f"User{i}", last_name="Test",
                        email=f"user{i}@example.com", role="attendee",
                        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
            repo.create(user)

        result = repo.list_users(page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_list_users_role_filter(self, repo):
        user1 = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                     role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        user2 = User(id="2", first_name="Jane", last_name="Doe", email="jane@example.com",
                     role="organizer", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user1)
        repo.create(user2)

        result = repo.list_users(page=1, page_size=10, role="organizer")
        assert result["total"] == 1

    def test_list_users_email_filter(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)

        result = repo.list_users(page=1, page_size=10, email="john@example.com")
        assert result["total"] == 1

    def test_update_user(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)

        updated = repo.update("1", UserUpdate(first_name="Jane", role="organizer"))
        assert updated is not None
        assert updated.first_name == "Jane"
        assert updated.role == "organizer"

    def test_update_nonexistent(self, repo):
        updated = repo.update("nonexistent", UserUpdate(first_name="Jane"))
        assert updated is None

    def test_update_email_uniqueness(self, repo):
        user1 = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                     role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        user2 = User(id="2", first_name="Jane", last_name="Doe", email="jane@example.com",
                     role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user1)
        repo.create(user2)

        with pytest.raises(ValueError, match="EMAIL_ALREADY_EXISTS"):
            repo.update("1", UserUpdate(email="jane@example.com"))

    def test_delete_user(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)
        assert repo.delete("1") is True
        assert repo.get_by_id("1") is None
        assert repo.delete("1") is False

    def test_get_by_email(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)
        found = repo.get_by_email("JOHN@EXAMPLE.COM")
        assert found is not None
        assert found.id == "1"

    def test_get_by_email_not_found(self, repo):
        found = repo.get_by_email("notexistent@example.com")
        assert found is None

    def test_list_users_no_filter(self, repo):
        """Verifica che list_users senza filtri restituisca tutti gli utenti."""
        for i in range(3):
            user = User(id=str(i), first_name=f"User{i}", last_name="Test",
                        email=f"user{i}@example.com", role="attendee",
                        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
            repo.create(user)
        result = repo.list_users(page=1, page_size=10)
        assert result["total"] == 3

    def test_update_all_fields(self, repo):
        user = User(id="1", first_name="John", last_name="Doe", email="john@example.com",
                    role="attendee", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        repo.create(user)

        updated = repo.update("1", UserUpdate(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            company="TechCorp",
            role="speaker",
        ))
        assert updated is not None
        assert updated.first_name == "Jane"
        assert updated.last_name == "Smith"
        assert updated.email == "jane@example.com"
        assert updated.company == "TechCorp"
        assert updated.role == "speaker"
