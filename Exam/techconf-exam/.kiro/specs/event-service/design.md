# Event Service — Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Flask App                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  routes.py  │──▶│  models.py  │──▶│  repository.py      │  │
│  │  (HTTP)     │   │ (Business)  │   │ (Persistence)       │  │
│  └─────────────┘   └─────────────┘   └─────────────────────┘  │
│         ▲                                      ▲              │
│         │                                      │              │
│         │         ┌────────────────────────────┘              │
│         └────────▶│  client.py (HTTP calls to user-service)   │
│                   └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### routes.py (HTTP Layer)
- Request parsing & validation
- Response formatting
- Status codes, headers
- Delegates to models for business logic

### models.py (Business Logic Layer)
- Domain model: `Event` dataclass
- Validation functions
- Business rules: REQ-EVT-B01 through REQ-EVT-B06
- Calls `client.py` for user-service validation

### repository.py (Persistence Abstraction)
- Interface: `EventRepository` (ABC)
- Implementations: Memory, JSON, SQLite
- Factory: `create_event_repository()`

### client.py (Inter-service Communication)
- `UserServiceClient` — calls user-service to validate organizer
- Handles 404 → REFERENCE_NOT_FOUND, timeout/5xx → DEPENDENCY_UNAVAILABLE

### config.py
- Reads env vars: PORT, STORAGE_BACKEND, DATA_DIR, USER_SERVICE_URL

## Data Flow

**Create Event (POST)**:
1. routes.py parses JSON, validates required fields
2. models.py validates data (dates, lengths, enums)
3. models.py calls client.py to validate organizer exists and has role=organizer
4. repository.py generates UUID, timestamps, saves
5. routes.py returns 201 + Location + Event

**Update Event (PATCH/PUT)**:
1. Similar to create, but also validates status transitions (REQ-EVT-B04)
2. If organizer_id changes, re-validate with user-service

## Error Handling
- Validation errors → 422 VALIDATION_ERROR
- Organizer not found → 422 REFERENCE_NOT_FOUND
- Invalid organizer role → 422 INVALID_ORGANIZER
- Invalid status transition → 422 INVALID_STATUS_TRANSITION
- User-service unavailable → 503 DEPENDENCY_UNAVAILABLE
- Not found → 404 NOT_FOUND
- Malformed JSON → 400 MALFORMED_JSON

## Storage Schema

Same pattern as user-service: memory dict, JSON file, SQLite table with indexes on organizer_id, status, city.

## Testing Strategy
- Unit: Mock repository and UserServiceClient, test models validation & business rules
- Unit: Test all three repository implementations with tmp_path
- Contract: assert_matches_contract for each endpoint
- Integration: Launch real service, test via HTTP client