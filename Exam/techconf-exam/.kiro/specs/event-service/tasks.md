# Event Service — Tasks

## Task Breakdown

### T-01: Configuration & Repository Factory
- [x] Create `config.py` reading env vars (PORT, STORAGE_BACKEND, DATA_DIR, USER_SERVICE_URL)
- [x] Create `repository.py` with `EventRepository` ABC and three implementations
- [x] Create `create_event_repository()` factory function
- _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-B05, REQ-EVT-B06_

### T-02: User Service Client
- [x] Create `client.py` with `UserServiceClient` for calling user-service
- [x] Handle 404 → REFERENCE_NOT_FOUND, timeout/5xx → DEPENDENCY_UNAVAILABLE
- _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B05_

### T-03: Domain Models & Validation
- [x] Create `models.py` with `Event` dataclass
- [x] Implement validation functions
- [x] Implement business rules (organizer validation, date validation, status transitions, filters)
- _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-B06_

### T-04: HTTP Routes
- [x] Create `routes.py` with all 7 endpoints
- [x] Implement request/response handling
- [x] Integrate with models, repository, and client
- _Requirements: All endpoints_

### T-05: App Factory & Entry Point
- [x] Create `event_service/__init__.py` with `create_app()` factory
- [x] Create `event_service/__main__.py` for `python -m event_service`
- [x] Wire configuration, repository, client, routes

### T-06: Unit Tests
- [x] Test models validation (dates, lengths, enums, status transitions)
- [x] Test business rules (organizer validation, filters)
- [x] Test all three repository backends with tmp_path
- [x] Contract validation test for each endpoint
- _Requirements: Coverage ≥ 80%_

### T-07: Integration Tests (Own)
- [x] Launch real event-service with user-service, test CRUD via HTTP
- [x] Test inter-service calls

---

## Task Order
1. T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07
2. Commit after each task: `feat(event): <task description> [T-XX]`
