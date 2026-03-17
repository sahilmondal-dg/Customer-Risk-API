# EXECUTION_PLAN.md
**Customer Risk API · Version 1.0**
_Classification: Training Demo System_
_Date: 2026-03-17 · Status: Draft_

---

## Resolved Decisions

The following open questions from ARCHITECTURE.md are resolved before planning proceeds.

| Open Question | Resolution |
|---|---|
| Customer ID prefix and format | `CUST-\d{4}` (e.g. `CUST-0042`) — pattern confirmed for INV-11 |
| Risk factor code values | `HIGH_TRANSACTION_VOLUME`, `MULTIPLE_JURISDICTIONS`, `ADVERSE_MEDIA_MATCH`, `PEP_ASSOCIATION`, `UNUSUAL_ACCOUNT_ACTIVITY` — confirmed for INV-13 |
| Can MEDIUM/HIGH customers have zero risk factors? | No — at least one factor is required for MEDIUM and HIGH tier customers |
| Health endpoint requirement | Required at `/health`, unauthenticated, returns `{"status": "ok"}` — confirmed for INV-21 |

---

## Session Overview

| Session | Name | Goal | Tasks | Est. Duration |
|---|---|---|---|---|
| 1 | Foundation | Repository scaffold, Docker Compose stack, and Postgres schema initialised and healthy | 3 | 60 min |
| 2 | Data Layer | Read-only DB access module with parameterised queries, retry logic, and query timeout | 2 | 45 min |
| 3 | API Layer | Protected `/api/customer/{customer_id}` endpoint with auth, validation, and error handling | 3 | 60 min |
| 4 | UI and Integration | Proxy route, static HTML UI, and full end-to-end stack verification | 2 | 45 min |

---

## Session 1 — Foundation

**Session Goal:** A running Docker Compose stack with two containers (FastAPI + Postgres) where Postgres is healthy, the schema and seed data are loaded on a fresh volume, and the FastAPI container starts and remains running. No application logic yet — only verified infrastructure.

**Integration Check:**
```bash
docker compose up -d && \
  docker compose ps --format json | python3 -c "
import sys, json
services = [json.loads(l) for l in sys.stdin]
names = [s['Service'] for s in services]
states = {s['Service']: s['State'] for s in services}
assert set(names) == {'api', 'db'}, f'Expected exactly two services, got {names}'
assert states['db'] == 'running', f'db not running: {states[\"db\"]}'
assert states['api'] == 'running', f'api not running: {states[\"api\"]}'
print('PASS: exactly two containers running')
" && \
  docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
    SELECT COUNT(*) FROM customer;
    SELECT COUNT(*) FROM risk_factor;
  "
```
_This verifies that the two-container constraint (INV-19) holds and that the seed data is loaded — neither of which is confirmed by any individual task verification command._

---

### Task 1.1 — Repository Scaffold

**Description:** Initialise the repository directory structure, create all placeholder files, install Python dependencies, and confirm the base environment is importable. No application logic. Output: a committed directory tree with a working `requirements.txt` and a `docker-compose.yml` skeleton.

**CC Prompt:**
```
Initialise the repository structure for the Customer Risk API project.

Create the following directory tree and files (empty or with minimal placeholder content):
  .
  ├── docker-compose.yml          # skeleton only — two services: api, db
  ├── .env.example                # placeholder: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, API_KEY
  ├── api/
  │   ├── Dockerfile
  │   ├── requirements.txt        # fastapi, uvicorn, psycopg2-binary
  │   └── main.py                 # placeholder: FastAPI app with no routes yet
  └── db/
      ├── 01_schema.sql           # placeholder comment only
      └── 02_seed.sql             # placeholder comment only

Rules:
- docker-compose.yml must define exactly two services named `api` and `db`.
- The `api` service must build from ./api/Dockerfile.
- The `db` service must use the official postgres image.
- Do not add any application logic, routes, or DB queries yet.
- Do not create any files not listed above.
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Run `docker compose config --services` | Output contains exactly `api` and `db`, nothing else |
| TC-2 | Run `pip install -r api/requirements.txt` in a clean venv | Exit code 0; fastapi, uvicorn, psycopg2-binary installed |
| TC-3 | Import `main` from api/main.py in a Python 3.11 interpreter | No ImportError |
| TC-4 | Run `docker compose build api` | Exit code 0 |

**Verification Command:**
```bash
docker compose config --services | sort | diff - <(echo -e "api\ndb") && \
  python3 -c "import sys; sys.path.insert(0,'api'); import main; print('PASS: main importable')"
