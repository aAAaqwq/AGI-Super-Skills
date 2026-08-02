PRAGMA foreign_keys = ON;

-- One immutable decision cutoff per production logical run.  Retry attempts
-- must reuse this exact value; caller-supplied state is not authoritative.
CREATE TABLE IF NOT EXISTS production_run_cutoff (
    logical_run_id TEXT PRIMARY KEY,
    decision_at_utc TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (logical_run_id) REFERENCES logical_run(logical_run_id)
);

CREATE TRIGGER IF NOT EXISTS production_run_cutoff_production_only
BEFORE INSERT ON production_run_cutoff
WHEN (SELECT run_namespace FROM logical_run
      WHERE logical_run_id = NEW.logical_run_id) != 'PRODUCTION'
BEGIN
    SELECT RAISE(ABORT, 'only production runs may freeze a decision cutoff');
END;
