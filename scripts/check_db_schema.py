import sys
import os
sys.path.append(os.getcwd())
from services.neon_service import get_table_columns

def check_schema():
    for table in ["chain_posts", "chain_reels", "chain_live_rooms"]:
        cols = get_table_columns(table)
        print(f"Table: {table}")
        print(f"Columns: {sorted(cols)}")
        print("-" * 40)

if __name__ == "__main__":
    check_schema()
