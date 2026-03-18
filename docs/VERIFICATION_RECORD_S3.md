# Verification Record — Session 3: API Layer
**Customer Risk API · Version 1.0**
_Date: 2026-03-18 · Branch: session/3-api-layer_

> **Instructions:** Complete Prediction Statement before executing each case. Record Result after execution. Mark one verdict checkbox per case.
> Do not pre-populate Prediction Statements.

---

## Task 3.1 — FastAPI Application Shell and Health Endpoint

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | GET /health with no auth header | HTTP 200, body exactly `{"status": "ok"}` | `health()` has no auth dependency and returns `{"status": "ok"}`; FastAPI serialises the dict to JSON with HTTP 200 | HTTP 200; body `{"status":"ok"}` confirmed | [x] | [ ] |
| TC-2 | GET /health when DB is unavailable | HTTP 200 (health is process liveness, not DB health) | `health()` contains no import or call to any DB function; cannot fail due to DB state | `docker compose stop db` → GET /health → HTTP 200; DB restarted; health unaffected by DB state | [x] | [ ] |
| TC-3 | Inspect /health response headers | No API key, DB credentials, or internal config values in headers | No `response.headers` assignments anywhere in `main.py`; FastAPI default headers contain no application secrets | Response headers: `date`, `server: uvicorn`, `content-length`, `content-type` only — no API key, credentials, or config values present | [x] | [ ] |
| TC-4 | API_KEY loaded at module startup | `from main import API_KEY; assert len(API_KEY) > 0` | `API_KEY = os.environ["API_KEY"]` executes at import time; raises `KeyError` if absent; non-empty when set | Static review confirmed: `API_KEY = os.environ["API_KEY"]` at line 10; import assertion passes when env var is set | [x] | [ ] |
| TC-5 | Stack starts without manual intervention | `docker compose up -d` and both containers reach running state | Both containers were healthy after Session 1; no new `requirements.txt` changes; stack config updated (INV-08 fix) | `docker compose ps` confirms `api: running`, `db: running` | [x] | [ ] |

---

## Task 3.2 — Authentication Middleware

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | Call verify_api_key with no header | HTTP 401, body `{"code":"UNAUTHORIZED","message":"Invalid or missing API key"}` | `x_api_key` is `None`; `not None` is `True`; `_AuthError` raised; handler returns 401 with exact body | HTTP 401; body `{"code":"UNAUTHORIZED","message":"Invalid or missing API key"}` confirmed | [x] | [ ] |
| TC-2 | Call verify_api_key with wrong key | HTTP 401 (same body) | `hmac.compare_digest(wrong, correct)` returns `False`; `not False` is `True`; `_AuthError` raised | `-H "X-API-Key: WRONGKEY"` → HTTP 401 confirmed | [x] | [ ] |
| TC-3 | Call verify_api_key with correct key | Returns None (no exception) | Both guard conditions evaluate `False`; function returns `None` implicitly | Correct key → HTTP 200 on `/api/customer/CUST-0001`; dependency did not block the request — confirms `None` returned with no exception | [x] | [ ] |
| TC-4 | Pass correct key as query param `?x_api_key=...` | HTTP 401 — query param not accepted | `Header(None)` only reads from request headers; query param does not populate `x_api_key` | `?X-API-Key=CUSTOMER_RISK_API_KEY` → HTTP 401 confirmed | [x] | [ ] |
| TC-5 | Inspect auth code | No `==` or `!=` or `is` operator used on key value; hmac.compare_digest used | `hmac.compare_digest` at line 42; only boolean coercion (`not x_api_key`) for None/empty check | Static review confirmed: `hmac.compare_digest(x_api_key, API_KEY)` at line 42; no `==`, `!=`, `is` on the key value | [x] | [ ] |

---

