#!/usr/bin/env python3
"""Run the Phase 7 Creator Studio migration against Neon."""

import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("FLASK_ENV", "production")

from services.neon_service import write_query

MIGRATION_FILE = os.path.join(os.path.dirname(__file__), "migrations", "create_creator_studio_tables.sql")


def split_sql_statements(sql_text):
    """Split SQL into individual statements, respecting DO $$ ... $$ blocks."""
    statements = []
    buf = []
    in_dollar = False
    dollar_tag = None

    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            if not in_dollar:
                continue

        if not in_dollar:
            dollar_match = re.match(r"^DO\s*\$\$", stripped, re.IGNORECASE)
            if dollar_match:
                in_dollar = True
                dollar_tag = "$$"
                buf.append(line)
                continue

            # Regular SQL statement
            if ";" in line:
                parts = line.split(";", 1)
                buf.append(parts[0])
                stmt = "\n".join(buf).strip()
                if stmt:
                    statements.append(stmt)
                buf = []
                remainder = parts[1].strip()
                if remainder:
                    buf.append(remainder)
            else:
                buf.append(line)
        else:
            buf.append(line)
            if dollar_tag and dollar_tag in line:
                # Check if this line ends the DO block
                # The last line of DO block is END $$; or similar
                if re.search(r"END\s*\$\$\s*;", line) or re.search(r"\$\$\s*;", line):
                    stmt = "\n".join(buf).strip()
                    if stmt:
                        statements.append(stmt)
                    buf = []
                    in_dollar = False
                    dollar_tag = None

    # Flush remaining
    remaining = "\n".join(buf).strip()
    if remaining:
        if remaining.endswith(";"):
            remaining = remaining[:-1]
        if remaining.strip():
            statements.append(remaining)

    return statements


def run():
    sql = open(MIGRATION_FILE).read()
    statements = split_sql_statements(sql)

    success = 0
    failed = 0
    for i, stmt in enumerate(statements):
        if not stmt.strip():
            continue
        try:
            write_query(stmt.strip())
            success += 1
            first_line = stmt.strip().split("\n")[0][:80]
            print(f"  OK ({i+1}): {first_line}")
        except Exception as e:
            failed += 1
            first_line = stmt.strip().split("\n")[0][:80]
            print(f"  FAIL ({i+1}): {first_line} -> {e}")

    print(f"\nMigration complete: {success} OK, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
