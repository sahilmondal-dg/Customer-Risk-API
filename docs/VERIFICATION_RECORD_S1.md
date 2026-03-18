# Verification Record — Session 1: Foundation
**Customer Risk API · Version 1.0**
_Date: 2026-03-18 · Branch: session/1-foundation_

> **Instructions:** Complete Prediction Statement before executing each case. Record Result after execution. Mark one verdict checkbox per case.
> Do not pre-populate Prediction Statements.

---

## Task 1.1 — Repository Scaffold

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | Run `docker compose config --services` | Output contains exactly `api` and `db`, nothing else | | `api` and `db` on separate lines; no other output | [ x ] | [ ] |
| TC-2 | Run `pip install -r api/requirements.txt` in a clean venv | Exit code 0; fastapi, uvicorn, psycopg2-binary installed | | Exit code 0; all three packages installed successfully | [ x ] | [ ] |
| TC-3 | Import `main` from api/main.py in a Python 3.11 interpreter | No ImportError | | No ImportError raised. Note: `API_KEY = os.environ["API_KEY"]` raises KeyError if env var is unset — not an ImportError, so test passes by specification, but requires API_KEY to be set for a clean import. | [ x ] | [ ] |
| TC-4 | Run `docker compose build api` | Exit code 0 | | Exit code 0; image built from python:3.11-slim | [ x ] | [ ] |

---

## Task 1.2 — Database Schema and Seed Data

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | Run schema against a fresh Postgres instance | Both tables created; no errors | | `customer` and `risk_factor` tables created; no errors | [ x ] | [ ] |
| TC-2 | Run seed after schema | All rows inserted; no errors | | 6 customer rows, 7 risk_factor rows inserted; no errors | [ x ] | [ ] |
| TC-3 | Run seed a second time (idempotency) | No errors; row counts unchanged | | 0 rows inserted on second run (ON CONFLICT DO NOTHING); counts unchanged | [ x ] | [ ] |
| TC-4 | Attempt to insert a `risk_tier` value of `'PENDING'` directly | DB rejects with constraint violation | | `ERROR: new row for relation "customer" violates check constraint "chk_customer_risk_tier"` | [ x ] | [ ] |
| TC-5 | Attempt to insert a `risk_factor.code` of `'UNKNOWN_CODE'` directly | DB rejects with constraint violation | | `ERROR: new row for relation "risk_factor" violates check constraint "chk_risk_factor_code"` | [ x ] | [ ] |
| TC-6 | Attempt to insert a `risk_factor` with a non-existent `customer_id` | DB rejects with FK violation | | `ERROR: insert or update on table "risk_factor" violates foreign key constraint "fk_risk_factor_customer"` | [ x ] | [ ] |
| TC-7 | Query `SELECT COUNT(*) FROM customer` | ≥ 6 rows | | `count = 6` | [ x ] | [ ] |
| TC-8 | All five codes appear in seed data | `SELECT DISTINCT code FROM risk_factor` returns all five | | Returns: `UNUSUAL_ACCOUNT_ACTIVITY`, `HIGH_TRANSACTION_VOLUME`, `MULTIPLE_JURISDICTIONS`, `ADVERSE_MEDIA_MATCH`, `PEP_ASSOCIATION` | [ x ] | [ ] |
| TC-9 | At least one LOW customer has zero factors | Query confirms empty factor set for that customer | | `CUST-0001` (LOW) has zero rows in `risk_factor` | [ x ] | [ ] |

---

## Task 1.3 — Docker Compose Wiring and Healthcheck

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | `docker compose up -d` on fresh volume | Both containers reach 'running' state; no restart loops | | Both containers reached `running` state; db healthcheck passed; api started after db healthy | [ x ] | [ ] |
| TC-2 | `docker compose ps` | Exactly two services listed | | Two services listed: `api`, `db` | [ x ] | [ ] |
| TC-3 | `docker compose logs db` | No startup errors; "database system is ready to accept connections" present | | `database system is ready to accept connections` present; schema and seed scripts executed without error | [ x ] | [ ] |
| TC-4 | `docker compose logs api` | FastAPI placeholder starts without error | | uvicorn started on 0.0.0.0:8000; no startup errors | [ x ] | [ ] |
| TC-5 | Inspect network config | api container has no external network access | | `app-net` defined with `internal: true`; `api` attached to `app-net` only; no external network reachable | [ x ] | [ ] |

---

## Session Integration Check

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| INT-1 | `docker compose up -d` and inspect running services via `docker compose ps --format json` | Exactly two services (`api`, `db`), both in `running` state | | Two services returned; both `State: running`; two-container constraint confirmed | [ x ] | [ ] |
| INT-2 | Query `SELECT COUNT(*) FROM customer` and `SELECT COUNT(*) FROM risk_factor` against running db container | Both queries return without error; counts reflect seed data | | `customer` count = 6; `risk_factor` count = 7; seed data loaded on fresh volume | [ x ] | [ ] |
