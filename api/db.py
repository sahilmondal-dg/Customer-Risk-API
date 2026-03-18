import os
import sys
import time
import psycopg2

# INV-22: timeout must be a named constant, never an inline literal
QUERY_TIMEOUT_SECONDS = 5


class CustomerNotFoundError(Exception):
    pass


class DataIntegrityError(Exception):
    pass


def get_connection():
    """
    Establish a psycopg2 connection with statement_timeout set.

    The Postgres role supplied via POSTGRES_USER must be a read-only role
    (SELECT privilege only). That role is created and configured in
    db/01_schema.sql — enforcement is at the credential level, not here.
    """
    host = os.environ["POSTGRES_HOST"]
    port = os.environ["POSTGRES_PORT"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    dbname = os.environ["POSTGRES_DB"]

    last_error = None
    for attempt in range(1, 11):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=dbname,
            )
            cur = conn.cursor()
            cur.execute("SET statement_timeout = %s", (QUERY_TIMEOUT_SECONDS * 1000,))
            conn.commit()
            cur.close()
            return conn
        except psycopg2.Error as exc:
            last_error = exc
            print(
                f"Database connection attempt {attempt}/10 failed: {exc.pgerror or str(exc)}",
                file=sys.stderr,
            )
            if attempt < 10:
                time.sleep(1)

    raise RuntimeError("Database unavailable after 10 attempts")


_ALLOWED_TIERS = {"LOW", "MEDIUM", "HIGH"}

_ALLOWED_CODES = {
    "HIGH_TRANSACTION_VOLUME",
    "MULTIPLE_JURISDICTIONS",
    "ADVERSE_MEDIA_MATCH",
    "PEP_ASSOCIATION",
    "UNUSUAL_ACCOUNT_ACTIVITY",
}


def get_customer(customer_id: str) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Query 1: fetch customer row — INV-01, INV-02, INV-15
        cur.execute(
            "SELECT customer_id, risk_tier FROM customer WHERE customer_id = %s",
            (customer_id,),
        )
        rows = cur.fetchall()

        if len(rows) == 0:
            raise CustomerNotFoundError
        if len(rows) > 1:
            raise DataIntegrityError("Duplicate customer record")

        db_customer_id, risk_tier = rows[0]

        # Validate tier — INV-12
        if risk_tier not in _ALLOWED_TIERS:
            raise DataIntegrityError("Invalid risk tier value")

        # Query 2: fetch risk factors — INV-01, INV-13, INV-14
        cur.execute(
            "SELECT code, description FROM risk_factor WHERE customer_id = %s",
            (customer_id,),
        )
        factor_rows = cur.fetchall()

        risk_factors = []
        for code, description in factor_rows:
            if code not in _ALLOWED_CODES:
                raise DataIntegrityError("Invalid risk factor code")
            risk_factors.append({"code": code, "description": description})

        return {
            "customer_id": str(db_customer_id),
            "risk_tier": risk_tier,
            "risk_factors": risk_factors,
        }
    finally:
        conn.close()
