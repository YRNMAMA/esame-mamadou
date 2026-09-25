# Implementation Plan: User Service

## Overview

Implementation plan for the User Service, preserving the existing task breakdown, requirement traceability, completion state, and execution order.

## Tasks

- [x] 1. T-01: Configuration & Repository Factory
  - [x] 1.1 Create `config.py` reading env vars (PORT, STORAGE_BACKEND, DATA_DIR)
  - [x] 1.2 Create `repository.py` with `UserRepository` ABC and three implementations
  - [x] 1.3 Create `create_user_repository()` factory function
  - _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03_

- [x] 2. T-02: Domain Models & Validation
  - [x] 2.1 Create `models.py` with `User` dataclass
  - [x] 2.2 Implement validation functions (email, lengths, role)
  - [x] 2.3 Implement business rules (uniqueness check, email normalization, filters)
  - _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03_

- [x] 3. T-03: HTTP Routes
  - [x] 3.1 Create `routes.py` with all 7 endpoints
  - [x] 3.2 Implement request/response handling
  - [x] 3.3 Integrate with models and repository
  - _Requirements: All endpoints_

- [x] 4. T-04: App Factory & Entry Point
  - [x] 4.1 Create `app/__init__.py` with `create_app()` factory
  - [x] 4.2 Create `app/__main__.py` for `python -m app` entry point
  - [x] 4.3 Wire configuration, repository, routes

- [x] 5. T-05: Unit Tests
  - [x] 5.1 Test models validation (email, lengths, role, normalization)
  - [x] 5.2 Test business rules (uniqueness, filters)
  - [x] 5.3 Test all three repository backends with `tmp_path`
  - [x] 5.4 Contract validation test for each endpoint
  - _Requirements: Coverage ≥ 80%_

- [x] 6. T-06: Integration Tests (Own)
  - [x] 6.1 Launch real user-service, test CRUD via HTTP
  - [x] 6.2 Test inter-service calls (when event/registration exist)

- [ ] 7. T-07: Test Requirements Traceability and Coverage Verification
  - [x] 7.1 Add requirement traceability to every user-service test using `@pytest.mark.req("REQ-...")`, a requirement ID in the test name, or a requirement ID in the test docstring
  - [x] 7.2 Register the `req` marker in the user-service pytest configuration to prevent unknown-marker warnings
  - [x] 7.3 Run the user-service test suite and verify that all tests pass
  - [ ] 7.4 Measure user-service coverage and verify that application coverage is at least 80%
  - _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03_

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
    { "id": 6, "tasks": ["7"] }
  ]
}
```

## Notes

### Task Order
1. T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07
2. Commit after each task: `feat(user): <task description> [T-XX]`
