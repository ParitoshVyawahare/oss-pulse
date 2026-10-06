-- OSS Pulse: service user for Airflow and dbt (key-pair auth, no password).
-- Run AFTER 01_account_setup.sql. The public key is not a secret; the private key is.
USE ROLE SECURITYADMIN;

CREATE USER IF NOT EXISTS oss_pulse_svc
  TYPE = SERVICE
  DEFAULT_ROLE = transformer
  DEFAULT_WAREHOUSE = transform_wh
  COMMENT = 'OSS Pulse: Airflow loads and dbt runs';

-- Set (or rotate) the key. Re-running with a new key replaces the old one.
ALTER USER oss_pulse_svc SET RSA_PUBLIC_KEY = '<PUBLIC_KEY>';

GRANT ROLE loader      TO USER oss_pulse_svc;
GRANT ROLE transformer TO USER oss_pulse_svc;

-- Check: RSA_PUBLIC_KEY_FP should show a fingerprint starting with SHA256:
DESC USER oss_pulse_svc;
