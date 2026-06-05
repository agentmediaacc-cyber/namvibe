from datetime import datetime, timezone, timedelta
from services.neon_service import fast_query, write_query
from services.supabase_safe import safe_count, safe_select

def calculate_profile_trust_score(profile_id):
    """
    Calculates trust score for a profile based on multiple factors.
    Range: 0.0 to 10.0
    """
    profile = (safe_select("chain_profiles", filters={"id": profile_id}, limit=1) or [{}])[0]
    if not profile: return 5.0

    score = 5.0 # Base score

    # 1. Account Age (+0.5 per month, max +2.0)
    created_at = profile.get("created_at")
    if created_at:
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created_at).days
        score += min(age_days / 30 * 0.5, 2.0)

    # 2. Verified Status (+3.0)
    if profile.get("is_verified") or profile.get("verified"):
        score += 3.0

    # 3. Premium Status (+1.0)
    if profile.get("is_premium"):
        score += 1.0

    # 4. Reports (-1.5 per resolved report, max -6.0)
    report_count = safe_count("chain_reports", filters={"target_profile_id": profile_id, "status": "resolved"})
    score -= min(report_count * 1.5, 6.0)

    # 5. Blocks (-0.2 per block, max -2.0)
    block_count = safe_count("chain_blocks", filters={"blocked_profile_id": profile_id})
    score -= min(block_count * 0.2, 2.0)

    # 6. Successful Interactions (+0.1 per interaction, max +2.0)
    # E.g. successful messages with unique users, completed marketplace transactions
    interaction_count = safe_count("chain_message_threads", filters={"created_by_profile_id": profile_id}) # Simplified
    score += min(interaction_count * 0.1, 2.0)

    # Ensure range 0 to 10
    final_score = max(0.0, min(10.0, score))
    
    # Update DB
    write_query("UPDATE chain_profiles SET trust_score = %s, last_trust_update = now() WHERE id = %s", (final_score, profile_id))
    
    return final_score

def batch_update_trust_scores(limit=100):
    """Periodic job to refresh trust scores"""
    sql = "SELECT id FROM chain_profiles WHERE last_trust_update IS NULL OR last_trust_update < now() - interval '1 day' LIMIT %s"
    profiles = fast_query(sql, (limit,))
    for p in profiles:
        calculate_profile_trust_score(p['id'])
    return len(profiles)
