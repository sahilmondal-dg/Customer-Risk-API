# Claude.md — v1.0 · FROZEN · 2026-03-17

---

## 1. System Intent

The Customer Risk API is a read-only internal service that accepts a `customer_id`, looks up the pre-assessed risk profile in a Postgres database, and returns the risk tier and contributing factors as structured JSON. It does not compute risk, manage users, or perform any write operations. Success means operations staff can query risk status reliably through a browser UI or HTTP client without direct database access, with every request authenticated and every response schema-stable.

---

## 2. Hard Invariants

INVARIANT: The API response values for `customer_id`, `risk_tier`, and `risk_factors` must exactly match the values stored in Postgres for the queried customer, including all risk factor rows — not a subset. This is never negotiable.

INVARIANT: A request for an existing `customer_id` must return HTTP 200 with a complete valid response. A request for a non-existent `customer_id` must return HTTP 404. A structurally incomplete record must never produce a 200. This is never negotiable.

INVARIANT: The API must never modify database state. No INSERT, UPDATE, DELETE, DDL, or SELECT FOR UPDATE may be issued. The Postgres role used by the API must be granted SELECT privilege only — enforced at the credential level, not only in application code. This is never negotiable.

INVARIANT: Every successful API response must conform to exactly this structure: `{"customer_id": "string", "risk_tier": "LOW|MEDIUM|HIGH", "risk_factors": [{"code": "string", "description": "string"}]}`. All keys must be present. `risk_factors` may be empty only for LOW tier customers. `customer_id` must serialise as a string type. This is never negotiable.

INVARIANT: Every request to `/api/*` endpoints must require a valid API key in the `X-API-Key` header. Requests without a valid key must return HTTP 401. The key must not be accepted via query parameter, request body, or any other mechanism. The `/health` endpoint is explicitly exempt. This is never negotiable.

INVARIANT: The API key must never appear in responses, error messages, application logs, access logs, UI source or rendered output, stack traces, or HTTP response headers. It must only be accepted via a named request header, never via query string. This is never negotiable.

INVARIANT: Database or server exceptions must never expose stack traces, SQL queries, connection strings, internal hostnames, ports, schema names, or configuration values. All error responses must contain exactly two keys — `code` and `message` — drawn from a predefined allowlist of generic messages. This is never negotiable.

INVARIANT: The system must operate entirely locally. No application code may call external APIs, third-party services, or remote databases. The FastAPI container's outbound network access must be restricted to the internal Docker Compose network only. This is never negotiable.

INVARIANT: The browser UI must render values exactly as returned by the API. It must not recompute risk tier, remap factor codes, or alter descriptions. It must display all fields including an empty `risk_factors` array. No computed value may replace an API-returned value in rendered output. This is never negotiable.

INVARIANT: All SQL queries must use parameterised statements. `cursor.execute()` must always be called with a query string using only `%s` placeholders and a separate parameters tuple. String concatenation and f-strings in SQL construction are forbidden at all call sites. This is never negotiable.

INVARIANT: The `customer_id` input must be validated against `^CUST-\d{4}$` before any database interaction. Maximum input length of 50 characters must be enforced before pattern matching. Inputs not matching must return HTTP 400. Empty string must return 400, not 404. This is never negotiable.

INVARIANT: The `risk_tier` field must only contain exactly `LOW`, `MEDIUM`, or `HIGH` in uppercase with no surrounding whitespace. This must be enforced by DB CHECK constraint and re-validated at the API serialisation layer. A non-conforming value retrieved from DB must return HTTP 500 with a sanitised error message. This is never negotiable.

INVARIANT: The `code` field in each risk factor must be one of: `HIGH_TRANSACTION_VOLUME`, `MULTIPLE_JURISDICTIONS`, `ADVERSE_MEDIA_MATCH`, `PEP_ASSOCIATION`, `UNUSUAL_ACCOUNT_ACTIVITY`. Any code not in this set must not be passed through — treat as a data integrity error. This is never negotiable.

INVARIANT: Every `risk_factor` row must have a corresponding `customer` row. The DB schema must enforce this via a foreign key constraint with ON DELETE CASCADE. The query assembling the response must verify all returned factors belong to the queried customer ID. This is never negotiable.

INVARIANT: A customer ID lookup must return exactly one record or zero. If more than one row is returned for a given `customer_id`, the API must return HTTP 500 with a sanitised error message — it must not silently return the first result. The `customer` table must have a PRIMARY KEY or UNIQUE constraint on `customer_id`. This is never negotiable.

INVARIANT: API key validation must use `hmac.compare_digest` for all key comparisons. Plain equality operators (`==`, `!=`, `is`) must not be used for API key comparison anywhere in the auth code path. This is never negotiable.

