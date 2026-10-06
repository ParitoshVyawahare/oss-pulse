-- =============================================================================
-- OSS Pulse: Snowflake account setup
-- Run once in a Snowsight SQL worksheet ("Run All"). Safe to re-run.
--
-- Least privilege: each built-in admin role does only its own job.
--   ACCOUNTADMIN  -> account-wide cost guardrail
--   SYSADMIN      -> creates warehouses and databases (and owns them)
--   SECURITYADMIN -> creates roles and grants privileges
-- =============================================================================

-- 1. COST GUARDRAIL ------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

-- Hard monthly cap for the whole account: 20 credits (~$40 on Standard edition).
CREATE RESOURCE MONITOR IF NOT EXISTS oss_pulse_monitor
  WITH CREDIT_QUOTA = 20
       FREQUENCY = MONTHLY
       START_TIMESTAMP = IMMEDIATELY
       TRIGGERS ON 75 PERCENT DO NOTIFY             -- email warning
                ON 100 PERCENT DO SUSPEND           -- stop new queries
                ON 110 PERCENT DO SUSPEND_IMMEDIATE; -- kill running queries too

ALTER ACCOUNT SET RESOURCE_MONITOR = oss_pulse_monitor;

-- The trial's default warehouse idles for minutes before suspending; make it 60s.
ALTER WAREHOUSE IF EXISTS compute_wh SET AUTO_SUSPEND = 60;


-- 2. WAREHOUSES AND DATABASE (owned by SYSADMIN) -------------------------------
USE ROLE SYSADMIN;

-- Separate warehouses per workload: separate cost tracking, no contention.
CREATE WAREHOUSE IF NOT EXISTS load_wh
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE
  COMMENT = 'OSS Pulse: loads raw files into BRONZE';

CREATE WAREHOUSE IF NOT EXISTS transform_wh
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE
  COMMENT = 'OSS Pulse: dbt transformations and dashboard queries';

-- Development database. (PROD is created in week 6 with the same pattern.)
CREATE DATABASE IF NOT EXISTS oss_pulse_dev COMMENT = 'OSS Pulse: development';
CREATE SCHEMA IF NOT EXISTS oss_pulse_dev.bronze COMMENT = 'Raw data, exactly as extracted';


-- 3. ROLES AND GRANTS (SECURITYADMIN) ------------------------------------------
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS loader      COMMENT = 'Loads raw data into BRONZE';
CREATE ROLE IF NOT EXISTS transformer COMMENT = 'Runs dbt: reads BRONZE, builds SILVER and GOLD';
CREATE ROLE IF NOT EXISTS reporter    COMMENT = 'Read-only access to modeled data';

-- Custom roles roll up to SYSADMIN, so admins can see everything they create.
GRANT ROLE loader      TO ROLE SYSADMIN;
GRANT ROLE transformer TO ROLE SYSADMIN;
GRANT ROLE reporter    TO ROLE SYSADMIN;

-- Give the roles to you (whoever is running this script).
SET me = CURRENT_USER();
GRANT ROLE loader      TO USER IDENTIFIER($me);
GRANT ROLE transformer TO USER IDENTIFIER($me);
GRANT ROLE reporter    TO USER IDENTIFIER($me);

-- Warehouses
GRANT USAGE ON WAREHOUSE load_wh      TO ROLE loader;
GRANT USAGE ON WAREHOUSE transform_wh TO ROLE transformer;
GRANT USAGE ON WAREHOUSE transform_wh TO ROLE reporter;

-- LOADER: can create and write tables, stages and file formats in BRONZE only.
GRANT USAGE ON DATABASE oss_pulse_dev        TO ROLE loader;
GRANT USAGE ON SCHEMA   oss_pulse_dev.bronze TO ROLE loader;
GRANT CREATE TABLE, CREATE STAGE, CREATE FILE FORMAT
  ON SCHEMA oss_pulse_dev.bronze TO ROLE loader;

-- TRANSFORMER: reads BRONZE, and can create its own schemas (dbt builds SILVER/GOLD).
GRANT USAGE, CREATE SCHEMA ON DATABASE oss_pulse_dev TO ROLE transformer;
GRANT USAGE ON SCHEMA oss_pulse_dev.bronze           TO ROLE transformer;
GRANT SELECT ON ALL TABLES    IN SCHEMA oss_pulse_dev.bronze TO ROLE transformer;
GRANT SELECT ON FUTURE TABLES IN SCHEMA oss_pulse_dev.bronze TO ROLE transformer;

-- REPORTER: reads whatever dbt builds. Schema-level future grants on BRONZE take
-- precedence over these database-level ones, so REPORTER never sees raw data.
GRANT USAGE ON DATABASE oss_pulse_dev TO ROLE reporter;
GRANT USAGE  ON FUTURE SCHEMAS IN DATABASE oss_pulse_dev TO ROLE reporter;
GRANT SELECT ON FUTURE TABLES  IN DATABASE oss_pulse_dev TO ROLE reporter;
GRANT SELECT ON FUTURE VIEWS   IN DATABASE oss_pulse_dev TO ROLE reporter;


-- 4. CHECK ---------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;
SHOW RESOURCE MONITORS;
