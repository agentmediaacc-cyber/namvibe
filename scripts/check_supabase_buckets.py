import os
import sys
from utils.supabase_client import get_supabase_admin
from services.media_storage_service import SUPPORTED_BUCKETS

def check_buckets():
    print("[check] Supabase Storage buckets...")
    try:
        storage = get_supabase_admin().storage
        all_buckets = storage.list_buckets()
        bucket_names = {b.name for b in all_buckets}
        
        missing = []
        for name in SUPPORTED_BUCKETS:
            if name in bucket_names:
                print(f"  OK: {name}")
            else:
                print(f"  MISSING: {name}")
                missing.append(name)
        
        if missing:
            print("\n⚠️ SETUP REQUIRED: The following buckets are missing in Supabase.")
            print("Please create them in the Supabase Dashboard and set public access.")
            print("\nSQL to create buckets (Supabase SQL Editor):")
            for m in missing:
                print(f"insert into storage.buckets (id, name, public) values ('{m}', '{m}', true);")
            return False
        
        print("\n✅ All storage buckets present.")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

if __name__ == "__main__":
    if not check_buckets():
        sys.exit(1)
