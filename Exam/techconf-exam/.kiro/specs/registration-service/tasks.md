# Implementation Plan: Registration Service

## Overview

Implementation plan for the Registration Service, preserving the existing task breakdown, requirement traceability, completion state, and execution order.

## Tasks

- [x] 1. T-01: Configuration & Repository Factory
  - [x] 1.1 Create `config.py` reading env vars (PORT, STORAGE_BACKEND, DATA_DIR, USER_SERVICE_URL, EVENT_SERVICE_URL)
  - [x] 1.2 Create `repository.py` with `RegistrationRepository` ABC and three implementations
  - [x] 1.3 Create `create_registration_repository()` factory function

- [x] 2. T-02: Service Clients
  - [x] 2.1 Create `client.py` with `UserServiceClient` and `EventServiceClient`
  - [x] 2.2 Handle 404 → REFERENCE_NOT_FOUND, timeout/5xx → DEPENDENCY_UNAVAILABLE

- [x] 3. T-03: Domain Models & Validation
  - [x] 3.1 Create `models.py` with `Registration` dataclass
  - [x] 3.2 Implement validation functions
  - [x] 3.3 Implement business rules (user/event validation, double registration, capacity, amount, status transitions, stats)

- [x] 4. T-04: HTTP Routes
  - [x] 4.1 Create `routes.py` with all 8 endpoints (including PUT 405)
  - [x] 4.2 Implement request/response handling
  - [x] 4.3 Integrate with models, repository, and clients

- [x] 5. T-05: App Factory & Entry Point
  - [x] 5.1 Create `registration_service/__init__.py` with `create_app()` factory
  - [x] 5.2 Create `registration_service/__main__.py` for `python -m registration_service`
  - [x] 5.3 Wire configuration, repository, clients, routes

- [x] 6. T-06: Unit Tests
  - [x] 6.1 Test models validation (capacity, status transitions, stats)
  - [x] 6.2 Test business rules (double registration, capacity, amount, stats)
  - [x] 6.3 Test all three repository backends with tmp_path
  - [x] 6.4 Contract validation test for each endpoint
  - [x] 6.5 Coverage ≥ 80%

- [x] 7. T-07: Integration Tests (Own)
  - [x] 7.1 Launch real registration-service with user/event, test CRUD via HTTP
  - [x] 7.2 Test inter-service calls

- [ ] 8. T-08: Test Requirements Traceability and Coverage Verification
  - [x] 8.1 Add requirement traceability to every registration-service unit and integration test using `@pytest.mark.req("REQ-...")`, a requirement ID in the test name, or a requirement ID in the test docstring
  - [x] 8.2 Register the `req` marker in the registration-service pytest configuration to prevent unknown-marker warnings
  - [x] 8.3 Run the registration-service unit test suite and verify that all unit tests pass
  - [x] 8.4 Run the registration-service integration test suite and verify that all integration tests pass
  - [~] 8.5 Measure registration-service coverage and verify that application coverage is at least 80%
  - _Requirements: REQ-REG-B01, REQ-REG-B02, REQ-REG-B03, REQ-REG-B04, REQ-REG-B05, REQ-REG-B06, REQ-REG-B07, REQ-REG-B08, REQ-REG-B09_

- [ ] 9. T-09: Complete the Bug Register with Verifiable Evidence
  - [~] 9.1 Inspect `BUGS.md` and identify every placeholder for issue references, regression tests, and commit hashes
  - [~] 9.2 Check `gh auth status`; only when GitHub CLI authentication is active, use `gh` to create or close the required real issues
  - [~] 9.3 Record real GitHub issue references in `BUGS.md` without inventing issue numbers when GitHub CLI authentication is unavailable
  - [~] 9.4 Record the real regression test name for each documented bug after verifying that the named test exists
  - [~] 9.5 Record the real commit hash for each documented fix after verifying that the commit exists in Git history
  - [~] 9.6 Verify that `BUGS.md` documents at least two closed bugs and that at least one is classified as an implementation bug, as required by Exam.MD §6.5
  - _Requirements: REQ-REG-B07, REQ-USR-B01_

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
    { "id": 7, "tasks": ["8"] },
    { "id": 8, "tasks": ["9"] }
  ]
}
```

## Notes

### Task Order
1. T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07 → T-08 → T-09
2. Commit after each task: `feat(registration): <task description> [T-XX]`
