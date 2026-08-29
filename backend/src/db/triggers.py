from sqlalchemy import text
from src.core.logger import log

TRIGGER_STATEMENTS = [
    """
    CREATE OR REPLACE FUNCTION prevent_audit_log_tampering()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'HIPAA VIOLATION: Updates and Deletes are strictly prohibited on incident_logs.';
    END;
    $$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS trg_prevent_update_incident_logs ON incident_logs;",
    """
    CREATE TRIGGER trg_prevent_update_incident_logs
    BEFORE UPDATE ON incident_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_tampering();
    """,
    "DROP TRIGGER IF EXISTS trg_prevent_delete_incident_logs ON incident_logs;",
    """
    CREATE TRIGGER trg_prevent_delete_incident_logs
    BEFORE DELETE ON incident_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_tampering();
    """
]

async def setup_triggers(engine):
    """
    Installs database-level strict security triggers.
    Ensures HIPAA compliance for audit trails.
    """
    try:
        async with engine.begin() as conn:
            for stmt in TRIGGER_STATEMENTS:
                stmt_clean = stmt.strip()
                if stmt_clean:
                    await conn.execute(text(stmt_clean))
        log.info("[Security] HIPAA Append-Only Triggers installed successfully.")
    except Exception as e:
        log.error(f"[Security] Failed to install HIPAA Triggers: {str(e)}")
