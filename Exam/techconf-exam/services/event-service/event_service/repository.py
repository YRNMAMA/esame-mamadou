"""Event repository implementations for memory, JSON, and SQLite backends."""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from techconf_common import VALIDATION_ERROR, NOT_FOUND, CONFLICT, error_response

from .models import Event, EventCreate, EventUpdate


class EventRepository(ABC):
    """Abstract base class for event persistence."""

    @abstractmethod
    def create(self, event: Event) -> Event:
        pass

    @abstractmethod
    def get_by_id(self, event_id: str) -> Optional[Event]:
        pass

    @abstractmethod
    def list_users(self, page: int, page_size: int, status: Optional[str] = None, city: Optional[str] = None) -> dict:
        pass

    @abstractmethod
    def update(self, event_id: str, data: EventUpdate) -> Optional[Event]:
        pass

    @abstractmethod
    def delete(self, event_id: str) -> bool:
        pass

    @abstractmethod
    def close(self):
        pass


class MemoryEventRepository(EventRepository):
    """In-memory event repository."""

    def __init__(self):
        self._events: dict[str, Event] = {}
        self._lock = threading.RLock()

    def create(self, event: Event) -> Event:
        with self._lock:
            self._events[event.id] = event
            return event

    def get_by_id(self, event_id: str) -> Optional[Event]:
        with self._lock:
            return self._events.get(event_id)

    def list_users(self, page: int, page_size: int, status: Optional[str] = None, city: Optional[str] = None) -> dict:
        with self._lock:
            events = list(self._events.values())

            if status:
                events = [e for e in events if e.status == status]
            if city:
                city_lower = city.lower()
                events = [e for e in events if e.city.lower() == city_lower]

            total = len(events)
            start = (page - 1) * page_size
            end = start + page_size
            items = events[start:end]

            return {
                "items": [asdict(e) for e in items],
                "page": page,
                "page_size": page_size,
                "total": total,
            }

    def update(self, event_id: str, data: EventUpdate) -> Optional[Event]:
        with self._lock:
            event = self._events.get(event_id)
            if not event:
                return None

            if data.title is not None:
                event.title = data.title
            if data.description is not None:
                event.description = data.description
            if data.organizer_id is not None:
                event.organizer_id = data.organizer_id
            if data.venue is not None:
                event.venue = data.venue
            if data.city is not None:
                event.city = data.city
            if data.start_date is not None:
                event.start_date = data.start_date
            if data.end_date is not None:
                event.end_date = data.end_date
            if data.capacity is not None:
                event.capacity = data.capacity
            if data.price is not None:
                event.price = data.price
            if data.status is not None:
                event.status = data.status

            from datetime import datetime, timezone
            event.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            return event

    def delete(self, event_id: str) -> bool:
        with self._lock:
            if event_id in self._events:
                del self._events[event_id]
                return True
            return False

    def close(self):
        pass