```

**Invariant Flag:** INV-19 (two-container constraint). Code review: confirm `docker-compose.yml` defines exactly `api` and `db` — no third service present.

---

### Task 1.2 — Database Schema and Seed Data

**Description:** Write `01_schema.sql` and `02_seed.sql`. Schema defines the `customer` and `risk_factor` tables with all constraints. Seed data populates representative records covering all three tiers and all five risk factor codes. Output: two `.sql` files deployable via `/docker-entrypoint-initdb.d/`.

**CC Prompt:**
```
Write the Postgres schema and seed data for the Customer Risk API.

File: db/01_schema.sql
- Create table `customer` with columns: `customer_id VARCHAR PRIMARY KEY`, `risk_tier VARCHAR NOT NULL`.
- Add CHECK constraint on `risk_tier` restricting values to exactly: 'LOW', 'MEDIUM', 'HIGH'.
- Create table `risk_factor` with columns: `id SERIAL PRIMARY KEY`, `customer_id VARCHAR NOT NULL`, `code VARCHAR NOT NULL`, `description TEXT NOT NULL`.
- Add FOREIGN KEY on `risk_factor.customer_id` referencing `customer.customer_id` with ON DELETE CASCADE.
- Add CHECK constraint on `risk_factor.code` restricting values to exactly: 'HIGH_TRANSACTION_VOLUME', 'MULTIPLE_JURISDICTIONS', 'ADVERSE_MEDIA_MATCH', 'PEP_ASSOCIATION', 'UNUSUAL_ACCOUNT_ACTIVITY'.
- All DDL must be idempotent: use CREATE TABLE IF NOT EXISTS.

File: db/02_seed.sql
- Insert using INSERT ... ON CONFLICT DO NOTHING.
- Seed at minimum:
  - Two LOW tier customers: at least one with zero risk factors, one with one or more factors.
  - Two MEDIUM tier customers: each with at least one risk factor.
  - Two HIGH tier customers: each with at least one risk factor.
  - All five risk factor codes must appear at least once across the seed data.
- Use customer_id format CUST-NNNN (e.g. CUST-0001).

Do not modify any other files.
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Run schema against a fresh Postgres instance | Both tables created; no errors |
| TC-2 | Run seed after schema | All rows inserted; no errors |
| TC-3 | Run seed a second time (idempotency) | No errors; row counts unchanged |
| TC-4 | Attempt to insert a `risk_tier` value of 'PENDING' directly | DB rejects with constraint violation |
| TC-5 | Attempt to insert a `risk_factor.code` of 'UNKNOWN_CODE' directly | DB rejects with constraint violation |
| TC-6 | Attempt to insert a `risk_factor` with a non-existent `customer_id` | DB rejects with FK violation |
| TC-7 | Query `SELECT COUNT(*) FROM customer` | ≥ 6 rows |
| TC-8 | All five codes appear in seed data | `SELECT DISTINCT code FROM risk_factor` returns all five |
| TC-9 | At least one LOW customer has zero factors | Query confirms empty factor set for that customer |

**Verification Command:**
```bash
docker compose up -d db && sleep 3 && \
  docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
    SELECT COUNT(*) AS customers FROM customer;
    SELECT COUNT(DISTINCT code) AS distinct_codes FROM risk_factor;
    SELECT customer_id FROM customer c WHERE risk_tier='LOW' AND NOT EXISTS (SELECT 1 FROM risk_factor rf WHERE rf.customer_id = c.customer_id) LIMIT 1;
  "
```

**Invariant Flag:** INV-03 (read-only DB role — schema must not grant write to app user), INV-12 (CHECK constraint on tier), INV-13 (CHECK constraint on code), INV-14 (FK constraint), INV-15 (PRIMARY KEY on customer_id), INV-23 (seed coverage). Code review: confirm CHECK constraints exist on both restricted columns; confirm FK with ON DELETE CASCADE; confirm PRIMARY KEY on `customer_id`.

---

### Task 1.3 — Docker Compose Wiring and Healthcheck

