"""Reel watch tracking: view/playback events, watch time, dedup."""

from services.neon_service import write_query, fast_query


def record_watch_event(reel_id, user_id=None, session_id=None, watch_seconds=0, completion_percent=0, replay_count=0):
    write_query(
        """INSERT INTO chain_reel_watch_events
           (reel_id, user_id, session_id, watch_seconds, completion_percent, replay_count)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (reel_id, user_id, session_id, watch_seconds, completion_percent, replay_count),
    )
    _maybe_aggregate(reel_id)


def get_watch_stats(reel_id):
    rows = fast_query(
        """SELECT COUNT(*) AS total_views,
                  COALESCE(AVG(watch_seconds), 0) AS avg_watch,
                  COALESCE(AVG(completion_percent), 0) AS avg_completion,
                  COALESCE(SUM(replay_count), 0) AS total_replays
           FROM chain_reel_watch_events WHERE reel_id = %s""",
        (reel_id,), default=[],
    )
    return rows[0] if rows else {}


def get_user_watch_history(user_id, limit=50):
    rows = fast_query(
        """SELECT reel_id, MAX(watch_seconds) AS max_watch,
                  MAX(completion_percent) AS max_completion,
                  SUM(replay_count) AS total_replays
           FROM chain_reel_watch_events
           WHERE user_id = %s
           GROUP BY reel_id
           ORDER BY MAX(created_at) DESC LIMIT %s""",
        (user_id, limit), default=[],
    )
    return rows or []


def _maybe_aggregate(reel_id):
    try:
        stats = get_watch_stats(reel_id)
        write_query(
            """UPDATE chain_reels SET
               views_count = GREATEST(COALESCE(views_count,0), %s),
               watch_score = %s
               WHERE id = %s""",
            (stats["total_views"], stats["avg_completion"], reel_id),
        )
    except Exception:
        pass
