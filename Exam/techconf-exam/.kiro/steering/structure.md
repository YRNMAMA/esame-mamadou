# TechConf — Code Structure Decisions

## Repository Layout

```
techconf-exam/
├── .kiro/
│   ├── steering/           # Platform-wide steering files
│   └── specs/
│       ├── user-service/
│       ├── event-service/
│       └── registration-service/
├── contracts/              # Non-modifiable OpenAPI contracts
├── tests/integration/      # Non-modifiable acceptance suite
├── services/
│   ├── common/             # Shared utilities (errors, pagination, HTTP client)
│   ├── user-service/
│   │   ├── app/            # Flask app package
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   ├── models.py
│   │   │   ├── repository.py
│   │   │   └── client.py
│   │   └── tests/          # Unit tests
│   ├── event-service/
│   │   ├── app/
│   │   └── tests/
│   └── registration-service/
│       ├── app/
│       └── tests/
├── services.yaml           # Manifest for acceptance suite
└── README.md
```

## Design Principles

### 1. Service Independence
- Each service is a separate Flask app with its own `app/` package
- Services communicate **only via HTTP** using env var URLs
- No direct imports between service packages
- Shared code lives in `services/common/` only

### 2. Internal Layering (per service)
```
routes.py       # HTTP layer: request parsing, response formatting, status codes
    │
    ▼
models.py       # Domain models, validation, business rules (REQ-*-B*)
    │
    ▼
repository.py   # Persistence abstraction (memory/json/sqlite)
    │
    ▼
client.py       # Outbound HTTP calls to other services
```

**Why**: Separates concerns, makes testing easy (mock repository or client), enables storage backend swap without touching business logic.

### 3. Shared Code (`services/common/`)
| Module | Purpose |
|--------|---------|
| `errors.py` | Standard error response format (`{"error": {"code", "message", "details"}}`) |
| `pagination.py` | Pagination helper (`page`, `page_size`, `total` → dict) |
| `http_client.py` | Thin `requests` wrapper with timeout, env var URL resolution, error mapping (404→422 REFERENCE_NOT_FOUND, timeout/5xx→503 DEPENDENCY_UNAVAILABLE) |

**Coupling trade-off**: Shared library creates compile-time coupling but eliminates duplication of error formats, pagination logic, and HTTP client patterns. If a service moves to another team, the common code can be vendored or published as a package.

### 4. Configuration
- Single `config.py` per service reads all env vars at startup
- Validates required vars (`PORT`)
- Provides defaults for optional vars
- Injected into repository and client constructors

### 5. Testing Strategy
- **Unit tests**: `services/<svc>/tests/` — mock repository and HTTP client
- **Integration tests (own)**: Launch real services via pytest fixtures, test cross-service flows
- **Acceptance tests**: Provided suite in `tests/integration/` (run against `services.yaml`)

### 6. Data Files
- `DATA_DIR` (default `./data`) holds JSON/SQLite files
- Added to `.gitignore` at repo root

### 7. Spec Organization
- One spec per service: `.kiro/specs/<service>/`
- Each spec has `requirements.md`, `design.md`, `tasks.md`
- Requirements trace to `REQ-*-B*` IDs from exam spec