# INVARIANTS.md
**Customer Risk API · Version 1.0**
_Classification: Training Demo System_

---

## Preamble

This document defines the system invariants for the Customer Risk API. Invariants are constraints that must hold true at all times. Violations represent either a defect, a security failure, or a data integrity failure — not a configuration choice.

**Assumed values** (marked ⚠️) must be confirmed against client seed data before go-live. Invariants derived from assumptions are correct in shape but may require value updates.

---

## Assumptions on Record

| Assumption | Value Assumed | Must Confirm Before |
|---|---|---|
| Customer ID format | `CUST-\d{4}` (e.g. `CUST-0042`) | INV-11 goes live |
| Risk factor code set | `HIGH_TRANSACTION_VOLUME`, `MULTIPLE_JURISDICTIONS`, `ADVERSE_MEDIA_MATCH`, `PEP_ASSOCIATION`, `UNUSUAL_ACCOUNT_ACTIVITY` | INV-13 goes live |
| MEDIUM/HIGH with zero factors | Not valid — at least one factor required | INV-04, INV-23 |
| Health endpoint | Required at `/health`, unauthenticated | INV-21 |
| Query timeout | 5 seconds | INV-22 |
| API key header | `X-API-Key` only | INV-05 |

---

## INV-01 — Database Is Source of Truth

The API response values for `customer_id`, `risk_tier`, and `risk_factors` must exactly match the values stored in Postgres for the queried customer. The response must contain **all** risk factor rows associated with that customer — not a subset.

**Violation Impact:** Incorrect or incomplete risk information returned to users.

**Detection:** Direct comparison between API response and DB query for the same customer ID, including factor count verification.

**Assumptions:** None.

---

## INV-02 — Customer Existence Mapping

A request for an existing `customer_id` must return HTTP 200 with a complete, valid response body. A request for a non-existent `customer_id` must return HTTP 404. A 200 response is only valid when the returned record is complete and passes schema validation — a structurally incomplete record must never produce a 200.

**Violation Impact:** Incorrect interpretation of risk data availability; silent data integrity failures surfaced as valid responses.

**Detection:** Test existing IDs, non-existing IDs, and IDs whose DB records are deliberately malformed (null tier, missing factors).

**Assumptions:** None.

---

## INV-03 — System Must Be Read-Only

The API must never modify database state. No endpoint may perform INSERT, UPDATE, DELETE, DDL operations, or acquire row-level locks via `SELECT FOR UPDATE`. The Postgres role used by the API must be granted `SELECT` privilege only — write capability must not exist at the credential level, not just the application level.

**Violation Impact:** Risk database corruption; false sense of security from application-level checks alone.

**Detection:** Code inspection for SQL operations; Postgres role verification via `\du` and `\dp`; attempt INSERT via the API DB credentials and confirm rejection at the DB level.

**Assumptions:** None.

---

## INV-04 — Response Schema Consistency

Every successful API response must conform to exactly this structure:

```json
{
  "customer_id": "string",
  "risk_tier": "LOW | MEDIUM | HIGH",
  "risk_factors": [
    { "code": "string", "description": "string" }
  ]
}
```

`customer_id` must be a string type in the serialised response. `risk_factors` must be an array; it may be empty only for LOW tier customers. All keys must be present — a response missing any key is a schema violation regardless of the values present.

**Violation Impact:** Client systems break due to inconsistent schema; type mismatches cause silent failures in downstream consumers.

**Detection:** JSON schema validation tests against every response; explicit type checks on `customer_id` to confirm string not integer serialisation.

**Assumptions:** ⚠️ MEDIUM and HIGH customers must have at least one risk factor.

---

## INV-05 — Authentication Enforcement

Every request to `/api/*` endpoints must require a valid API key passed via the `X-API-Key` request header. Requests without a valid key must return HTTP 401. The API key must be accepted only via the `X-API-Key` header — passing the key as a query parameter, request body field, or any other mechanism must not grant access. The `/health` endpoint is explicitly exempt from authentication.

**Violation Impact:** Unauthorised access to risk data; credential exposure via URL logging if query parameter passing is permitted.

**Detection:** Requests with no key, wrong key, key in query param, and key in body must all return 401 on protected routes. Request with valid key in `X-API-Key` header must return 200.

**Assumptions:** ⚠️ `X-API-Key` as header name. ⚠️ `/health` exemption.

---

## INV-06 — API Key Must Never Be Exposed

The API key must never appear in responses, error messages, application logs, access logs, the UI source or rendered output, stack traces, or HTTP response headers. The API key must only be accepted via a named request header, never via query string, to prevent URL-level exposure in access logs and browser history.

