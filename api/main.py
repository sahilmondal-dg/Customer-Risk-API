import hmac
import os
import re
import sys
from pathlib import Path

import psycopg2.errors
from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import HTMLResponse, JSONResponse

# INV-17: loaded from environment at module startup; a restart re-reads the value
API_KEY = os.environ["API_KEY"]

app = FastAPI()

_UI_INDEX = Path(__file__).parent / "ui" / "index.html"


@app.on_event("startup")
async def startup_db_check():
    from db import get_connection
    try:
        conn = get_connection()
        conn.close()
    except RuntimeError as exc:
        print(f"Startup failed: database unavailable — {exc}", file=sys.stderr)
        sys.exit(1)


class _AuthError(Exception):
    pass


@app.exception_handler(_AuthError)
async def _auth_error_handler(request, exc):
    return JSONResponse(
        status_code=401,
        content={"code": "UNAUTHORIZED", "message": "Invalid or missing API key"},
    )


# INV-05, INV-16: header-only, timing-safe comparison
async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise _AuthError()
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise _AuthError()


# INV-21: unauthenticated, no DB call, no shared code path with risk data retrieval
@app.get("/health")
async def health():
    return {"status": "ok"}


_CUSTOMER_ID_RE = re.compile(r"^CUST-\d{4}$")
_CUSTOMER_ID_MAX_LEN = 50

_INTERNAL_ERROR = JSONResponse(
    status_code=500,
    content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"},
)

# INV-02, INV-04, INV-05, INV-07, INV-11
@app.get("/api/customer/{customer_id}", dependencies=[Depends(verify_api_key)])
async def get_customer_endpoint(customer_id: str):
    from db import CustomerNotFoundError, get_customer

    # INV-11: length check before pattern match, both before any DB interaction
    if len(customer_id) > _CUSTOMER_ID_MAX_LEN:
        return JSONResponse(
            status_code=400,
            content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"},
        )
    if not _CUSTOMER_ID_RE.match(customer_id):
        return JSONResponse(
            status_code=400,
            content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"},
        )

    try:
        result = get_customer(customer_id)
        return JSONResponse(status_code=200, content=result)
    except CustomerNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"code": "NOT_FOUND", "message": "Customer not found"},
        )
    except Exception:
        return _INTERNAL_ERROR


# INV-19: served by the FastAPI container — no separate server
@app.get("/")
async def ui_index():
    return HTMLResponse(content=_UI_INDEX.read_text())


# INV-18: no auth check, no API_KEY reference, calls get_customer directly
# INV-22: QueryCanceled mapped to 503
@app.get("/lookup")
async def lookup(customer_id: str = Query(default="")):
    from db import CustomerNotFoundError, get_customer

    # INV-11: same validation as /api/customer, before any DB interaction
    if len(customer_id) > _CUSTOMER_ID_MAX_LEN:
        return JSONResponse(
            status_code=400,
            content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"},
        )
    if not _CUSTOMER_ID_RE.match(customer_id):
        return JSONResponse(
            status_code=400,
            content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"},
        )

    try:
        result = get_customer(customer_id)
        return JSONResponse(status_code=200, content=result)
    except CustomerNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"code": "NOT_FOUND", "message": "Customer not found"},
        )
    except psycopg2.errors.QueryCanceled:
        return JSONResponse(
            status_code=503,
            content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"},
        )
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message": "An internal error occurred"},
        )