**Description:** Complete `docker-compose.yml` with the Postgres healthcheck, `depends_on: condition: service_healthy` for the api service, environment variable bindings from `.env`, and volume mount for init scripts. Output: a `docker-compose.yml` that brings up both containers cleanly from a fresh volume.

**CC Prompt:**
```
Complete docker-compose.yml for the Customer Risk API.

Requirements:
- `db` service: use image postgres:15, set POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB from environment variables (sourced from .env). Mount ./db/ to /docker-entrypoint-initdb.d/. Add a healthcheck using pg_isready with interval 5s, timeout 5s, retries 5.
- `api` service: build from ./api/Dockerfile. Set all environment variables required by the app (POSTGRES_* and API_KEY). Expose port 8000. Add depends_on with condition: service_healthy referencing the db service.
- Both services must be on a single internal Docker network named `app-net`. The api container must have NO external network access beyond this internal network — do not add any external network definitions or default bridge access.
- Exactly two services. No additional services.

Do not modify any files other than docker-compose.yml and api/Dockerfile (Dockerfile may add uvicorn startup command only).
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | `docker compose up -d` on fresh volume | Both containers reach 'running' state; no restart loops |
| TC-2 | `docker compose ps` | Exactly two services listed |
| TC-3 | `docker compose logs db` | No startup errors; "database system is ready to accept connections" present |
| TC-4 | `docker compose logs api` | FastAPI placeholder starts without error |
| TC-5 | Inspect network config | api container has no external network access |

**Verification Command:**
```bash
docker compose up -d && sleep 5 && \
  docker compose ps --format "table {{.Service}}\t{{.State}}" && \
  docker compose exec db pg_isready -U "$POSTGRES_USER" && \
  echo "PASS: stack healthy"
```

**Invariant Flag:** INV-08 (no external network), INV-19 (two-container constraint), INV-20 (DB connection failure behaviour — healthcheck is the mechanism). Code review: confirm no third service; confirm internal network only on api; confirm healthcheck present on db; confirm depends_on condition: service_healthy.

---

## Session 2 — Data Layer

**Session Goal:** A standalone, importable Python module (`db.py`) that exposes a single function `get_customer(customer_id: str)` returning a typed dict or raising defined exceptions. The function must use parameterised queries, enforce a 5-second timeout, and implement the retry loop. Verified in isolation without a running HTTP server.

**Integration Check:**
```bash
docker compose up -d && sleep 5 && \
  docker compose exec api python3 -c "
from db import get_customer, CustomerNotFoundError
result = get_customer('CUST-0001')
assert 'customer_id' in result
assert result['risk_tier'] in ('LOW','MEDIUM','HIGH')
assert isinstance(result['risk_factors'], list)
print('PASS: get_customer returns valid structure for CUST-0001')
try:
    get_customer('CUST-9999')
    print('FAIL: expected CustomerNotFoundError')
except CustomerNotFoundError:
    print('PASS: CustomerNotFoundError raised for unknown ID')
"
```
_This verifies that the DB module connects through the real Docker network and returns the correct shape — not tested by any individual task command._

---

### Task 2.1 — Database Connection and Retry Module

**Description:** Write `api/db.py` with connection initialisation, a retry loop (10 attempts, 1-second sleep), a 5-second query timeout constant, and a read-only Postgres role setup. Output: `db.py` with a `get_connection()` function and defined exception types.

**CC Prompt:**
```
Write api/db.py for the Customer Risk API.

This module handles all database connectivity. Do not add any HTTP or FastAPI logic here.

Requirements:
- Define a module-level constant: QUERY_TIMEOUT_SECONDS = 5
- Define two custom exceptions: CustomerNotFoundError and DataIntegrityError (both inherit from Exception).
- Implement get_connection() which:
  - Reads DB connection parameters from environment variables: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB.
  - Attempts to connect up to 10 times, sleeping 1 second between attempts.
  - On each attempt, if connection fails, logs a human-readable message (not a stack trace) to stderr.
  - After 10 failed attempts, raises a RuntimeError with message "Database unavailable after 10 attempts" and exits with sys.exit(1).
  - On success, sets the connection's options to enforce a statement_timeout of QUERY_TIMEOUT_SECONDS * 1000 milliseconds using SET statement_timeout.
  - Returns the psycopg2 connection object.