**Violation Impact:** Credential compromise.

**Detection:** Trigger all error paths and inspect responses and logs; review UI source; confirm access log format does not record `X-API-Key` header values; attempt passing key as query param and confirm it is rejected, not logged.

**Assumptions:** None.

---

## INV-07 — Internal Errors Must Not Leak

Database or server exceptions must never expose stack traces, SQL queries, connection strings, internal hostnames, ports, schema names, or configuration values. All error responses must conform to a fixed approved structure containing only a `code` field and a `message` field drawn from a predefined allowlist of generic messages. Any response not matching this structure is a violation. This applies to all code paths including startup, retry loops, and timeout handling.

**Violation Impact:** Information disclosure vulnerability.

**Detection:** Simulate DB unavailability, query timeout, malformed input, and serialisation errors; inspect all responses for any content outside the approved error structure; verify startup-path error output.

**Assumptions:** None.

---

## INV-08 — No External Service Calls

The system must operate entirely locally. No application code may call external APIs, third-party services, or remote databases. This constraint must be enforced at the infrastructure level — the FastAPI container's outbound network access must be restricted to the internal Docker Compose network only, so the constraint is not solely dependent on code review.

**Violation Impact:** Violation of system constraints; potential data exfiltration via dependencies.

**Detection:** Code review and dependency inspection; network policy verification in Docker Compose; runtime network monitoring during test execution.

**Assumptions:** None.

---

## INV-09 — UI Must Not Transform or Suppress API Data

The browser UI must render values exactly as returned by the API. It must not recompute risk tier, remap factor codes, or alter descriptions. It must display all fields present in the API response and must not conditionally suppress any field, including an empty `risk_factors` array. Display formatting such as colour-coding or capitalisation is permitted provided the underlying data value is not altered. The distinction between permitted presentation formatting and forbidden data mutation must be verifiable by inspecting the JavaScript — no computed value may replace an API-returned value in the rendered output.

**Violation Impact:** UI and API data divergence; operational staff act on incomplete information.

**Detection:** Inspect UI JavaScript for any transformation logic; compare rendered output against raw API response for all three risk tiers including a LOW customer with an empty factors array.

**Assumptions:** None.

---

## INV-10 — SQL Queries Must Be Parameterised

All SQL queries must use parameterised statements. `cursor.execute()` must always be called with a query string containing only `%s` placeholders and a separate parameters tuple — never a pre-formatted or pre-interpolated string. String concatenation and f-strings in SQL construction are forbidden at all call sites and in all helper functions. Second-order injection — where a value is safely stored but later used in dynamic query construction — is also forbidden.

**Violation Impact:** SQL injection vulnerability.

**Detection:** Code inspection of all call sites and helper functions; execute a SQL injection payload as a customer ID and confirm it is handled safely.

**Assumptions:** None.

---

## INV-11 — Customer ID Format Validation ⚠️

The `customer_id` input must be validated against the pattern `CUST-\d{4}` before any database interaction. Inputs not matching this pattern must be rejected with HTTP 400. Validation must be applied at the entry point — no DB query may be issued for an input that fails format validation. Maximum input length must be enforced before pattern matching to prevent regex amplification. An empty string must be rejected with 400, not 404.

**Violation Impact:** False 400 errors on valid IDs if pattern is wrong; unexpected DB behaviour or query failures on malformed input.

**Detection:** Test valid format IDs, invalid format IDs, empty string, excessively long strings, and SQL injection payloads. Confirm 400 is returned before any DB interaction occurs.

**Assumptions:** ⚠️ Customer ID pattern is `CUST-\d{4}` — must be confirmed against seed data before go-live.

---

## INV-12 — Risk Tier Values Are Restricted

The `risk_tier` field must only contain exactly `LOW`, `MEDIUM`, or `HIGH` in uppercase with no surrounding whitespace. This constraint must be enforced at both the DB level (CHECK constraint) and at the API serialisation layer — the API must re-validate the value retrieved from the DB before including it in a response. A value retrieved from the DB that does not match the allowed set must be treated as a data integrity error and must return HTTP 500 with a sanitised error message, not passed through to the caller.

**Violation Impact:** System logic inconsistency; downstream consumers receive unexpected values.

**Detection:** DB constraint verification; attempt to insert an invalid tier value directly into the DB and confirm rejection; seed a record with a trailing-space value and confirm the API rejects it at the serialisation layer.

**Assumptions:** None.

---

