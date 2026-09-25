# TechConf — Platform Standards

Source: Exam §4 (verbatim for Kiro steering)

## Service Startup

A `services.yaml` file in the repo root declares each implemented service:
- `cwd`: working directory (relative to repo root)
- `command`: shell command to start the service (must listen on `$PORT`)
- `health_path`: defaults to `/health`

The acceptance suite injects:
- `PORT` — the port the service **must** listen on
- `USER_SERVICE_URL`, `EVENT_SERVICE_URL`, `REGISTRATION_SERVICE_URL`, `FEEDBACK_SERVICE_URL`, `NOTIFICATION_SERVICE_URL`

## API Conventions

- **Base path**: `/api/v1/<resource>`
- **Format**: JSON, snake_case field names
- **IDs**: UUID v4, server-generated, never accepted in input
- **Timestamps**: ISO 8601 UTC (`2026-10-15T09:30:00Z`); every resource has `created_at` and `updated_at`
- **Dates**: `YYYY-MM-DD`
- **Amounts**: Decimal with 2 places (`149.00`), implicit EUR
- **Pagination**: `?page=1&page_size=20` (max 100) → `{"items": [...], "page": 1, "page_size": 20, "total": 57}`

## Error Format

Always:
```json
{
  "error": {
    "code": "UPPER_SNAKE",
    "message": "Human-readable description",
    "details": {}
  }
}
```

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 201 | Created (+ `Location` header) |
| 200 | Success (read/modify) |
| 204 | Deleted |
| 400 | Malformed JSON |
| 404 | `NOT_FOUND` |
| 405 | Method not allowed |
| 409 | Conflict (e.g., duplicate email, double registration) |
| 422 | `VALIDATION_ERROR` / `REFERENCE_NOT_FOUND` / business rule |
| 503 | `DEPENDENCY_UNAVAILABLE` |

## Inter-Service Calls

- URLs **only** from env vars (`USER_SERVICE_URL`, etc.)
- Default: `http://localhost:<port>`
- Timeout: 2 seconds
- **404 from dependency** → return 422 `REFERENCE_NOT_FOUND`
- **Timeout / connection refused / 5xx** → return 503 `DEPENDENCY_UNAVAILABLE`

## Health Endpoint

`GET /health` → `200 {"status": "ok", "service": "<name>"}`

## Persistence

- `STORAGE_BACKEND` = `memory` (default) | `json` | `sqlite`
- With `json`/`sqlite`: files in `DATA_DIR` (default `./data`, git-ignored)
- **Only stdlib**: `json`, `sqlite3` — no external DBMS
- Backend switch must not require business logic changes

## Python Dependencies

- Runtime: `flask`, `requests`
- Test: `pytest`, `pytest-cov`, `responses`