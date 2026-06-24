"""Phase 157 Audit I: Ads foundation completeness."""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.neon_service import fast_query, write_query
from services.ads_service import create_campaign, get_active_campaigns, record_impression, record_click, get_campaign_stats, get_ads_for_feed

def get_test_profiles(count=2):
    rows = fast_query(f"SELECT id FROM chain_profiles LIMIT {count}", default=[])
    return [str(r["id"]) for r in rows]

def run():
    profiles = get_test_profiles(2)
    if len(profiles) < 2:
        print("SKIP: Need at least 2 profiles in DB")
        return
    profile_id, viewer_id = profiles[0], profiles[1]

    # Check tables exist
    for table in ["chain_ad_campaigns", "chain_ad_impressions", "chain_ad_clicks"]:
        rows = fast_query(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = %s",
            (table,), default=[]
        )
        assert rows, f"Table {table} does not exist"

    campaign_id = None
    try:
        res = create_campaign(profile_id, "Test Ad", "https://example.com/ad", "https://example.com", ad_type="feed")
        assert res.get("ok"), f"Create campaign failed: {res}"
        campaign_id = res["campaign_id"]

        campaigns = get_active_campaigns()
        cids = [c["id"] for c in campaigns]
        assert campaign_id in cids, f"Campaign should be in active list"

        ok = record_impression(campaign_id, viewer_id)
        assert ok, "record_impression failed"

        ok = record_click(campaign_id, viewer_id)
        assert ok, "record_click failed"

        stats = get_campaign_stats(campaign_id)
        assert stats["impressions"] >= 1, f"Expected >= 1 impressions"
        assert stats["clicks"] >= 1, f"Expected >= 1 clicks"

        ads = get_ads_for_feed(viewer_id=viewer_id, slot_count=2)
        for ad in ads:
            assert ad.get("is_ad")
            assert ad.get("sponsored")
    finally:
        if campaign_id:
            write_query("DELETE FROM chain_ad_impressions WHERE campaign_id = %s", (campaign_id,))
            write_query("DELETE FROM chain_ad_clicks WHERE campaign_id = %s", (campaign_id,))
            write_query("DELETE FROM chain_ad_campaigns WHERE id = %s", (campaign_id,))

    print("PASS: audit_phase157_ads_foundation")

if __name__ == "__main__":
    run()