## INV-13 — Risk Factor Codes Are From a Defined Set ⚠️

The `code` field in each risk factor must be one of the following defined values:

- `HIGH_TRANSACTION_VOLUME`
- `MULTIPLE_JURISDICTIONS`
- `ADVERSE_MEDIA_MATCH`
- `PEP_ASSOCIATION`
- `UNUSUAL_ACCOUNT_ACTIVITY`

Any `code` value returned from the DB that is not in this set must be treated as a data integrity error and must not be passed through to the caller. Changes to this set are breaking changes and require a version signal.

**Violation Impact:** Downstream consumers depending on stable code identifiers break silently; contract is violated without detection.

**Detection:** Verify all seed data codes against the defined set; attempt to seed a record with an unlisted code and confirm the API rejects it at the serialisation layer.

**Assumptions:** ⚠️ Code set as listed above — must be confirmed against client seed data before go-live.

---

## INV-14 — Referential Integrity Between Customer and Risk Factors

Every `risk_factor` row must have a corresponding `customer` row. No orphaned factor rows may exist. The DB schema must enforce this via a foreign key constraint with `ON DELETE CASCADE` or equivalent. At the application layer, the query assembling the response must verify that all returned factors belong to the queried customer ID — a mismatch must be treated as a data integrity error.

**Violation Impact:** Factors from one customer could appear in another customer's response; orphaned rows produce undefined API behaviour.

**Detection:** FK constraint verification in schema; attempt to insert an orphaned factor row directly and confirm DB rejection; verify query logic associates factors to the correct customer ID.

**Assumptions:** None.

---

## INV-15 — Customer Lookup Returns Exactly One Record

A customer ID lookup must return exactly one customer record or zero. If the query returns more than one row for a given `customer_id`, the API must treat this as a data integrity error and return HTTP 500 with a sanitised error message — it must not silently return the first result. The `customer` table must have a primary key or unique constraint on `customer_id` enforced at the DB level.

**Violation Impact:** Ambiguous lookups silently return arbitrary data; data integrity failures are invisible to callers.

**Detection:** Unique constraint verification in schema; attempt to insert a duplicate customer ID directly and confirm DB rejection; verify application-layer handling of a hypothetical multi-row result.

**Assumptions:** None.

---

## INV-16 — Authentication Uses Timing-Safe Comparison

API key validation must use `hmac.compare_digest` for all key comparisons. Plain equality operators (`==`, `!=`, `is`) must not be used for API key comparison at any point in the auth code path. This applies to the primary validation and to any fallback or error handling paths.

**Violation Impact:** Timing side-channel attack enables key enumeration.

**Detection:** Code inspection of all auth code paths including error handlers; confirm no equality operator is used on the key value.

**Assumptions:** None.

---

## INV-17 — API Key Loaded at Startup from Environment

The API key must be loaded from the `.env` file at process startup and must not be cached beyond process lifetime. A process restart must re-read the key from the environment, so that rotating `.env` and redeploying takes effect immediately on restart with no stale key surviving.

**Violation Impact:** Key rotation does not take effect; a compromised key remains valid after the intended revocation point.

**Detection:** Rotate the key in `.env`, restart the container, confirm the old key is rejected and the new key is accepted.

**Assumptions:** None.

---

## INV-18 — Proxy Route Does Not Bypass Authentication

The internal data function shared between the proxy route and the API route must be the only application-layer entry point to the risk data. No route other than the defined `/api/*` routes may invoke this function or return risk data. The proxy route must not perform its own auth check — auth lives on the API route only. Addition of any new route that calls the internal data function is a violation unless that route is a defined `/api/*` endpoint subject to INV-05.

**Violation Impact:** Auth boundary enforced by convention is silently broken by a new route; risk data exposed without key check.

**Detection:** Code inspection of all route handlers; confirm the internal data function is called from exactly the routes intended; confirm no auth logic exists on the data function itself.

**Assumptions:** None.

---

## INV-19 — System Starts With Exactly Two Containers

The Docker Compose configuration must define exactly two services: the FastAPI application container and the Postgres database container. No additional containers may be introduced without a documented architectural decision superseding Decision 1. All application concerns — the protected API endpoint, the browser-facing proxy route, and static HTML serving — must be handled by the single FastAPI container.

**Violation Impact:** Orchestration complexity reintroduced; auth enforcement may shift to infrastructure layer without corresponding invariant coverage; scope of Decision 1 violated without review.

**Detection:** Service count verification in `docker-compose.yml`; confirm no additional service definitions exist; confirm UI is served from the FastAPI container, not a separate process.