- The Postgres role connected must be a read-only role. Document in a comment that this role is configured in 01_schema.sql (to be enforced there — not in this file).
- Do not use any ORM. Use psycopg2 directly.
- Do not import FastAPI or any HTTP library.
- Do not create or modify any files other than api/db.py.
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Call `get_connection()` with valid env vars pointing to running Postgres | Returns a live psycopg2 connection; no exception |
| TC-2 | Call `get_connection()` with unreachable host | After 10 attempts (≈10 seconds), raises RuntimeError with "Database unavailable" message |
| TC-3 | Inspect connection after `get_connection()` | `SHOW statement_timeout` returns '5000ms' or equivalent |
| TC-4 | QUERY_TIMEOUT_SECONDS is a named constant | `from db import QUERY_TIMEOUT_SECONDS; assert QUERY_TIMEOUT_SECONDS == 5` |
| TC-5 | Attempt an INSERT via the returned connection | DB rejects with permission denied (read-only role) |

**Verification Command:**
```bash
docker compose exec api python3 -c "
from db import get_connection, QUERY_TIMEOUT_SECONDS
assert QUERY_TIMEOUT_SECONDS == 5, 'Timeout constant wrong'
conn = get_connection()
cur = conn.cursor()
cur.execute('SHOW statement_timeout')
timeout = cur.fetchone()[0]
print(f'statement_timeout: {timeout}')
conn.close()
print('PASS: connection established with timeout set')
"
```

**Invariant Flag:** INV-03 (read-only role), INV-20 (DB connection failure behaviour — retry loop and exit code), INV-22 (query timeout — QUERY_TIMEOUT_SECONDS constant). Code review: confirm QUERY_TIMEOUT_SECONDS is a named constant not an inline literal; confirm retry loop exits with sys.exit(1) after 10 attempts; confirm statement_timeout is set on the connection.

---

### Task 2.2 — Customer Lookup Query

**Description:** Add `get_customer(customer_id: str)` to `api/db.py`. This function issues two parameterised queries (customer row, then risk factor rows), assembles the result dict, validates the returned tier value and factor codes against the allowed sets, and raises defined exceptions for not-found and integrity error cases. Output: the completed `get_customer` function.

**CC Prompt:**
```
Add the get_customer function to api/db.py.

Function signature: get_customer(customer_id: str) -> dict

Requirements:
- Call get_connection() to obtain a connection. Use a try/finally to ensure the connection is always closed.
- Issue two parameterised queries using cursor.execute(query, (params,)) — never string interpolation or f-strings:
  1. SELECT customer_id, risk_tier FROM customer WHERE customer_id = %s
  2. SELECT code, description FROM risk_factor WHERE customer_id = %s
- If query 1 returns zero rows: raise CustomerNotFoundError.
- If query 1 returns more than one row: raise DataIntegrityError with message "Duplicate customer record".
- Validate the returned risk_tier value: it must be exactly 'LOW', 'MEDIUM', or 'HIGH' (no surrounding whitespace). If not: raise DataIntegrityError with message "Invalid risk tier value".
- Validate each returned risk factor code against the allowed set: HIGH_TRANSACTION_VOLUME, MULTIPLE_JURISDICTIONS, ADVERSE_MEDIA_MATCH, PEP_ASSOCIATION, UNUSUAL_ACCOUNT_ACTIVITY. If any code is not in this set: raise DataIntegrityError with message "Invalid risk factor code".
- Return a dict with exactly these keys: customer_id (str), risk_tier (str), risk_factors (list of dicts, each with keys code and description).
- Do not add any HTTP logic, FastAPI imports, or logging beyond what already exists in the file.
- Do not modify any other files.
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Call `get_customer` with a seeded LOW-tier ID with no factors | Returns dict with risk_tier='LOW', risk_factors=[] |
| TC-2 | Call `get_customer` with a seeded HIGH-tier ID | Returns dict with risk_tier='HIGH', risk_factors list non-empty; all factor codes in allowed set |
| TC-3 | Call `get_customer` with a non-existent ID | Raises CustomerNotFoundError |
| TC-4 | Seed a record with a trailing-space tier value ('LOW ') directly in DB; call get_customer | Raises DataIntegrityError |
| TC-5 | Seed a factor with an unlisted code directly in DB; call get_customer | Raises DataIntegrityError |
| TC-6 | Inspect SQL in get_customer | All cursor.execute calls use %s placeholders and a params tuple — no f-strings or concatenation |
| TC-7 | Call `get_customer` for each seeded customer | customer_id in response matches the queried ID; factor count matches DB |

**Verification Command:**
```bash
docker compose exec api python3 -c "
from db import get_customer, CustomerNotFoundError, DataIntegrityError

