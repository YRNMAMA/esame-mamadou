# TechConf — Technology Stack

## Runtime

- **Python**: 3.12
- **Web Framework**: Flask 3.x
- **HTTP Client**: requests 2.x

## Testing

- **Unit/Integration**: pytest 7.x/8.x
- **Mocking**: responses (for HTTP mocking in unit tests)
- **Coverage**: pytest-cov (target ≥ 80%)
- **Contract Validation**: jsonschema + PyYAML (provided validator)

## Persistence

Three backends supported via `STORAGE_BACKEND` env var:

| Backend | Description | Dependencies |
|---------|-------------|--------------|
| `memory` | In-memory dict (default) | None |
| `json` | File-based JSON in `DATA_DIR` | stdlib `json` |
| `sqlite` | SQLite database in `DATA_DIR` | stdlib `sqlite3` |

**Constraint**: Only standard library for persistence. No external DBMS.

## Configuration

All services read from environment variables:
- `PORT` — listen port (mandatory)
- `*_SERVICE_URL` — inter-service URLs (e.g., `USER_SERVICE_URL`)
- `STORAGE_BACKEND` — `memory` | `json` | `sqlite` (default: `memory`)
- `DATA_DIR` — data directory for json/sqlite (default: `./data`)

## Code Organization

- Each service is a self-contained Flask app in `services/<service>/`
- Shared code in `services/common/` (error formatting, pagination, HTTP client)
- Unit tests in `services/<service>/tests/`
- Specs in `.kiro/specs/<service>/`