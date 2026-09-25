# User Service — Requirements

## User Stories & Acceptance Criteria (EARS Notation)

### REQ-USR-B01 — Email Uniqueness (Case-Insensitive)
**User Story**: As a platform, I want to prevent duplicate user accounts, so that each person has exactly one identity.

**Acceptance Criteria**
1. WHEN a user is created with an email that already exists (any case) THE SYSTEM SHALL respond 409 with error code `EMAIL_ALREADY_EXISTS`
2. WHEN a user is created with a new email THE SYSTEM SHALL create the user successfully

### REQ-USR-B02 — Email Normalization
**User Story**: As a platform, I want emails stored in lowercase, so that case-insensitive uniqueness is enforced at storage level.

**Acceptance Criteria**
1. WHEN a user is created THE SYSTEM SHALL store the email in lowercase
2. WHEN a user is retrieved THE SYSTEM SHALL return the email in lowercase

### REQ-USR-B03 — List Filters
**User Story**: As an API consumer, I want to filter users by role and email, so that I can find specific users efficiently.

**Acceptance Criteria**
1. WHEN listing users with `role` query parameter THE SYSTEM SHALL return only users with that role
2. WHEN listing users with `email` query parameter THE SYSTEM SHALL return only users with that exact email (case-insensitive match)

---

## API Endpoints (from OpenAPI contract)

### POST /api/v1/users — Create User
- **Input**: `first_name` (1-50), `last_name` (1-50), `email` (valid email, unique), `company` (optional, max 100), `role` (optional, enum: attendee|speaker|organizer, default: attendee)
- **Success**: 201 + Location header + User object
- **Errors**: 400 (malformed JSON), 422 (validation), 409 (EMAIL_ALREADY_EXISTS)

### GET /api/v1/users — List Users
- **Query**: `page` (default 1), `page_size` (default 20, max 100), `role` (optional), `email` (optional)
- **Success**: 200 + UserPage object
- **Errors**: 422 (validation)

### GET /api/v1/users/{id} — Get User
- **Success**: 200 + User object
- **Errors**: 404 (NOT_FOUND)

### PUT /api/v1/users/{id} — Replace User
- **Input**: Same as create (all required)
- **Success**: 200 + User object
- **Errors**: 404, 422, 409 (EMAIL_ALREADY_EXISTS)

### PATCH /api/v1/users/{id} — Partial Update
- **Input**: All fields optional
- **Success**: 200 + User object
- **Errors**: 404, 422, 409 (EMAIL_ALREADY_EXISTS)

### DELETE /api/v1/users/{id} — Delete User
- **Success**: 204
- **Errors**: 404

### GET /health — Health Check
- **Success**: 200 + `{"status": "ok", "service": "user-service"}`

---

## Data Model

**User** (response):
- `id`: UUID v4 (server-generated)
- `first_name`: string
- `last_name`: string
- `email`: string (lowercase, unique)
- `company`: string | null
- `role`: enum (attendee | speaker | organizer)
- `created_at`: ISO 8601 UTC
- `updated_at`: ISO 8601 UTC

**UserCreate** (request):
- Required: `first_name`, `last_name`, `email`
- Optional: `company`, `role`

**UserUpdate** (request for PATCH):
- All fields optional

---

## Storage Backend Requirements

- Support `memory`, `json`, `sqlite` via `STORAGE_BACKEND` env var
- `DATA_DIR` for json/sqlite files (default `./data`)
- Switching backend requires no business logic changes