class JsonEventRepository(EventRepository):
    """JSON file-based event repository."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.file_path = data_dir / "events.json"
        self._lock = threading.RLock()
        self._ensure_file()

    def _ensure_file(self):
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        with self._lock:
            content = self.file_path.read_text(encoding="utf-8")
            return json.loads(content) if content.strip() else []

    def _save(self, events: list[dict]):
        with self._lock:
            self.file_path.write_text(json.dumps(events, indent=2), encoding="utf-8")

    def create(self, event: Event) -> Event:
        events = self._load()
        events.append(asdict(event))
        self._save(events)
        return event

    def get_by_id(self, event_id: str) -> Optional[Event]:
        events = self._load()
        for e in events:
            if e["id"] == event_id:
                return Event(**e)
        return None

    def list_users(self, page: int, page_size: int, status: Optional[str] = None, city: Optional[str] = None) -> dict:
        events = self._load()

        if status:
            events = [e for e in events if e["status"] == status]
        if city:
            city_lower = city.lower()
            events = [e for e in events if e["city"].lower() == city_lower]

        total = len(events)
        start = (page - 1) * page_size
        end = start + page_size
        items = events[start:end]

        return {
            "items": [Event(**e) for e in items],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def update(self, event_id: str, data: EventUpdate) -> Optional[Event]:
        events = self._load()
        for i, e in enumerate(events):
            if e["id"] == event_id:
                if data.title is not None:
                    e["title"] = data.title
                if data.description is not None:
                    e["description"] = data.description
                if data.organizer_id is not None:
                    e["organizer_id"] = data.organizer_id
                if data.venue is not None:
                    e["venue"] = data.venue
                if data.city is not None:
                    e["city"] = data.city
                if data.start_date is not None:
                    e["start_date"] = data.start_date
                if data.end_date is not None:
                    e["end_date"] = data.end_date
                if data.capacity is not None:
                    e["capacity"] = data.capacity
                if data.price is not None:
                    e["price"] = data.price
                if data.status is not None:
                    e["status"] = data.status

                from datetime import datetime, timezone
                e["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

                self._save(events)
                return Event(**e)
        return None

    def delete(self, event_id: str) -> bool:
        events = self._load()
        for i, e in enumerate(events):
            if e["id"] == event_id:
                events.pop(i)
                self._save(events)
                return True
        return False

    def close(self):
        pass


class SqliteEventRepository(EventRepository):
    """SQLite-based event repository."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.db_path = data_dir / "events.db"
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    organizer_id TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    city TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    capacity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_organizer ON events(organizer_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_city ON events(city)")
            conn.commit()
            conn.close()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, event: Event) -> Event:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT INTO events (id, title, description, organizer_id, venue, city, start_date, end_date, capacity, price, status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event.id, event.title, event.description, event.organizer_id, event.venue, event.city,
                     event.start_date, event.end_date, event.capacity, event.price, event.status,
                     event.created_at, event.updated_at)
                )
                conn.commit()
            finally:
                conn.close()
        return event

    def get_by_id(self, event_id: str) -> Optional[Event]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            conn.close()
            if row:
                return Event(**dict(row))
            return None

    def list_users(self, page: int, page_size: int, status: Optional[str] = None, city: Optional[str] = None) -> dict:
        with self._lock:
            conn = self._get_conn()
            query = "SELECT * FROM events WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)
            if city:
                query += " AND LOWER(city) = LOWER(?)"
                params.append(city)

            count_query = query.replace("SELECT *", "SELECT COUNT(*)")
            total = conn.execute(count_query, params).fetchone()[0]

            query += " ORDER BY created_at LIMIT ? OFFSET ?"
            params.extend([page_size, (page - 1) * page_size])
            rows = conn.execute(query, params).fetchall()
            conn.close()

            items = [Event(**dict(row)) for row in rows]
            return {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
            }

    def update(self, event_id: str, data: EventUpdate) -> Optional[Event]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
                if not row:
                    return None

                updates = []
                params = []
                if data.title is not None:
                    updates.append("title = ?")
                    params.append(data.title)
                if data.description is not None:
                    updates.append("description = ?")
                    params.append(data.description)
                if data.organizer_id is not None:
                    updates.append("organizer_id = ?")
                    params.append(data.organizer_id)
                if data.venue is not None:
                    updates.append("venue = ?")
                    params.append(data.venue)
                if data.city is not None:
                    updates.append("city = ?")
                    params.append(data.city)
                if data.start_date is not None:
                    updates.append("start_date = ?")
                    params.append(data.start_date)
                if data.end_date is not None:
                    updates.append("end_date = ?")
                    params.append(data.end_date)
                if data.capacity is not None:
                    updates.append("capacity = ?")
                    params.append(data.capacity)
                if data.price is not None:
                    updates.append("price = ?")
                    params.append(data.price)
                if data.status is not None:
                    updates.append("status = ?")
                    params.append(data.status)

                if updates:
                    from datetime import datetime, timezone
                    updates.append("updated_at = ?")
                    params.append(datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

                    params.append(event_id)
                    conn.execute(f"UPDATE events SET {', '.join(updates)} WHERE id = ?", params)
                    conn.commit()

                row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
                if row:
                    return Event(**dict(row))
                return None
            finally:
                conn.close()

    def delete(self, event_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            return deleted

    def close(self):
        pass


def create_event_repository(config) -> EventRepository:
    """Factory function to create the appropriate repository based on config."""
    if config.storage_backend == "memory":
        return MemoryEventRepository()
    elif config.storage_backend == "json":
        return JsonEventRepository(config.data_dir)
    elif config.storage_backend == "sqlite":
        return SqliteEventRepository(config.data_dir)
    else:
        raise ValueError(f"Unknown storage backend: {config.storage_backend}")