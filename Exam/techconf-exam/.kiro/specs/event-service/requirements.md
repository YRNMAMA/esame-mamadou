# Event Service — Requirements

## User Stories & Acceptance Criteria (EARS Notation)

### REQ-EVT-B01 — Organizer Must Exist
**User Story**: As an event service, I want to validate that the organizer exists in user-service, so that events are only created by valid users.

**Acceptance Criteria**
1. WHEN an event is created with an organizer_id THE SYSTEM SHALL call user-service GET /api/v1/users/{id} to verify existence
2. IF user-service returns 404 THE SYSTEM SHALL respond 422 with error code `REFERENCE_NOT_FOUND`
3. IF user-service is unreachable THE SYSTEM SHALL respond 503 with error code `DEPENDENCY_UNAVAILABLE`

### REQ-EVT-B02 — Organizer Must Have Role Organizer
**User Story**: As an event service, I want to ensure only users with role=organizer can create events, so that attendees cannot create events.

**Acceptance Criteria**
1. WHEN an event is created with an organizer_id THE SYSTEM SHALL verify the user has role=organizer
2. IF the user exists but has role != organizer THE SYSTEM SHALL respond 422 with error code `INVALID_ORGANIZER`

### REQ-EVT-B03 — End Date >= Start Date
**User Story**: As an event organizer, I want the system to reject events where end_date is before start_date, so that events have valid duration.

**Acceptance Criteria**
1. WHEN an event is created or updated with end_date < start_date THE SYSTEM SHALL respond 422 with error code `VALIDATION_ERROR`

### REQ-EVT-B04 — Valid Status Transitions
**User Story**: As an event organizer, I want only valid status transitions, so that events follow a logical lifecycle.

**Acceptance Criteria**
1. WHEN status changes from draft to published THE SYSTEM SHALL allow it
2. WHEN status changes from draft to cancelled THE SYSTEM SHALL allow it
3. WHEN status changes from published to cancelled THE SYSTEM SHALL allow it
4. WHEN status changes from published to draft THE SYSTEM SHALL respond 422 with error code `INVALID_STATUS_TRANSITION`
5. WHEN status changes from cancelled to anything THE SYSTEM SHALL respond 422 with error code `INVALID_STATUS_TRANSITION`

### REQ-EVT-B05 — User Service Unavailable
**User Story**: As a platform, I want event-service to handle user-service unavailability gracefully.

**Acceptance Criteria**
1. WHEN user-service is unreachable (timeout, connection refused, 5xx) THE SYSTEM SHALL respond 503 with error code `DEPENDENCY_UNAVAILABLE`

### REQ-EVT-B06 — List Filters
**User Story**: As an API consumer, I want to filter events by status and city.

**Acceptance Criteria**
1. WHEN listing events with status query parameter THE SYSTEM SHALL return only events with that status
2. WHEN listing events with city query parameter THE SYSTEM SHALL return only events in that city (case-insensitive)

---

## API Endpoints (from OpenAPI contract)

### POST /api/v1/events — Create Event
- **Input**: title (3-120), description (optional, max 2000), organizer_id (UUID, required), venue (max 100), city (max 60), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), capacity (1-10000), price (>=0), status (optional, enum: draft|published|cancelled, default: draft)
- **Success**: 201 + Location header + Event object
- **Errors**: 400, 422, 503

### GET /api/v1/events — List Events
- **Query**: page, page_size, status, city
- **Success**: 200 + EventPage object
- **Errors**: 422

### GET /api/v1/events/{id} — Get Event
- **Success**: 200 + Event object
- **Errors**: 404

### PUT /api/v1/events/{id} — Replace Event
- **Input**: Same as create (all required)
- **Success**: 200 + Event object
- **Errors**: 404, 422, 503

### PATCH /api/v1/events/{id} — Partial Update
- **Input**: All fields optional
- **Success**: 200 + Event object
- **Errors**: 404, 422, 503

### DELETE /api/v1/events/{id} — Delete Event
- **Success**: 204
- **Errors**: 404

### GET /health — Health Check
- **Success**: 200 + {"status": "ok", "service": "event-service"}

---

## Data Model

**Event** (response):
- id, title, description, organizer_id, venue, city, start_date, end_date, capacity, price, status, created_at, updated_at

**EventCreate** (request):
- Required: title, organizer_id, venue, city, start_date, end_date, capacity, price
- Optional: description, status

**EventUpdate** (request for PATCH):
- All fields optional