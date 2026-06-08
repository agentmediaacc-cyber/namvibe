from pathlib import Path
from services.neon_service import write_query

sql = Path("scripts/phase25_add_chain_profile_features.sql").read_text()
write_query(sql, ())
print("✅ Missing CHAIN profile feature columns added to Neon.")
