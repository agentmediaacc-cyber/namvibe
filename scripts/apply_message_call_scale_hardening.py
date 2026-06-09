"""Apply CALL + MESSAGE SCALE HARDENING migration — columns, indexes, tables."""
import os, sys, logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scale_hardening")

def main():
    sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "message_call_scale_hardening.sql")
    from services.neon_service import write_query

    with open(sql_path) as f:
        sql = f.read()

    blocks = []
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
            if "already exists" in str(e):
                ok += 1
            else:
                logger.warning("SQL block failed: %s", e)
                fail += 1

    logger.info("Scale hardening migration: %d OK, %d failed", ok, fail)
    if fail:
        logger.warning("Some blocks failed — check schema above.")
    else:
        logger.info("All CALL + MESSAGE scale hardening tables/indexes verified.")

if __name__ == "__main__":
    main()
