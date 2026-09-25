# Registration Service — Tasks

## Task Breakdown

### T-01: Configuration & Repository Factory
- [x] Create `config.py` reading env vars (PORT, STORAGE_BACKEND, DATA_DIR, USER_SERVICE_URL, EVENT_SERVICE_URL)
- [x] Create `repository.py` with `RegistrationRepository` ABC and three implementations
- [x] Create `create_registration_repository()` factory function

### T-02: Service Clients
- [x] Create `client.py` with `UserServiceClient` and `EventServiceClient`
- [x] Handle 404 → REFERENCE_NOT_FOUND, timeout/5xx → DEPENDENCY_UNAVAILABLE

### T-03: Domain Models & Validation
- [x] Create `models.py` with `Registration` dataclass
- [x] Implement validation functions
- [x] Implement business rules (user/event validation, double registration, capacity, amount, status transitions, stats)

### T-04: HTTP Routes
- [x] Create `routes.py` with all 8 endpoints (including PUT 405)
- [x] Implement request/response handling
- [x] Integrate with models, repository, and clients

### T-05: App Factory & Entry Point
- [x] Create `registration_service/__init__.py` with `create_app()` factory
- [x] Create `registration_service/__main__.py` for `python -m registration_service`
- [x] Wire configuration, repository, clients, routes

### T-06: Unit Tests
- [x] Test models validation (capacity, status transitions, stats)
- [x] Test business rules (double registration, capacity, amount, stats)
- [x] Test all three repository backends with tmp_path
- [x] Contract validation test for each endpoint
- [x] Coverage ≥ 80%

### T-07: Integration Tests (Own)
- [x] Launch real registration-service with user/event, test CRUD via HTTP
- [x] Test inter-service calls

---

## Task Order
1. T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07
2. Commit after each task: `feat(registration): <task description> [T-XX]`