result = get_customer('CUST-0001')
assert result['risk_tier'] in ('LOW','MEDIUM','HIGH'), 'Invalid tier'
assert isinstance(result['risk_factors'], list), 'risk_factors not list'
print(f'PASS: {result[\"customer_id\"]} tier={result[\"risk_tier\"]} factors={len(result[\"risk_factors\"])}')

try:
    get_customer('CUST-9999')
    print('FAIL: expected CustomerNotFoundError')
except CustomerNotFoundError:
    print('PASS: CustomerNotFoundError raised')
"
```

**Invariant Flag:** INV-01 (DB source of truth and completeness), INV-02 (existence mapping), INV-10 (parameterised SQL), INV-12 (tier re-validation on read), INV-13 (code validation on read), INV-14 (referential integrity — query associates factors to correct customer), INV-15 (single-record lookup — multi-row handled as DataIntegrityError). Code review: inspect every cursor.execute call — confirm %s placeholders and params tuple used; no f-strings or string concatenation anywhere in the function.

---

## Session 3 — API Layer

**Session Goal:** A running FastAPI application with the `/health` endpoint, authenticated `/api/customer/{customer_id}` endpoint, input validation, and correct error responses for all defined cases. Verified against a live stack with real HTTP requests.

**Integration Check:**
```bash
docker compose up -d && sleep 5 && \
  curl -sf http://localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d=={'status':'ok'}, d; print('PASS: /health')" && \
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/customer/CUST-0001) && \
  [ "$STATUS" = "401" ] && echo "PASS: 401 without key" && \
  curl -sf -H "X-API-Key: $API_KEY" http://localhost:8000/api/customer/CUST-0001 | \
    python3 -c "import sys,json; d=json.load(sys.stdin); assert 'risk_tier' in d and 'risk_factors' in d; print('PASS: valid lookup')"
```
_This verifies that auth, health, and data retrieval work together on the running stack — not confirmed by individual task commands._

---

### Task 3.1 — FastAPI Application Shell and Health Endpoint

**Description:** Write the main FastAPI application in `api/main.py` with app initialisation, startup DB connection verification (with retry), and the `/health` endpoint. No protected routes yet. Output: a running FastAPI app with `/health` returning `{"status": "ok"}`.

**CC Prompt:**
```
Write api/main.py for the Customer Risk API.

Requirements:
- Create a FastAPI app instance.
- On startup (use @app.on_event("startup") or lifespan context): call get_connection() from db.py to verify DB connectivity. If get_connection() raises after its retry loop, log a human-readable error message and exit with sys.exit(1). During the retry window, the app must be running but any request to protected routes must return 503 (handled in a later task — for now, allow the startup to block).
- Implement GET /health:
  - Returns HTTP 200 with body {"status": "ok"}.
  - Requires no authentication.
  - Must not call get_connection() or any DB function.
  - Must not share any code path with risk data retrieval.
