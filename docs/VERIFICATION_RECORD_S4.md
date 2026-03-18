# Verification Record — Session 4: UI and Integration
**Customer Risk API · Version 1.0**
_Date: 2026-03-18 · Branch: session/4-ui-integration_

> **Instructions:** Complete Prediction Statement before executing each case. Record Result after execution. Mark one verdict checkbox per case.
> Do not pre-populate Prediction Statements.

---

## Pre-Session Carry-Over — INV-22 Remediation

Before Task 4.1 begins, the TC-8 gap from Session 3 must be resolved. The `/api/customer/{customer_id}` endpoint's bare `except Exception:` must be split to catch `psycopg2.errors.QueryCanceled` explicitly and return HTTP 503. The `/lookup` route introduced in Task 4.1 must apply the same mapping.

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-8 (S3 carry-over) | Trigger DB timeout via `pg_sleep` with valid key on `/api/customer/{customer_id}` | HTTP 503, sanitised body only | `psycopg2.errors.QueryCanceled` is caught explicitly before `except Exception:`; returns `JSONResponse(status_code=503, content={"code":"INTERNAL_ERROR","message":"An internal error occurred"})` | **CONFIRMED FAIL:** Task prompt for 4.1 forbids modifying `/api/customer`. Bare `except Exception:` remains. Table lock (pg_sleep 15s) → `statement_timeout` fires → `QueryCanceled` → HTTP 500. Body `{"code":"INTERNAL_ERROR","message":"An internal error occurred"}` — sanitised but wrong status code. INV-22 gap persists on `/api/customer`. | [ ] | [x] |

---

## Task 4.1 — Proxy Route and Static UI

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| TC-1 | GET http://localhost:8000/ | HTTP 200; HTML page with input and button | `GET /` returns `HTMLResponse` of `ui/index.html`; file contains an `<input>` element and a button labelled "Look Up" | HTTP 200; `<input` and `Look Up` both present in response body — confirmed via `curl` + `grep` | [x] | [ ] |
| TC-2 | GET /lookup?customer_id=CUST-0001 | HTTP 200; JSON identical to /api/customer/CUST-0001 response | `/lookup` calls `get_customer('CUST-0001')` directly; same dict assembled by `db.py`; both routes return identical JSON — no transformation applied by either | HTTP 200; `{"customer_id":"CUST-0001","risk_tier":"LOW","risk_factors":[]}` — string equality confirmed against `/api/customer/CUST-0001` response | [x] | [ ] |
| TC-3 | GET /lookup?customer_id=CUST-9999 | HTTP 404 with sanitised body | `CustomerNotFoundError` raised by `get_customer`; caught; returns `JSONResponse(404, {"code":"NOT_FOUND","message":"Customer not found"})` — same mapping as `/api/customer` | HTTP 404; body `{"code":"NOT_FOUND","message":"Customer not found"}` confirmed | [x] | [ ] |
| TC-4 | GET /lookup?customer_id=INVALID | HTTP 400 | `_CUSTOMER_ID_RE.match('INVALID')` returns `None`; 400 returned before any DB call; same validation logic as `/api/customer` | HTTP 400; body `{"code":"INTERNAL_ERROR","message":"An internal error occurred"}` confirmed | [x] | [ ] |
| TC-5 | Browser: enter CUST-0001 and click Look Up | customer_id, risk_tier, and risk_factors all displayed | JS `fetch('/lookup?customer_id=CUST-0001')` returns JSON; template rendering reads `d.customer_id`, `d.risk_tier`, `d.risk_factors` directly from the response — no remapping | Static + live: `/lookup?customer_id=CUST-0005` (HIGH tier) returns `customer_id`, `risk_tier`, and two `risk_factors` entries. JS always appends `dtFactors`/`ddFactors` nodes — `risk_factors` section rendered unconditionally via DOM `appendChild` | [x] | [ ] |
| TC-6 | Browser: enter ID for LOW tier with no factors | risk_factors displayed as empty — not hidden | JS renders `d.risk_factors` regardless of array length; no `if (risk_factors.length > 0)` guard suppresses the empty list | `/lookup?customer_id=CUST-0001` → `"risk_factors":[]`; `dtFactors`/`ddFactors` nodes always appended to `dl`; `length === 0` branch renders `(none)` text — section present, not suppressed | [x] | [ ] |
| TC-7 | Inspect ui/index.html source | No API key string; no external script src attributes | `ui/index.html` was written without any reference to `API_KEY`; the `/lookup` route requires no auth header from the browser; no `<script src="...">` tags pointing to external CDN | `grep` for `CUSTOMER_RISK_API_KEY`, `API_KEY`, `apikey` → no matches; `grep` for `<script.*src=` → no matches | [x] | [ ] |
| TC-8 | Inspect /lookup route code in main.py | API_KEY not referenced; no HTTP call to /api/customer | `/lookup` calls `get_customer(customer_id)` from `db.py` directly; `API_KEY` variable is not imported or referenced anywhere in the `/lookup` route body; no `httpx`, `requests`, or `urllib` call present | `grep` on lines 99–134: `API_KEY` appears only in comment at line 99 (not as a variable reference); `get_customer` called at line 118 from `db` import; no `requests`, `httpx`, `urllib` in file | [x] | [ ] |
| TC-9 | Browser network tab for /lookup request | X-API-Key header not sent | `/lookup` requires no auth dependency; the browser JS uses a plain `fetch('/lookup?...')` with no custom headers; `X-API-Key` never constructed or sent | `grep` for `X-API-Key`, `headers`, `Authorization` in `ui/index.html` → no matches; `fetch` call has no options object — default headers only | [x] | [ ] |
| TC-10 | Compare /lookup and /api/customer responses for same ID | JSON responses are identical | Both routes call `get_customer(customer_id)` from the same `db.py` module and return the result directly via `JSONResponse`; no intermediate transformation at either layer | String equality confirmed: `$API_RESP = $LOOKUP_RESP = {"customer_id":"CUST-0001","risk_tier":"LOW","risk_factors":[]}` | [x] | [ ] |

---

## Session Integration Check

| Case | Scenario | Expected | Prediction Statement | Result | PASS | FAIL |
|---|---|---|---|---|---|---|
| INT-1 | GET http://localhost:8000/ | HTTP 200; HTML page contains `<input` element | `GET /` serves `ui/index.html` as `HTMLResponse`; file contains at minimum one `<input>` element for the customer ID field | HTTP 200; `<input` confirmed present in response body | [x] | [ ] |
| INT-2 | GET /lookup?customer_id=CUST-0001 | HTTP 200; JSON contains `risk_tier` key | `/lookup` calls `get_customer` which queries the live DB over the Docker internal network; `risk_tier` key is present in the returned dict | HTTP 200; `"risk_tier"` key confirmed in response body | [x] | [ ] |
| INT-3 | `docker compose ps -q \| wc -l` | Exactly 2 containers | No new services were added in Session 4; `ui/index.html` is served by the `api` container — no third Nginx or static-file container introduced (INV-19) | Container count = 2: `customer_risk_api-api-1` and `customer_risk_api-db-1` | [x] | [ ] |
