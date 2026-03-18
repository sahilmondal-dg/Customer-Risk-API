import hmac
import os
import sys

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse

# INV-17: loaded from environment at module startup; a restart re-reads the value
API_KEY = os.environ["API_KEY"]

app = FastAPI()


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


# INV-05, INV-16: header-only, timing-safe comparison — not wired to any route yet
async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise _AuthError()
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise _AuthError()


# INV-21: unauthenticated, no DB call, no shared code path with risk data retrieval
@app.get("/health")
async def health():
    return {"status": "ok"}
