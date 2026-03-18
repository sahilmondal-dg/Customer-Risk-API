-- Customer Risk API — Seed Data
-- Task 1.2 · Idempotent: safe to run multiple times

-- Customers
INSERT INTO customer (customer_id, risk_tier) VALUES
    ('CUST-0001', 'LOW'),
    ('CUST-0002', 'LOW'),
    ('CUST-0003', 'MEDIUM'),
    ('CUST-0004', 'MEDIUM'),
    ('CUST-0005', 'HIGH'),
    ('CUST-0006', 'HIGH')
ON CONFLICT DO NOTHING;

-- CUST-0001: LOW, zero risk factors — satisfies INV-23 (LOW with empty factors)
-- CUST-0002: LOW, one risk factor
-- CUST-0003: MEDIUM, two risk factors
-- CUST-0004: MEDIUM, one risk factor
-- CUST-0005: HIGH, two risk factors
-- CUST-0006: HIGH, one risk factor

INSERT INTO risk_factor (customer_id, code, description) VALUES
    -- CUST-0002 (LOW)
    ('CUST-0002', 'UNUSUAL_ACCOUNT_ACTIVITY',
        'Irregular transaction pattern detected during routine account review.'),

    -- CUST-0003 (MEDIUM)
    ('CUST-0003', 'HIGH_TRANSACTION_VOLUME',
        'Transaction volume exceeds threshold for customer segment over the past 90 days.'),
    ('CUST-0003', 'MULTIPLE_JURISDICTIONS',
        'Transactions recorded across five or more distinct jurisdictions within a 30-day period.'),

    -- CUST-0004 (MEDIUM)
    ('CUST-0004', 'ADVERSE_MEDIA_MATCH',
        'Customer name returned a match in adverse media screening conducted during onboarding review.'),

    -- CUST-0005 (HIGH)
    ('CUST-0005', 'PEP_ASSOCIATION',
        'Customer has a confirmed association with a politically exposed person identified in public records.'),
    ('CUST-0005', 'MULTIPLE_JURISDICTIONS',
        'Accounts active in jurisdictions flagged under current regulatory guidance.'),

    -- CUST-0006 (HIGH)
    ('CUST-0006', 'HIGH_TRANSACTION_VOLUME',
        'Sustained high-frequency transactions inconsistent with declared business activity.')
ON CONFLICT DO NOTHING;
