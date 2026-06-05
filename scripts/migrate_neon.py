import os
import sys
import subprocess
from urllib.parse import urlparse

def migrate(files=None, dry_run=False):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ FAILED: DATABASE_URL not set")
        return False

    parsed = urlparse(db_url)
    masked_url = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}{parsed.path}"
    print(f"[migrate] Target: {masked_url}")

    if not files:
        files = ["sql/chain_neon_core_schema.sql"]

    for schema_file in files:
        if not os.path.exists(schema_file):
            print(f"❌ FAILED: Schema file missing: {schema_file}")
            return False

        if dry_run:
            print(f"[migrate] DRY RUN: Skipping {schema_file}")
            continue

        print(f"[migrate] Applying {schema_file}...")
        try:
            res = subprocess.run(["psql", db_url, "-f", schema_file], capture_output=True, text=True)
            if res.returncode != 0:
                print(f"❌ FAILED: psql error in {schema_file}")
                print(res.stderr)
                return False
            print(res.stdout)
        except FileNotFoundError:
            print("❌ FAILED: 'psql' command not found. Please install postgresql-client.")
            return False
        except Exception as e:
            print(f"❌ FAILED: {e}")
            return False

    if not dry_run:
        print("✅ Migration successful.")
    return True

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    target_files = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if not migrate(files=target_files, dry_run=is_dry):
        sys.exit(1)
