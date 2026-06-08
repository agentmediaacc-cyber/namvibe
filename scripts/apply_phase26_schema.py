from pathlib import Path
from services.neon_service import write_query

sql = Path("scripts/phase26_full_profile_schema.sql").read_text()
write_query(sql, ())
print("✅ Full CHAIN profile schema applied.")
