from services.neon_service import fast_query


def can_access_thread(profile_id, thread_id):
    if not profile_id or not thread_id:
        return False
    rows = fast_query(
        "SELECT profile_id FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s LIMIT 1",
        (thread_id, profile_id),
        default=[],
    )
    return bool(rows)
