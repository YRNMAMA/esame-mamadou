"""Registration repository implementations for memory, JSON, and SQLite backends."""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from techconf_common import VALIDATION_ERROR, NOT_FOUND, CONFLICT, error_response

from .models import Registration, RegistrationCreate, RegistrationPatch, RegistrationStats


class RegistrationRepository(ABC):
    """Abstract base class for registration persistence."""

    @abstractmethod
    def create(self, registration: Registration) -> Registration:
        pass

    @abstractmethod
    def get_by_id(self, reg_id: str) -> Optional[Registration]:
        pass

    @abstractmethod
    def get_by_user_and_event(self, user_id: str, event_id: str) -> Optional[Registration]:
        pass

    @abstractmethod
    def list_registrations(self, page: int, page_size: int, user_id: Optional[str] = None, event_id: Optional[str] = None, status: Optional[str] = None) -> dict:
        pass

    @abstractmethod
    def update_status(self, reg_id: str, status: str) -> Optional[Registration]:
        pass

    @abstractmethod
    def delete(self, reg_id: str) -> bool:
        pass

    @abstractmethod
    def count_confirmed_for_event(self, event_id: str) -> int:
        pass

    @abstractmethod
    def close(self):
        pass


class MemoryRegistrationRepository(RegistrationRepository):
    """In-memory registration repository."""

    def __init__(self):
        self._registrations: dict[str, Registration] = {}
        self._lock = threading.RLock()

    def create(self, registration: Registration) -> Registration:
        with self._lock:
            self._registrations[registration.id] = registration
            return registration

    def get_by_id(self, reg_id: str) -> Optional[Registration]:
        with self._lock:
            return self._registrations.get(reg_id)

    def get_by_user_and_event(self, user_id: str, event_id: str) -> Optional[Registration]:
        with self._lock:
            for reg in self._registrations.values():
                if reg.user_id == user_id and reg.event_id == event_id:
                    return reg
            return None

    def list_registrations(self, page: int, page_size: int, user_id: Optional[str] = None, event_id: Optional[str] = None, status: Optional[str] = None) -> dict:
        with self._lock:
            registrations = list(self._registrations.values())

            if user_id:
                registrations = [r for r in registrations if r.user_id == user_id]
            if event_id:
                registrations = [r for r in registrations if r.event_id == event_id]
            if status:
                registrations = [r for r in registrations if r.status == status]

            total = len(registrations)
            start = (page - 1) * page_size
            end = start + page_size
            items = registrations[start:end]

            return {
                "items": [asdict(r) for r in items],
                "page": page,
                "page_size": page_size,
                "total": total,
            }

    def update_status(self, reg_id: str, status: str) -> Optional[Registration]:
        with self._lock:
            reg = self._registrations.get(reg_id)
            if not reg:
                return None

            reg.status = status
            from datetime import datetime, timezone
            reg.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            return reg

    def delete(self, reg_id: str) -> bool:
        with self._lock:
            if reg_id in self._registrations:
                del self._registrations[reg_id]
                return True
            return False

    def count_confirmed_for_event(self, event_id: str) -> int:
        with self._lock:
            return sum(1 for r in self._registrations.values() if r.event_id == event_id and r.status == "confirmed")

    def close(self):
        pass


