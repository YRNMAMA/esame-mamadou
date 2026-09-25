# User Service — Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Flask App                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  routes.py  │──▶│  models.py  │──▶│  repository.py      │  │
│  │  (HTTP)     │   │ (Business)  │   │ (Persistence)       │  │
│  └─────────────┘   └─────────────┘   └─────────────────────┘  │
│                                                ▲               │
│                                                │               │
│                           ┌────────────────────┘               │
│                           ▼                                    │
│              ┌─────────────────────────┐                       │
│              │  Storage Backend        │                       │
│              │  (memory | json | sqlite)                       │
│              └─────────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### routes.py (HTTP Layer)
- Request parsing & validation
- Response formatting (success + error)
- Status codes, headers (Location)
- Delegates to models for business logic

### models.py (Business Logic Layer)
- Domain model: `User` dataclass
- Validation functions (email format, lengths, role enum)
- Business rules: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03
- No HTTP, no persistence concerns

### repository.py (Persistence Abstraction)
- Interface: `UserRepository` (abstract base class)
- Implementations:
  - `MemoryUserRepository` — in-memory dict
  - `JsonUserRepository` — JSON file in `DATA_DIR/users.json`
  - `SqliteUserRepository` — SQLite table in `DATA_DIR/users.db`
- Factory: `create_user_repository()` reads `STORAGE_BACKEND`

### config.py
- Reads all env vars at startup
- Provides defaults
- Single source of truth for configuration

## Data Flow

**Create User (POST)**:
1. `routes.py` parses JSON, validates required fields
2. `models.py` validates email format, lengths, role enum
3. `models.py` normalizes email to lowercase
4. `repository.py` checks uniqueness (case-insensitive)
5. `repository.py` generates UUID, timestamps, saves
6. `routes.py` returns 201 + Location + User

**List Users (GET)**:
1. `routes.py` parses query params (page, page_size, role, email)
2. `repository.py` filters, paginates
3. `routes.py` returns paginated response

## Error Handling

- Validation errors → 422 `VALIDATION_ERROR` with details
- Duplicate email → 409 `EMAIL_ALREADY_EXISTS`
- Not found → 404 `NOT_FOUND`
- Malformed JSON → 400 `MALFORMED_JSON` (Flask handles)

## Storage Schema

### Memory
```python
{user_id: UserObject, ...}
```

### JSON (users.json)
```json
[
  {"id": "...", "first_name": "...", "last_name": "...", "email": "...", "company": "...", "role": "...", "created_at": "...", "updated_at": "..."}
]
```

### SQLite (users.db)
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    company TEXT,
    role TEXT NOT NULL DEFAULT 'attendee',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_users_email ON users(LOWER(email));
CREATE INDEX idx_users_role ON users(role);
```

## Testing Strategy

- **Unit**: Mock `UserRepository`, test models validation & business rules
- **Unit**: Test each repository implementation with `tmp_path`
- **Contract**: Use `assert_matches_contract` for each endpoint
- **Integration**: Launch real service, test via HTTP client