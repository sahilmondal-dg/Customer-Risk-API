# Verification Record — Session 2: Data Layer
**Customer Risk API · Version 1.0**
_Date: 2026-03-18 · Branch: session/2-data-layer_

> **Instructions:** Complete Prediction Statement before executing each case. Record Result after execution. Mark one verdict checkbox per case.
> Do not pre-populate Prediction Statements.

---

## Task 2.1 — Database Connection and Retry Module

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | Call `get_connection()` with valid env vars pointing to running Postgres | Returns a live psycopg2 connection; no exception | Returns a psycopg2 connection object; no exception raised | Connection returned; confirmed live by executing `SHOW statement_timeout` against it | [x] | [ ] |
| TC-2 | Call `get_connection()` with unreachable host | After 10 attempts (~10 seconds), raises RuntimeError with "Database unavailable" message | 10 stderr lines printed, one per attempt; RuntimeError raised with exact message "Database unavailable after 10 attempts" | 10 human-readable stderr messages printed; `RuntimeError: Database unavailable after 10 attempts` raised after ~10 seconds | [x] | [ ] |
| TC-3 | Inspect connection after `get_connection()` | `SHOW statement_timeout` returns '5000ms' or equivalent | `SHOW statement_timeout` returns `5000ms`; value derives from `QUERY_TIMEOUT_SECONDS * 1000 = 5000` | `statement_timeout: 5000ms` confirmed | [x] | [ ] |
| TC-4 | QUERY_TIMEOUT_SECONDS is a named constant | `from db import QUERY_TIMEOUT_SECONDS; assert QUERY_TIMEOUT_SECONDS == 5` | Import succeeds; assertion passes; value is 5 | `QUERY_TIMEOUT_SECONDS = 5` confirmed at module level (line 7); assertion passes | [x] | [ ] |
| TC-5 | Attempt an INSERT via the returned connection | DB rejects with permission denied (read-only role) | `psycopg2.errors.InsufficientPrivilege` raised; app role has SELECT only | DB rejected INSERT with `permission denied` — read-only role enforced by `01_schema.sql` | [x] | [ ] |

---

## Task 2.2 — Customer Lookup Query

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | Call `get_customer` with a seeded LOW-tier ID with no factors | Returns dict with risk_tier='LOW', risk_factors=[] | `get_customer('CUST-0001')` returns `{'customer_id': 'CUST-0001', 'risk_tier': 'LOW', 'risk_factors': []}` — CUST-0001 confirmed LOW with zero factors in S1 | `customer_id='CUST-0001'`, `risk_tier='LOW'`, `risk_factors=[]`; confirmed via integration check | [x] | [ ] |
| TC-2 | Call `get_customer` with a seeded HIGH-tier ID | Returns dict with risk_tier='HIGH', risk_factors list non-empty; all factor codes in allowed set | Returns dict with risk_tier='HIGH' and at least one factor; all codes in `_ALLOWED_CODES` set | HIGH-tier customer returned with non-empty risk_factors; all codes present in allowed set | [x] | [ ] |
| TC-3 | Call `get_customer` with a non-existent ID | Raises CustomerNotFoundError | `get_customer('CUST-9999')` raises `CustomerNotFoundError`; zero rows returned by query 1 triggers the `len(rows) == 0` branch | `CustomerNotFoundError` raised; confirmed via integration check | [x] | [ ] |
| TC-4 | Seed a record with a trailing-space tier value ('LOW ') directly in DB; call get_customer | Raises DataIntegrityError | — | **NOT EXECUTED** — `01_schema.sql` CHECK constraint on `risk_tier` prevents inserting 'LOW ' via the app role or any normal credentials. Branch confirmed present by static review (line 90–91 of `db.py`); unreachable in a correctly operating stack. | [ ] | [ ] |
| TC-5 | Seed a factor with an unlisted code directly in DB; call get_customer | Raises DataIntegrityError | — | **NOT EXECUTED** — `01_schema.sql` CHECK constraint on `risk_factor.code` prevents inserting an unlisted code. Branch confirmed present by static review (line 102–103 of `db.py`); unreachable in a correctly operating stack. | [ ] | [ ] |
| TC-6 | Inspect SQL in get_customer | All cursor.execute calls use %s placeholders and a params tuple — no f-strings or concatenation | Both `cursor.execute` calls will use `%s` with a `(customer_id,)` tuple; no f-strings anywhere in the function | Static review confirmed: query 1 (`line 76–79`) and query 2 (`line 94–97`) both use `%s` + params tuple; no f-strings or concatenation found | [x] | [ ] |
| TC-7 | Call `get_customer` for each seeded customer | customer_id in response matches the queried ID; factor count matches DB | Each call returns the queried ID in `customer_id`; `str()` cast applied; factor list length matches DB row count for that customer | All six seeded customers returned matching `customer_id`; factor counts matched DB seed data | [x] | [ ] |

---

## Session Integration Check

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| INT-1 | Call `get_customer('CUST-0001')` inside the running api container | Returns dict with `customer_id`, `risk_tier` in ('LOW','MEDIUM','HIGH'), and `risk_factors` as a list | Returns `{'customer_id': 'CUST-0001', 'risk_tier': 'LOW', 'risk_factors': []}` — CUST-0001 is LOW with zero factors per S1 seed record | `PASS: get_customer returns valid structure for CUST-0001`; `customer_id` present, `risk_tier='LOW'`, `risk_factors=[]` | [x] | [ ] |
| INT-2 | Call `get_customer('CUST-9999')` inside the running api container | Raises `CustomerNotFoundError` | Zero rows returned for unknown ID; `CustomerNotFoundError` raised and caught by the integration script | `PASS: CustomerNotFoundError raised for unknown ID` | [x] | [ ] |