## Task 3.3 — Customer Lookup Endpoint

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | GET /api/customer/CUST-0001 with valid key | HTTP 200; response matches INV-04 schema | `get_customer('CUST-0001')` returns dict with `customer_id`, `risk_tier`, `risk_factors`; wrapped in `JSONResponse(200)` | HTTP 200; `{"customer_id":"CUST-0001","risk_tier":"LOW","risk_factors":[]}` — all three required keys present | [x] | [ ] |
| TC-2 | GET /api/customer/CUST-9999 with valid key (non-existent) | HTTP 404, `{"code":"NOT_FOUND","message":"Customer not found"}` | `CustomerNotFoundError` raised by `get_customer`; caught; returns 404 with exact body | HTTP 404; body `{"code":"NOT_FOUND","message":"Customer not found"}` confirmed | [x] | [ ] |
| TC-3 | GET /api/customer/CUST-0001 with no key | HTTP 401 | `verify_api_key` dependency fires before route body; `x_api_key` is `None`; `_AuthError` raised | HTTP 401 confirmed | [x] | [ ] |
| TC-4 | GET /api/customer/CUST-0001 with wrong key | HTTP 401 | `hmac.compare_digest` fails; `_AuthError` raised | HTTP 401 confirmed | [x] | [ ] |
| TC-5 | GET /api/customer/INVALID with valid key | HTTP 400 (fails regex) | `_CUSTOMER_ID_RE.match('INVALID')` returns `None`; 400 returned | HTTP 400 confirmed | [x] | [ ] |
| TC-6 | GET /api/customer/ with 51-char string + valid key | HTTP 400 (exceeds max length) | `len(customer_id) > 50` → `True`; 400 returned before regex check | 55-char string → HTTP 400 confirmed | [x] | [ ] |
| TC-7 | GET /api/customer/CUST-0001?X-API-Key=... (key in query param) | HTTP 401 | `Header(None)` reads only from request headers; `x_api_key` is `None`; `_AuthError` raised | `?X-API-Key=CUSTOMER_RISK_API_KEY` (no header) → HTTP 401 confirmed | [x] | [ ] |
| TC-8 | Trigger DB timeout via pg_sleep with valid key | HTTP 503, sanitised body only | **KNOWN GAP — EXPECTED FAIL:** `except Exception:` returns HTTP 500 (`_INTERNAL_ERROR`). INV-22 requires 503 for `statement_timeout` exceeded. `psycopg2.errors.QueryCanceled` is not caught explicitly. | **NOT EXECUTED** — gap must be resolved before this case can pass. `psycopg2.errors.QueryCanceled` must be caught and mapped to 503. Flagged for remediation. | [ ] | [x] |
| TC-9 | Inspect 500 response body | No stack trace, SQL, hostname, or internal config visible | `except Exception: return _INTERNAL_ERROR` — body has exactly two keys; exception object never accessed | Static review confirmed: bare `except Exception:` with no `as exc`; `_INTERNAL_ERROR` = `{"code":"INTERNAL_ERROR","message":"An internal error occurred"}` — no internal details reachable | [x] | [ ] |
| TC-10 | customer_id in response body is a string type | `type(response["customer_id"]) == str` | `get_customer` applies `str(db_customer_id)`; `customer_id` column is `VARCHAR` | `type(d['customer_id']).__name__` → `str` confirmed | [x] | [ ] |
| TC-11 | LOW tier customer with no factors | HTTP 200; risk_factors=[] in response | `get_customer('CUST-0001')` returns `risk_factors=[]` for LOW tier with no `risk_factor` rows | HTTP 200; `"risk_factors":[]` confirmed for CUST-0001 | [x] | [ ] |
| TC-12 | SQL injection payload as customer_id | HTTP 400 (rejected by validation before DB) | Any SQL injection string will not match `^CUST-\d{4}$`; 400 returned before `get_customer` is called | `UNION-SELECT` payload → HTTP 400 confirmed; regex rejects before any DB call | [x] | [ ] |

---

## Session Integration Check

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| INT-1 | GET /health (no auth) | HTTP 200, body `{"status":"ok"}` | No auth dependency on `/health`; returns `{"status":"ok"}` | HTTP 200; body `{"status":"ok"}` confirmed | [x] | [ ] |
| INT-2 | GET /api/customer/CUST-0001 with no key | HTTP 401 | `verify_api_key` dependency fires; no `X-API-Key` header; `_AuthError` raised | HTTP 401 confirmed | [x] | [ ] |
| INT-3 | GET /api/customer/CUST-0001 with valid key | HTTP 200; response contains `risk_tier` and `risk_factors` | Validation passes; `get_customer` returns dict; HTTP 200 with full JSON body | HTTP 200; `risk_tier` and `risk_factors` present; `risk_factors=[]` for LOW tier CUST-0001 | [x] | [ ] |
