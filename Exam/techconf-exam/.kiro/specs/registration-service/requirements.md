# Registration Service — Requirements

## User Stories & Acceptance Criteria (EARS Notation)

### REQ-REG-B01 — User Must Exist
**User Story**: As a registration service, I want to validate that the user exists in user-service, so that only registered users can register for events.

**Acceptance Criteria**
1. WHEN a registration is created with a user_id THE SYSTEM SHALL call user-service GET /api/v1/users/{id}
2. IF user-service returns 404 THE SYSTEM SHALL respond 422 with error code `REFERENCE_NOT_FOUND`
3. IF user-service is unreachable THE SYSTEM SHALL respond 503 with error code `DEPENDENCY_UNAVAILABLE`

### REQ-REG-B02 — Event Must Exist
**User Story**: As a registration service, I want to validate that the event exists in event-service.

**Acceptance Criteria**
1. WHEN a registration is created with an event_id THE SYSTEM SHALL call event-service GET /api/v1/events/{id}
2. IF event-service returns 404 THE SYSTEM SHALL respond 422 with error code `REFERENCE_NOT_FOUND`
3. IF event-service is unreachable THE SYSTEM SHALL respond 503 with error code `DEPENDENCY_UNAVAILABLE`

### REQ-REG-B03 — Event Must Be Published
**User Story**: As an event organizer, I want only published events to accept registrations.

**Acceptance Criteria**
1. WHEN a registration is created for an event with status != published THE SYSTEM SHALL respond 422 with error code `EVENT_NOT_OPEN`

### REQ-REG-B04 — No Double Registration
**User Story**: As a user, I want to be prevented from registering twice for the same event.

**Acceptance Criteria**
1. WHEN a user tries to create a second registration for the same event with status=confirmed THE SYSTEM SHALL respond 409 with error code `ALREADY_REGISTERED`

### REQ-REG-B05 — Capacity Enforcement
**User Story**: As an event organizer, I want registrations to stop when the event is full.

**Acceptance Criteria**
1. WHEN a registration is requested AND confirmed registrations < event.capacity THE SYSTEM SHALL create it with status "confirmed"
2. IF confirmed registrations == event.capacity THE SYSTEM SHALL respond 409 with error code `EVENT_FULL`
3. WHEN a confirmed registration is cancelled THE SYSTEM SHALL free one seat

### REQ-REG-B06 — Amount from Event Price
**User Story**: As a platform, I want the registration amount to be copied from event.price at registration time.

**Acceptance Criteria**
1. WHEN a registration is created THE SYSTEM SHALL set amount = event.price (read from event-service)
2. THE amount field is read-only, never accepted from client

### REQ-REG-B07 — Status Transitions
**User Story**: As a user, I want to cancel my registration but not re-confirm a cancelled one.

**Acceptance Criteria**
1. WHEN status changes from confirmed to cancelled THE SYSTEM SHALL allow it
2. WHEN status changes from cancelled to confirmed THE SYSTEM SHALL respond 422 with error code `INVALID_STATUS_TRANSITION`

### REQ-REG-B08 — Stats Endpoint
**User Story**: As an organizer, I want to see registration stats for an event.

**Acceptance Criteria**
1. WHEN stats is requested for an event_id THE SYSTEM SHALL return {event_id, capacity, confirmed, available}
2. IF event doesn't exist THE SYSTEM SHALL respond 404 with error code `NOT_FOUND`

### REQ-REG-B09 — Dependency Unavailable
**User Story**: As a platform, I want registration-service to handle dependency unavailability.

**Acceptance Criteria**
1. WHEN user-service or event-service is unreachable THE SYSTEM SHALL respond 503 with error code `DEPENDENCY_UNAVAILABLE`

---

## API Endpoints (from OpenAPI contract)

### POST /api/v1/registrations — Create Registration
- **Input**: user_id (UUID), event_id (UUID)
- **Success**: 201 + Location header + Registration object (amount from event, status=confirmed)
- **Errors**: 400, 409 (ALREADY_REGISTERED, EVENT_FULL), 422 (REFERENCE_NOT_FOUND, EVENT_NOT_OPEN), 503

### GET /api/v1/registrations — List Registrations
- **Query**: page, page_size, user_id, event_id, status
- **Success**: 200 + RegistrationPage object
- **Errors**: 422

### GET /api/v1/registrations/stats — Registration Stats
- **Query**: event_id (required)
- **Success**: 200 + RegistrationStats object
- **Errors**: 404, 422, 503

### GET /api/v1/registrations/{id} — Get Registration
- **Success**: 200 + Registration object
- **Errors**: 404

### PATCH /api/v1/registrations/{id} — Update Status
- **Input**: status (confirmed|cancelled)
- **Success**: 200 + Registration object
- **Errors**: 404, 422

### DELETE /api/v1/registrations/{id} — Delete Registration
- **Success**: 204
- **Errors**: 404

### PUT /api/v1/registrations/{id} — Not Allowed
- **Error**: 405

### GET /health — Health Check
- **Success**: 200 + {"status": "ok", "service": "registration-service"}

---

## Data Model

**Registration** (response):
- id, user_id, event_id, amount, status, created_at, updated_at

**RegistrationCreate** (request):
- Required: user_id, event_id

**RegistrationPatch** (request):
- Required: status