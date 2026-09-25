# User Service — Tasks

## Task Breakdown

### T-01: Configuration & Repository Factory
- [x] Create `config.py` reading env vars (PORT, STORAGE_BACKEND, DATA_DIR)
- [x] Create `repository.py` with `UserRepository` ABC and three implementations
- [x] Create `create_user_repository()` factory function
- _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03_

### T-02: Domain Models & Validation
- [x] Create `models.py` with `User` dataclass
- [x] Implement validation functions (email, lengths, role)
- [x] Implement business rules (uniqueness check, email normalization, filters)
- _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03_

### T-03: HTTP Routes
- [x] Create `routes.py` with all 7 endpoints
- [x] Implement request/response handling
- [x] Integrate with models and repository
- _Requirements: All endpoints_

### T-04: App Factory & Entry Point
- [x] Create `app/__init__.py` with `create_app()` factory
- [x] Create `app/__main__.py` for `python -m app` entry point
- [x] Wire configuration, repository, routes

### T-05: Unit Tests
- [x] Test models validation (email, lengths, role, normalization)
- [x] Test business rules (uniqueness, filters)
- [x] Test all three repository backends with `tmp_path`
- [x] Contract validation test for each endpoint
- _Requirements: Coverage ≥ 80%_

### T-06: Integration Tests (Own)
- [x] Launch real user-service, test CRUD via HTTP
- [x] Test inter-service calls (when event/registration exist)

---

## Task Order
1. T-01 → T-02 → T-03 → T-04 → T-05 → T-06
2. Commit after each task: `feat(user): <task description> [T-XX]`
