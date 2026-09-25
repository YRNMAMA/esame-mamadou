"""User repository implementations for memory, JSON, and SQLite backends."""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from uuid import uuid4

from techconf_common import (
    VALIDATION_ERROR,
    NOT_FOUND,
    CONFLICT,
    EMAIL_ALREADY_EXISTS,
    error_response,
)

from user_service.models import User, UserCreate, UserUpdate


class UserRepository(ABC):
    """Abstract base class for user persistence."""

    @abstractmethod
    def create(self, user: User) -> User:
        pass

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def list_users(self, page: int, page_size: int, role: Optional[str] = None, email: Optional[str] = None) -> dict:
        pass

    @abstractmethod
    def update(self, user_id: str, data: UserUpdate) -> Optional[User]:
        pass

    @abstractmethod
    def delete(self, user_id: str) -> bool:
        pass

    @abstractmethod
    def close(self):
        pass


class MemoryUserRepository(UserRepository):
    """In-memory user repository."""

    def __init__(self):
        self._users: dict[str, User] = {}
        self._lock = threading.RLock()

    def create(self, user: User) -> User:
        with self._lock:
            if any(u.email.lower() == user.email.lower() for u in self._users.values()):
                raise ValueError(EMAIL_ALREADY_EXISTS)
            self._users[user.id] = user
            return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        with self._lock:
            return self._users.get(user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        with self._lock:
            email_lower = email.lower()
            for user in self._users.values():
                if user.email.lower() == email_lower:
                    return user
            return None

    def list_users(self, page: int, page_size: int, role: Optional[str] = None, email: Optional[str] = None) -> dict:
        with self._lock:
            users = list(self._users.values())

            if role:
                users = [u for u in users if u.role == role]
            if email:
                email_lower = email.lower()
                users = [u for u in users if u.email.lower() == email_lower]

            total = len(users)
            start = (page - 1) * page_size
            end = start + page_size
            items = users[start:end]

            return {
                "items": [asdict(u) for u in items],
                "page": page,
                "page_size": page_size,
                "total": total,
            }

    def update(self, user_id: str, data: UserUpdate) -> Optional[User]:
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return None

            if data.email is not None:
                if any(u.email.lower() == data.email.lower() for u in self._users.values() if u.id != user_id):
                    raise ValueError(EMAIL_ALREADY_EXISTS)
                user.email = data.email.lower()

            if data.first_name is not None:
                user.first_name = data.first_name
            if data.last_name is not None:
                user.last_name = data.last_name
            if data.company is not None:
                user.company = data.company
            if data.role is not None:
                user.role = data.role

            from datetime import datetime, timezone
            user.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            return user

    def delete(self, user_id: str) -> bool:
        with self._lock:
            if user_id in self._users:
                del self._users[user_id]
                return True
            return False

    def close(self):
        pass


class JsonUserRepository(UserRepository):
    """JSON file-based user repository."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.file_path = data_dir / "users.json"
        self._lock = threading.RLock()
        self._ensure_file()

    def _ensure_file(self):
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        with self._lock:
            content = self.file_path.read_text(encoding="utf-8")
            return json.loads(content) if content.strip() else []

    def _save(self, users: list[dict]):
        with self._lock:
            self.file_path.write_text(json.dumps(users, indent=2), encoding="utf-8")

    def create(self, user: User) -> User:
        users = self._load()
        if any(u["email"].lower() == user.email.lower() for u in users):
            raise ValueError(EMAIL_ALREADY_EXISTS)
        users.append(asdict(user))
        self._save(users)
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        users = self._load()
        for u in users:
            if u["id"] == user_id:
                return User(**u)
        return None

    def get_by_email(self, email: str) -> Optional[User]:
        users = self._load()
        email_lower = email.lower()
        for u in users:
            if u["email"].lower() == email_lower:
                return User(**u)
        return None

    def list_users(self, page: int, page_size: int, role: Optional[str] = None, email: Optional[str] = None) -> dict:
        users = self._load()

        if role:
            users = [u for u in users if u["role"] == role]
        if email:
            email_lower = email.lower()
            users = [u for u in users if u["email"].lower() == email_lower]

        total = len(users)
        start = (page - 1) * page_size
        end = start + page_size
        items = users[start:end]

        return {
            "items": [User(**u) for u in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def update(self, user_id: str, data: UserUpdate) -> Optional[User]:
        users = self._load()
        for i, u in enumerate(users):
            if u["id"] == user_id:
                if data.email is not None:
                    if any(other["email"].lower() == data.email.lower() for other in users if other["id"] != user_id):
                        raise ValueError(EMAIL_ALREADY_EXISTS)
                    u["email"] = data.email.lower()

                if data.first_name is not None:
                    u["first_name"] = data.first_name
                if data.last_name is not None:
                    u["last_name"] = data.last_name
                if data.company is not None:
                    u["company"] = data.company
                if data.role is not None:
                    u["role"] = data.role

                from datetime import datetime, timezone
                u["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

                self._save(users)
                return User(**u)
        return None

    def delete(self, user_id: str) -> bool:
        users = self._load()
        for i, u in enumerate(users):
            if u["id"] == user_id:
                users.pop(i)
                self._save(users)
                return True
        return False

    def close(self):
        pass


class SqliteUserRepository(UserRepository):
    """SQLite-based user repository."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.db_path = data_dir / "users.db"
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    company TEXT,
                    role TEXT NOT NULL DEFAULT 'attendee',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(LOWER(email))")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
            conn.commit()
            conn.close()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, user: User) -> User:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO users (id, first_name, last_name, email, company, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user.id, user.first_name, user.last_name, user.email.lower(), user.company, user.role, user.created_at, user.updated_at)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                raise ValueError(EMAIL_ALREADY_EXISTS)
            finally:
                conn.close()
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            conn.close()
            if row:
                return User(**dict(row))
            return None

    def get_by_email(self, email: str) -> Optional[User]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
            conn.close()
            if row:
                return User(**dict(row))
            return None

    def list_users(self, page: int, page_size: int, role: Optional[str] = None, email: Optional[str] = None) -> dict:
        with self._lock:
            conn = self._get_conn()
            query = "SELECT * FROM users WHERE 1=1"
            params = []

            if role:
                query += " AND role = ?"
                params.append(role)
            if email:
                query += " AND LOWER(email) = LOWER(?)"
                params.append(email)

            # Get total count
            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            total = conn.execute(count_query, params).fetchone()[0]

            # Get paginated results
            query += " ORDER BY created_at LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            rows = conn.execute(query, params).fetchall()
            conn.close()

            items = [User(**dict(row)) for row in rows]
            return {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
            }

    def update(self, user_id: str, data: UserUpdate) -> Optional[User]:
        with self._lock:
            conn = self._get_conn()
            try:
                # Check if user exists
                row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                if not row:
                    return None

                # Build update query
                updates = []
                params = []
                if data.email is not None:
                    # Check uniqueness
                    existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?) AND id != ?", (data.email, user_id)).fetchone()
                    if existing:
                        raise ValueError(EMAIL_ALREADY_EXISTS)
                    updates.append("email = ?")
                    params.append(data.email.lower())
                if data.first_name is not None:
                    updates.append("first_name = ?")
                    params.append(data.first_name)
                if data.last_name is not None:
                    updates.append("last_name = ?")
                    params.append(data.last_name)
                if data.company is not None:
                    updates.append("company = ?")
                    params.append(data.company)
                if data.role is not None:
                    updates.append("role = ?")
                    params.append(data.role)

                if updates:
                    from datetime import datetime, timezone
                    updates.append("updated_at = ?")
                    params.append(datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

                    params.append(user_id)
                    conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
                    conn.commit()

                # Return updated user
                row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                if row:
                    return User(**dict(row))
                return None
            except sqlite3.IntegrityError:
                raise ValueError(EMAIL_ALREADY_EXISTS)
            finally:
                conn.close()

    def delete(self, user_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            return deleted

    def close(self):
        pass


def create_user_repository(config) -> UserRepository:
    """Factory function to create the appropriate repository based on config."""
    if config.storage_backend == "memory":
        return MemoryUserRepository()
    elif config.storage_backend == "json":
        return JsonUserRepository(config.data_dir)
    elif config.storage_backend == "sqlite":
        return SqliteUserRepository(config.data_dir)
    else:
        raise ValueError(f"Unknown storage backend: {config.storage_backend}")