class JsonRegistrationRepository(RegistrationRepository):
    """JSON file-based registration repository."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.file_path = data_dir / "registrations.json"
        self._lock = threading.RLock()
        self._ensure_file()

    def _ensure_file(self):
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        with self._lock:
            content = self.file_path.read_text(encoding="utf-8")
            return json.loads(content) if content.strip() else []

    def _save(self, registrations: list[dict]):
        with self._lock:
            self.file_path.write_text(json.dumps(registrations, indent=2), encoding="utf-8")

    def create(self, registration: Registration) -> Registration:
        registrations = self._load()
        registrations.append(asdict(registration))
        self._save(registrations)
        return registration

    def get_by_id(self, reg_id: str) -> Optional[Registration]:
        registrations = self._load()
        for r in registrations:
            if r["id"] == reg_id:
                return Registration(**r)
        return None

    def get_by_user_and_event(self, user_id: str, event_id: str) -> Optional[Registration]:
        registrations = self._load()
        for r in registrations:
            if r["user_id"] == user_id and r["event_id"] == event_id:
                return Registration(**r)
        return None

    def list_registrations(self, page: int, page_size: int, user_id: Optional[str] = None, event_id: Optional[str] = None, status: Optional[str] = None) -> dict:
        registrations = self._load()

        if user_id:
            registrations = [r for r in registrations if r["user_id"] == user_id]
        if event_id:
            registrations = [r for r in registrations if r["event_id"] == event_id]
        if status:
            registrations = [r for r in registrations if r["status"] == status]

        total = len(registrations)
        start = (page - 1) * page_size
        end = start + page_size
        items = registrations[start:end]

        return {
            "items": [Registration(**r) for r in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def update_status(self, reg_id: str, status: str) -> Optional[Registration]:
        registrations = self._load()
        for i, r in enumerate(registrations):
            if r["id"] == reg_id:
                r["status"] = status
                from datetime import datetime, timezone
                r["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                self._save(registrations)
                return Registration(**r)
        return None

    def delete(self, reg_id: str) -> bool:
        registrations = self._load()
        for i, r in enumerate(registrations):
            if r["id"] == reg_id:
                registrations.pop(i)
                self._save(registrations)
                return True
        return False

    def count_confirmed_for_event(self, event_id: str) -> int:
        registrations = self._load()
        return sum(1 for r in registrations if r["event_id"] == event_id and r["status"] == "confirmed")

    def close(self):
        pass


class SqliteRegistrationRepository(RegistrationRepository):
    """SQLite-based registration repository."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.db_path = data_dir / "registrations.db"
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_user ON registrations(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_event ON registrations(event_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_status ON registrations(status)")
            conn.commit()
            conn.close()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, registration: Registration) -> Registration:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO registrations (id, user_id, event_id, amount, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (registration.id, registration.user_id, registration.event_id,
                     registration.amount, registration.status, registration.created_at, registration.updated_at)
                )
                conn.commit()
            finally:
                conn.close()
        return registration

    def get_by_id(self, reg_id: str) -> Optional[Registration]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
            conn.close()
            if row:
                return Registration(**dict(row))
            return None

    def get_by_user_and_event(self, user_id: str, event_id: str) -> Optional[Registration]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM registrations WHERE user_id = ? AND event_id = ?", (user_id, event_id)).fetchone()
            conn.close()
            if row:
                return Registration(**dict(row))
            return None

    def list_registrations(self, page: int, page_size: int, user_id: Optional[str] = None, event_id: Optional[str] = None, status: Optional[str] = None) -> dict:
        with self._lock:
            conn = self._get_conn()
            query = "SELECT * FROM registrations WHERE 1=1"
            params = []

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if event_id:
                query += " AND event_id = ?"
                params.append(event_id)
            if status:
                query += " AND status = ?"
                params.append(status)

            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            total = conn.execute(count_query, params).fetchone()[0]

            query += " ORDER BY created_at LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            rows = conn.execute(query, params).fetchall()
            conn.close()

            items = [Registration(**dict(row)) for row in rows]
            return {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
            }

    def update_status(self, reg_id: str, status: str) -> Optional[Registration]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
                if not row:
                    return None

                from datetime import datetime, timezone
                updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

                conn.execute("UPDATE registrations SET status = ?, updated_at = ? WHERE id = ?", (status, updated_at, reg_id))
                conn.commit()

                row = conn.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
                if row:
                    return Registration(**dict(row))
                return None
            finally:
                conn.close()

    def delete(self, reg_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            return deleted

    def count_confirmed_for_event(self, event_id: str) -> int:
        with self._lock:
            conn = self._get_conn()
            count = conn.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'", (event_id,)).fetchone()[0]
            conn.close()
            return count

    def close(self):
        pass


def create_registration_repository(config) -> RegistrationRepository:
    """Factory function to create the appropriate repository based on config."""
    if config.storage_backend == "memory":
        return MemoryRegistrationRepository()
    elif config.storage_backend == "json":
        return JsonRegistrationRepository(config.data_dir)
    elif config.storage_backend == "sqlite":
        return SqliteRegistrationRepository(config.data_dir)
    else:
        raise ValueError(f"Unknown storage backend: {config.storage_backend}")