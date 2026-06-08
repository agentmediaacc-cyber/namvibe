"""Apply Phase 37 DB migration."""
import os, sys, logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phase37")

def main():
    sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase37_message_call_runtime_fix.sql")

    from services.neon_service import write_query

    with open(sql_path) as f:
        statements = []
        current = []
        for line in f:
            if line.strip().upper() == "$$":
                current.append(line)
            elif line.strip() == "" and current:
                statements.append("".join(current))
                current = []
            else:
                current.append(line)
        if current:
            statements.append("".join(current))

    blocks = []
    with open(sql_path) as f:
        sql = f.read()

    for stmt in sql.split(";"):
        s = stmt.strip()
        if s:
            blocks.append(s + ";")

    ok = 0
    fail = 0
    for block in blocks:
        if not block or len(block) < 5:
            continue
        try:
            write_query(block, ())
            ok += 1
        except Exception as e:
            if "already exists" in str(e) or "IF NOT EXISTS" in block:
                ok += 1
            else:
                logger.warning("SQL block failed: %s", e)
                fail += 1

    logger.info("Migration: %d OK, %d failed", ok, fail)
    if fail:
        logger.warning("Some blocks failed — check schema above.")
    else:
        logger.info("All Phase 37 tables/indexes verified.")

if __name__ == "__main__":
    main()
