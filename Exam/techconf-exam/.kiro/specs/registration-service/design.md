# Registration Service — Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Flask App                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  routes.py  │──▶│  models.py  │──▶│  repository.py      │  │
│  │  (HTTP)     │   │ (Business)  │   │ (Persistence)       │  │
│  └─────────────┘   └─────────────┘   └─────────────────────┘  │
│         ▲                  ▲                    ▲             │
│         │                  │                    │             │
│         │         ┌────────┴────────┐          │             │
│         └────────▶│ client.py        │          │             │
│                   │ (user + event    │          │             │
│                   │  service calls)  │          │             │
│                   └──────────────────┘          │             │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### routes.py (HTTP Layer)
- Request parsing & validation
- Response formatting
- Status codes, headers
- Delegates to models for business logic

### models.py (Business Logic Layer)
- Domain model: `Registration` dataclass
- Validation functions
- Business rules: REQ-REG-B01 through REQ-REG-B09
- Calls `client.py` for user-service and event-service validation

### repository.py (Persistence Abstraction)
- Interface: `RegistrationRepository` (ABC)
- Implementations: Memory, JSON, SQLite
- Factory: `create_registration_repository()`

### client.py (Inter-service Communication)
- `UserServiceClient` — calls user-service
- `EventServiceClient` — calls event-service
- Handles 404 → REFERENCE_NOT_FOUND, timeout/5xx → DEPENDENCY_UNAVAILABLE

### config.py
- Reads env vars: PORT, STORAGE_BACKEND, DATA_DIR, USER_SERVICE_URL, EVENT_SERVICE_URL

## Data Flow

**Create Registration (POST)**:
1. routes.py parses JSON, validates required fields
2. models.py calls client.py to validate user exists and event exists
3. models.py checks event status == published
4. models.py checks for existing confirmed registration (REQ-REG-B04)
5. models.py checks capacity (REQ-REG-B05)
5. models.py gets event.price from event-service (REQ-REG-B06)
6. repository.py generates UUID, timestamps, saves
7. routes.py returns 201 + Location + Registration

**Stats (GET /stats)**:
1. routes.py calls event-service to verify event exists
2. repository.py counts confirmed registrations
3. Returns capacity, confirmed, available

## Error Handling
- Validation errors → 422 VALIDATION_ERROR
- User not found → 422 REFERENCE_NOT_FOUND
- Event not found → 422 REFERENCE_NOT_FOUND
- Event not published → 422 EVENT_NOT_OPEN
- Double registration → 409 ALREADY_REGISTERED
- Event full → 409 EVENT_FULL
- Invalid status transition → 422 INVALID_STATUS_TRANSITION
- Dependencies unavailable → 503 DEPENDENCY_UNAVAILABLE
- Not found → 404 NOT_FOUND
- Method not allowed → 405 METHOD_NOT_ALLOWED
- Malformed JSON → 400 MALFORMED_JSON

## Storage Schema

Same pattern as other services. Table indexes on user_id, event_id, status.

## Testing Strategy
- Unit: Mock repository, UserServiceClient, EventServiceClient
- Unit: Test all three repository implementations with tmp_path
- Contract: assert_matches_contract for each endpoint
- Integration: Launch real service with user/event, test via HTTP