**Assumptions:** None.

---

## INV-20 — DB Connection Failure Behaviour

After exhausting the retry loop (10 attempts, 1-second intervals), the FastAPI process must exit with a non-zero exit code and emit a human-readable error message identifying DB unavailability as the cause. During the retry window, any incoming HTTP request must receive HTTP 503, not 500, and must not expose connection details in the response body.

**Violation Impact:** Silent failure leaves container running but non-functional; 500 responses during startup may leak internal configuration in violation of INV-07.

**Detection:** Start the stack with Postgres intentionally unavailable; confirm 503 responses during retry window; confirm non-zero exit after retry exhaustion; confirm no DB details in any response during this window.

**Assumptions:** None.

---

## INV-21 — Health Endpoint Behaviour ⚠️

The `/health` endpoint must return HTTP 200 with a fixed, minimal response body (`{"status": "ok"}`). It must not return business data, customer records, risk information, internal configuration, DB connection status details, or service version information. It must not require authentication. It must not share any code path with the risk data retrieval logic. It must return 200 regardless of DB connectivity — it is a process liveness signal, not a DB health signal.

**Violation Impact:** Information disclosure via an unauthenticated route; false health signals if the endpoint depends on DB state.

**Detection:** Request `/health` without an API key and confirm 200; inspect response body and confirm it contains no business data or internal configuration; confirm the endpoint returns 200 when the DB is unavailable.

**Assumptions:** ⚠️ Health endpoint is required at `/health`.

---

## INV-22 — Query Timeout Enforcement

All database queries must be subject to a 5-second timeout. A query exceeding this limit must be cancelled at the DB level, not just abandoned at the application level. The caller must receive HTTP 503 with a sanitised error message. The timeout value must be a named constant, not an inline literal.

**Violation Impact:** Slow queries hold connections indefinitely; connection pool exhaustion under load; no signal to caller that the request failed.

**Detection:** Simulate a slow query via `pg_sleep` and confirm 503 is returned within the timeout window; confirm query is cancelled in Postgres via `pg_stat_activity`; confirm no DB details in the response body.

**Assumptions:** ⚠️ 5-second timeout (stated in architecture assumptions — revisit if data volume grows).

---

## INV-23 — Seed Data Coverage ⚠️

On a fresh volume, the database must contain at least one customer record for each of the three risk tiers (LOW, MEDIUM, HIGH). LOW tier customers must include at least one record with an empty `risk_factors` array. MEDIUM and HIGH tier customers must each have at least one record with at least one risk factor. All five defined risk factor codes must appear in the seed data at least once.

**Violation Impact:** System passes all invariants but is not representative of intended data; edge cases in the empty-array path are never exercised in testing.

**Detection:** After `docker compose up` on a fresh volume, query the DB directly and verify tier distribution and factor code coverage against this invariant.

**Assumptions:** ⚠️ Code set and tier rules as assumed above — must be confirmed against client seed data before go-live.

---

## Summary Table

| ID | Topic | Assumed? |
|---|---|---|
| INV-01 | DB source of truth + completeness | No |
| INV-02 | Existence mapping + completeness gate | No |
| INV-03 | Read-only + DB role enforcement | No |
| INV-04 | Response schema + type correctness | Partially |
| INV-05 | Auth enforcement + header-only | Partially |
| INV-06 | Key non-exposure + query param rejection | No |
| INV-07 | Error leakage + approved error structure | No |
| INV-08 | No external calls + network enforcement | No |
| INV-09 | UI non-transformation + non-suppression | No |
| INV-10 | Parameterised SQL + helper functions | No |
| INV-11 | Customer ID format validation | ⚠️ Yes — pattern |
| INV-12 | Risk tier restriction + re-validation on read | No |
| INV-13 | Risk factor code set | ⚠️ Yes — codes |
| INV-14 | Referential integrity | No |
| INV-15 | Single-record lookup | No |
| INV-16 | Timing-safe key comparison | No |
| INV-17 | Key loaded at startup | No |
| INV-18 | Proxy route auth boundary | No |
| INV-19 | Two-container + single app container constraint | No |
| INV-20 | DB connection failure behaviour | No |
| INV-21 | Health endpoint behaviour | ⚠️ Yes — endpoint |
| INV-22 | Query timeout enforcement | ⚠️ Yes — value |
| INV-23 | Seed data coverage | ⚠️ Yes — codes + rules |

---

_Last updated: 2026-03-17 · Status: Draft — assumed values in INV-11, INV-13, INV-21, INV-22, INV-23 pending client confirmation_
