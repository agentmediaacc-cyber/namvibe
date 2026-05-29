from utils.supabase_client import get_supabase_admin

def count_table(table_name):
    supabase = get_supabase_admin()
    try:
        res = supabase.table(table_name).select("id", count="exact").execute()
        return res.count or 0
    except Exception as exc:
        print(f"[ANALYTICS] count failed for {table_name}:", exc)
        return 0


def platform_snapshot():
    return {
        "profiles": count_table("chain_profiles"),
        "live_rooms": count_table("chain_live_rooms"),
        "messages": count_table("chain_chat_messages"),
        "notifications": count_table("chain_notifications"),
        "wallet_transactions": count_table("chain_wallet_transactions"),
        "gift_events": count_table("chain_gift_events"),
    }
