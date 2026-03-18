-- Customer Risk API — Schema
-- Task 1.2 · Idempotent: safe to run on an existing database

CREATE TABLE IF NOT EXISTS customer (
    customer_id VARCHAR PRIMARY KEY,
    risk_tier   VARCHAR NOT NULL,
    CONSTRAINT chk_customer_risk_tier
        CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))
);

CREATE TABLE IF NOT EXISTS risk_factor (
    id          SERIAL  PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    code        VARCHAR NOT NULL,
    description TEXT    NOT NULL,
    CONSTRAINT fk_risk_factor_customer
        FOREIGN KEY (customer_id)
        REFERENCES customer (customer_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_risk_factor_code
        CHECK (code IN (
            'HIGH_TRANSACTION_VOLUME',
            'MULTIPLE_JURISDICTIONS',
            'ADVERSE_MEDIA_MATCH',
            'PEP_ASSOCIATION',
            'UNUSUAL_ACCOUNT_ACTIVITY'
        ))
);