- Load the API_KEY from environment variable API_KEY at module startup into a module-level variable.
- Do not implement any /api/* routes yet.
- Do not create any other files.
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | GET /health with no auth header | HTTP 200, body exactly `{"status": "ok"}` |
| TC-2 | GET /health when DB is unavailable | HTTP 200 (health is process liveness, not DB health) |
| TC-3 | Inspect /health response headers | No API key, DB credentials, or internal config values in headers |
| TC-4 | API_KEY loaded at module startup | `from main import API_KEY; assert len(API_KEY) > 0` |
| TC-5 | Stack starts without manual intervention | `docker compose up -d` and both containers reach running state |

**Verification Command:**
```bash
docker compose up -d && sleep 5 && \
  BODY=$(curl -s http://localhost:8000/health) && \
  python3 -c "import json; d=json.loads('$BODY'); assert d == {'status':'ok'}, d; print('PASS: /health correct')"
```

**Invariant Flag:** INV-17 (API key loaded at startup), INV-20 (startup failure behaviour), INV-21 (health endpoint behaviour — no auth, no DB path, correct body). Code review: confirm /health does not import or call any DB function; confirm no auth dependency; confirm API_KEY loaded at module level from environment.

---

### Task 3.2 — Authentication Middleware

**Description:** Add the API key authentication dependency to `api/main.py`. This is a FastAPI dependency function that checks the `X-API-Key` header using `hmac.compare_digest` and returns HTTP 401 if the key is missing or invalid. Output: a reusable `verify_api_key` dependency, not yet wired to any route.

**CC Prompt:**
```
Add API key authentication to api/main.py.

Requirements:
- Implement a FastAPI dependency function named verify_api_key(x_api_key: str = Header(None)).
- The function must:
  - Return HTTP 401 if x_api_key is None or empty.
  - Compare x_api_key to the module-level API_KEY variable using hmac.compare_digest only. No == operator, no != operator, no `is` comparison anywhere in the auth code path.
  - Return HTTP 401 if the comparison fails.
  - Return nothing (None) on success — it is a guard, not a data provider.
- The 401 response body must be: {"code": "UNAUTHORIZED", "message": "Invalid or missing API key"}.
- Do not wire this dependency to any route yet — that happens in Task 3.3.
- Do not accept the API key via query parameter, request body, or any mechanism other than the X-API-Key header.
- Do not modify any other files.
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Call verify_api_key with no header | HTTP 401, body `{"code":"UNAUTHORIZED","message":"Invalid or missing API key"}` |
| TC-2 | Call verify_api_key with wrong key | HTTP 401 (same body) |
| TC-3 | Call verify_api_key with correct key | Returns None (no exception) |
| TC-4 | Pass correct key as query param `?x_api_key=...` | HTTP 401 — query param not accepted |
| TC-5 | Inspect auth code | No `==` or `!=` or `is` operator used on key value; hmac.compare_digest used |

**Verification Command:**
```bash
docker compose exec api python3 -c "
import hmac, inspect
from main import verify_api_key
src = inspect.getsource(verify_api_key)
assert 'hmac.compare_digest' in src, 'hmac.compare_digest not found'
assert ' == ' not in src, 'plain == found in auth path'
print('PASS: timing-safe comparison confirmed')
"
```

**Invariant Flag:** INV-05 (auth enforcement — header only), INV-06 (key non-exposure), INV-16 (timing-safe comparison). Code review: read every line of verify_api_key; confirm no equality operator on key value; confirm no query parameter path; confirm 401 body matches approved error structure.

---

### Task 3.3 — Customer Lookup Endpoint

**Description:** Implement `GET /api/customer/{customer_id}` in `api/main.py`. This route applies the `verify_api_key` dependency, validates the customer ID format, calls `get_customer`, and maps all exception types to correct HTTP responses. All error responses must use the approved structure. Output: a working, authenticated endpoint.

**CC Prompt:**
```
Implement the customer lookup endpoint in api/main.py.

Requirements:
- Route: GET /api/customer/{customer_id}
- Apply the verify_api_key dependency to this route.
- Input validation (before any DB call):
  - Enforce a maximum input length of 50 characters. If exceeded: return HTTP 400.
  - Validate customer_id against the regex pattern ^CUST-\d{4}$. If it does not match: return HTTP 400.
- If validation passes, call get_customer(customer_id) from db.py.
- Map exceptions to HTTP responses:
  - CustomerNotFoundError → HTTP 404, body: {"code": "NOT_FOUND", "message": "Customer not found"}
  - DataIntegrityError → HTTP 500, body: {"code": "INTERNAL_ERROR", "message": "An internal error occurred"}
  - Any other exception (including psycopg2 errors, timeouts) → HTTP 500, same body as above
- On success: return HTTP 200 with the dict returned by get_customer as the JSON body.
- All error response bodies must contain exactly two keys: `code` and `message`. No stack traces, SQL text, connection strings, internal hostnames, ports, schema names, or configuration values may appear in any error response.
- Do not add any other routes.
- Do not modify db.py or any other file.
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | GET /api/customer/CUST-0001 with valid key | HTTP 200; response matches INV-04 schema |
| TC-2 | GET /api/customer/CUST-9999 with valid key (non-existent) | HTTP 404, `{"code":"NOT_FOUND","message":"Customer not found"}` |
| TC-3 | GET /api/customer/CUST-0001 with no key | HTTP 401 |
| TC-4 | GET /api/customer/CUST-0001 with wrong key | HTTP 401 |
| TC-5 | GET /api/customer/INVALID with valid key | HTTP 400 (fails regex) |
| TC-6 | GET /api/customer/ with 51-char string + valid key | HTTP 400 (exceeds max length) |
| TC-7 | GET /api/customer/CUST-0001?X-API-Key=... (key in query param) | HTTP 401 |
| TC-8 | Trigger DB timeout via pg_sleep with valid key | HTTP 503, sanitised body only |
| TC-9 | Inspect 500 response body | No stack trace, SQL, hostname, or internal config visible |
| TC-10 | customer_id in response body is a string type | `type(response["customer_id"]) == str` |
| TC-11 | LOW tier customer with no factors | HTTP 200; risk_factors=[] in response |
| TC-12 | SQL injection payload as customer_id | HTTP 400 (rejected by validation before DB) |

**Verification Command:**
```bash
docker compose up -d && sleep 5 && \
  curl -sf -H "X-API-Key: $API_KEY" http://localhost:8000/api/customer/CUST-0001 | \
    python3 -c "
import sys,json
d=json.load(sys.stdin)
assert isinstance(d['customer_id'], str), 'customer_id not string'
assert d['risk_tier'] in ('LOW','MEDIUM','HIGH'), 'invalid tier'
assert isinstance(d['risk_factors'], list), 'risk_factors not list'
print('PASS: 200 response valid')
" && \
  S=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/customer/CUST-0001) && \
  [ "$S" = "401" ] && echo "PASS: 401 without key" && \
  S=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" http://localhost:8000/api/customer/CUST-9999) && \
  [ "$S" = "404" ] && echo "PASS: 404 for unknown ID" && \
  S=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" http://localhost:8000/api/customer/INVALID) && \
  [ "$S" = "400" ] && echo "PASS: 400 for invalid format"
```

**Invariant Flag:** INV-01, INV-02, INV-04 (schema), INV-05 (auth enforcement), INV-06 (key non-exposure), INV-07 (error leakage), INV-10 (parameterised SQL — through db.py), INV-11 (ID validation), INV-12 (tier restriction), INV-13 (code set). Code review: confirm validation precedes DB call; confirm all exception paths return only approved error structure; confirm no internal values in any error body.

---

## Session 4 — UI and Integration

**Session Goal:** A browser-accessible single HTML page served by the FastAPI container, with a proxy route that allows the UI to query risk data without exposing the API key to the browser. Full end-to-end stack verified including the UI rendering correct data and not transforming it.

**Integration Check:**
```bash
docker compose up -d && sleep 5 && \
  curl -sf http://localhost:8000/ | grep -q '<input' && echo "PASS: UI served with input element" && \
  curl -sf "http://localhost:8000/lookup?customer_id=CUST-0001" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); assert 'risk_tier' in d; print('PASS: proxy route works')" && \
  COUNT=$(docker compose ps -q | wc -l | tr -d ' ') && \
  [ "$COUNT" = "2" ] && echo "PASS: exactly two containers"
```
_This verifies that the UI is served from the FastAPI container (not separately), the proxy route returns data, and the two-container constraint still holds._

---

### Task 4.1 — Proxy Route and Static UI

**Description:** Add the `/lookup` proxy route to `api/main.py` (unauthenticated from the browser's perspective — the route calls `get_customer` directly), add a `GET /` route that serves `ui/index.html`, and write the static HTML+JS UI. Output: a browsable interface at `http://localhost:8000/`.

**CC Prompt:**
```
Add the UI proxy route and static file serving to api/main.py, and write the UI file.

Requirements for api/main.py:
- Add a GET / route that returns ui/index.html as an HTMLResponse. Do not use a separate web server or Nginx.
- Implement GET /lookup?customer_id={customer_id}:
  - This route requires NO X-API-Key header from the caller (it is browser-facing).
  - It must NOT perform its own auth check. Auth lives on /api/* routes only.
  - It calls get_customer(customer_id) directly — it must NOT call the /api/customer route or issue an HTTP request to itself.
  - It applies the same input validation as Task 3.3: max length 50 chars, regex ^CUST-\d{4}$.
  - It maps exceptions to the same HTTP responses as Task 3.3.
  - On success: returns the dict from get_customer as JSON.
  - The API_KEY variable must not be referenced anywhere in this route's code.

Requirements for ui/index.html (create this file):
- Plain HTML + vanilla JavaScript. No frontend framework. No external CDN scripts.
- A text input labelled "Customer ID" and a button labelled "Look Up".
- On button click: fetch /lookup?customer_id={value} and display the result.
- Display fields: customer_id, risk_tier, and all risk_factors (code and description for each).
- Display error messages (404, 400, 500) from the response body without modification.
- Must NOT transform, recompute, or suppress any field returned by the API.
- Must NOT hardcode or reference the API key in any way.

Do not modify db.py. Do not modify the /api/customer route. Do not create any other files.
```

**Test Cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | GET http://localhost:8000/ | HTTP 200; HTML page with input and button |
| TC-2 | GET /lookup?customer_id=CUST-0001 | HTTP 200; JSON identical to /api/customer/CUST-0001 response |
| TC-3 | GET /lookup?customer_id=CUST-9999 | HTTP 404 with sanitised body |
| TC-4 | GET /lookup?customer_id=INVALID | HTTP 400 |
| TC-5 | Browser: enter CUST-0001 and click Look Up | customer_id, risk_tier, and risk_factors all displayed |
| TC-6 | Browser: enter ID for LOW tier with no factors | risk_factors displayed as empty — not hidden |
| TC-7 | Inspect ui/index.html source | No API key string; no external script src attributes |
| TC-8 | Inspect /lookup route code in main.py | API_KEY not referenced; no HTTP call to /api/customer |
| TC-9 | Browser network tab for /lookup request | X-API-Key header not sent |
| TC-10 | Compare /lookup and /api/customer responses for same ID | JSON responses are identical |

**Verification Command:**
```bash
docker compose up -d && sleep 5 && \
  curl -sf http://localhost:8000/ | grep -q 'Look Up' && echo "PASS: UI served" && \
  API_RESP=$(curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/customer/CUST-0001) && \
  PROXY_RESP=$(curl -s "http://localhost:8000/lookup?customer_id=CUST-0001") && \
  python3 -c "
import json, sys
api = json.loads('''$API_RESP''')
proxy = json.loads('''$PROXY_RESP''')
assert api == proxy, f'Mismatch: {api} vs {proxy}'
print('PASS: proxy and API responses identical')
" && \
  curl -s http://localhost:8000/ | grep -vq "$API_KEY" && echo "PASS: API key not in UI source"
```

**Invariant Flag:** INV-06 (key non-exposure — UI must not contain or transmit key), INV-09 (UI non-transformation), INV-18 (proxy route auth boundary — does not call /api/* route; API_KEY not referenced), INV-19 (two-container constraint — UI served by FastAPI container). Code review: confirm /lookup does not reference API_KEY; confirm /lookup calls get_customer directly and does not issue HTTP to /api/customer; confirm ui/index.html contains no API_KEY string; confirm no transformation logic in JS.

---

## Appendix — Invariant Coverage Map

| Invariant | Session | Task(s) |
|---|---|---|
| INV-01 | 2 | 2.2 |
| INV-02 | 2, 3 | 2.2, 3.3 |
| INV-03 | 1, 2 | 1.2, 2.1 |
| INV-04 | 3 | 3.3 |
| INV-05 | 3, 4 | 3.2, 3.3, 4.1 |
| INV-06 | 3, 4 | 3.2, 4.1 |
| INV-07 | 3 | 3.3 |
| INV-08 | 1 | 1.3 |
| INV-09 | 4 | 4.1 |
| INV-10 | 2 | 2.2 |
| INV-11 | 3 | 3.3 |
| INV-12 | 1, 2 | 1.2, 2.2 |
| INV-13 | 1, 2 | 1.2, 2.2 |
| INV-14 | 1 | 1.2 |
| INV-15 | 2 | 2.2 |
| INV-16 | 3 | 3.2 |
| INV-17 | 3 | 3.1 |
| INV-18 | 4 | 4.1 |
| INV-19 | 1, 4 | 1.3, 4.1 |
| INV-20 | 2 | 2.1 |
| INV-21 | 3 | 3.1 |
| INV-22 | 2 | 2.1 |
| INV-23 | 1 | 1.2 |

---

_Last updated: 2026-03-17 · Status: Draft — ready for Phase 4 Design Gate_
