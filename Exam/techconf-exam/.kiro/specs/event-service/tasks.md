# Implementation Plan: Event Service

## Overview

Implementation plan for the Event Service, preserving the existing task breakdown, requirement traceability, completion state, and execution order.

## Tasks

- [x] 1. T-01: Configuration & Repository Factory
  - [x] 1.1 Create `config.py` reading env vars (PORT, STORAGE_BACKEND, DATA_DIR, USER_SERVICE_URL)
  - [x] 1.2 Create `repository.py` with `EventRepository` ABC and three implementations
  - [x] 1.3 Create `create_event_repository()` factory function
  - _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-B05, REQ-EVT-B06_

- [x] 2. T-02: User Service Client
  - [x] 2.1 Create `client.py` with `UserServiceClient` for calling user-service
  - [x] 2.2 Handle 404 → REFERENCE_NOT_FOUND, timeout/5xx → DEPENDENCY_UNAVAILABLE
  - _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B05_

- [x] 3. T-03: Domain Models & Validation
  - [x] 3.1 Create `models.py` with `Event` dataclass
  - [x] 3.2 Implement validation functions
  - [x] 3.3 Implement business rules (organizer validation, date validation, status transitions, filters)
  - _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-B06_

- [x] 4. T-04: HTTP Routes
  - [x] 4.1 Create `routes.py` with all 7 endpoints
  - [x] 4.2 Implement request/response handling
  - [x] 4.3 Integrate with models, repository, and client
  - _Requirements: All endpoints_

- [x] 5. T-05: App Factory & Entry Point
  - [x] 5.1 Create `event_service/__init__.py` with `create_app()` factory
  - [x] 5.2 Create `event_service/__main__.py` for `python -m event_service`
  - [x] 5.3 Wire configuration, repository, client, routes

- [x] 6. T-06: Unit Tests
  - [x] 6.1 Test models validation (dates, lengths, enums, status transitions)
  - [x] 6.2 Test business rules (organizer validation, filters)
  - [x] 6.3 Test all three repository backends with tmp_path
  - [x] 6.4 Contract validation test for each endpoint
  - _Requirements: Coverage ≥ 80%_

- [x] 7. T-07: Integration Tests (Own)
  - [x] 7.1 Launch real event-service with user-service, test CRUD via HTTP
  - [x] 7.2 Test inter-service calls

- [ ] 8. T-08: Test Requirements Traceability and Coverage Verification
  - [x] 8.1 Add requirement traceability to every event-service unit and integration test using `@pytest.mark.req("REQ-...")`, a requirement ID in the test name, or a requirement ID in the test docstring
  - [x] 8.2 Register the `req` marker in the event-service pytest configuration to prevent unknown-marker warnings
  - [x] 8.3 Run the event-service unit test suite and verify that all unit tests pass
  - [x] 8.4 Run the event-service integration test suite and verify that all integration tests pass
  - [~] 8.5 Measure event-service coverage and verify that application coverage is at least 80%
  - _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-B05, REQ-EVT-B06_

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2"] },
    { "id": 2, "tasks": ["3"] },
    { "id": 3, "tasks": ["4"] },
    { "id": 4, "tasks": ["5"] },
    { "id": 5, "tasks": ["6"] },
    { "id": 6, "tasks": ["7"] },
    { "id": 7, "tasks": ["8"] }
  ]
}
```

## Notes

### Task Order
1. T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07 → T-08
2. Commit after each task: `feat(event): <task description> [T-XX]`