INVARIANT: The API key must be loaded from the `.env` file at process startup. A process restart must re-read the key from the environment — no stale key may survive a restart. This is never negotiable.

INVARIANT: The internal data function shared between the proxy route and the API route must be the only application-layer entry point to the risk data. The proxy route must not perform its own auth check. No route other than defined `/api/*` routes may return risk data unless it calls the internal function and that route is a defined `/api/*` endpoint. This is never negotiable.

INVARIANT: The Docker Compose configuration must define exactly two services: the FastAPI application container and the Postgres database container. All application concerns — the protected API endpoint, the browser-facing proxy route, and static HTML serving — must be handled by the single FastAPI container. This is never negotiable.

INVARIANT: After exhausting the retry loop (10 attempts, 1-second intervals), the FastAPI process must exit with a non-zero exit code and emit a human-readable error message identifying DB unavailability. During the retry window, incoming HTTP requests must receive HTTP 503. No connection details may appear in any response during this window. This is never negotiable.

INVARIANT: The `/health` endpoint must return HTTP 200 with body `{"status": "ok"}`. It must not return business data, require authentication, share any code path with risk data retrieval, or depend on DB connectivity — it is a process liveness signal only. This is never negotiable.

INVARIANT: All database queries must be subject to a 5-second timeout enforced at the DB level via `statement_timeout`. A query exceeding this limit must return HTTP 503 with a sanitised error message. The timeout value must be the named constant `QUERY_TIMEOUT_SECONDS`. This is never negotiable.

INVARIANT: On a fresh volume, the database must contain at least one customer per tier (LOW, MEDIUM, HIGH). LOW tier must include at least one record with zero risk factors. MEDIUM and HIGH must each have at least one record with at least one risk factor. All five defined risk factor codes must appear in the seed data at least once. This is never negotiable.

---

## 3. Scope Boundary

**Files CC may create or modify:**

```
docker-compose.yml
.env.example
api/Dockerfile
api/requirements.txt
api/main.py
api/db.py
ui/index.html
db/01_schema.sql
db/02_seed.sql
```

**CC must not:**
- Create any file not listed above
- Add a third service to `docker-compose.yml`
- Use an ORM — psycopg2 only, direct SQL
- Add any write endpoint (POST, PUT, PATCH, DELETE)
- Import or call any external HTTP library or third-party service from application code
- Use f-strings or string concatenation in any SQL query
- Add external network access to the `api` container
- Use any frontend framework or external CDN scripts in `ui/index.html`
- Reference `API_KEY` anywhere in the `/lookup` proxy route or UI
- Add auth logic to the `/lookup` route or the internal data function
- Implement any business logic that computes risk scores

**Conflict rule:** If a task prompt conflicts with any invariant above, the invariant wins. Flag the conflict immediately — never resolve it silently by proceeding.

---

## 4. Fixed Stack

| Component | Technology / Version |
|---|---|
| Orchestration | Docker Compose (v2 syntax) |
| Database | `postgres:15` (official Docker image) |
| API runtime | Python 3.11 |
| API framework | FastAPI (latest compatible) |
| DB driver | `psycopg2-binary` — no ORM |
| ASGI server | `uvicorn` |
| UI | Plain HTML + vanilla JavaScript — no framework, no external CDN |

**Environment variables (all sourced from `.env`):**

| Variable | Used by |
|---|---|
| `POSTGRES_USER` | db service, api service |
| `POSTGRES_PASSWORD` | db service, api service |
| `POSTGRES_DB` | db service, api service |
| `POSTGRES_HOST` | api service (`db` — Docker Compose service name) |
| `POSTGRES_PORT` | api service (`5432`) |
| `API_KEY` | api service |

**Named constants (must not be inline literals):**

| Constant | Value | Location |
|---|---|---|
| `QUERY_TIMEOUT_SECONDS` | `5` | `api/db.py` |

**API key header name:** `X-API-Key` (exact casing)

**Customer ID pattern:** `^CUST-\d{4}$` · Max input length: `50` characters

**Allowed risk tiers:** `LOW`, `MEDIUM`, `HIGH`

**Allowed risk factor codes:** `HIGH_TRANSACTION_VOLUME`, `MULTIPLE_JURISDICTIONS`, `ADVERSE_MEDIA_MATCH`, `PEP_ASSOCIATION`, `UNUSUAL_ACCOUNT_ACTIVITY`

**Approved error response structure (only two keys, no others):**
```json
{"code": "ERROR_CODE", "message": "Human-readable message"}
```

**Approved error codes:** `UNAUTHORIZED`, `NOT_FOUND`, `INTERNAL_ERROR`
