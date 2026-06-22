"""
Content Manager Service — Unified management for posts and reels.
Handles tabs (Newest, Oldest, Drafts, Scheduled, Archived, Pinned) and visibility controls.
"""
from services.neon_service import fast_query, write_query
from services.logging_service import log_info, log_error

CONTENT_COLUMNS = {
    "posts": [
        "id", "profile_id", "body", "media_url", "visibility", "status",
        "is_archived", "is_pinned", "scheduled_at", "created_at", "updated_at",
    ],
    "reels": [
        "id", "profile_id", "caption", "video_url", "thumbnail_url", "visibility",
        "status", "is_archived", "is_pinned", "created_at", "updated_at",
    ],
}

def _ensure_content_columns():
    """Return the production content columns without schema reads in request paths."""
    return CONTENT_COLUMNS

def get_managed_posts(profile_id, tab='newest', limit=20, cursor=None):
    """Lists posts for management with tab-based filtering and cursor pagination."""
    cols = _ensure_content_columns().get("posts", [])
    if not cols:
        # Fallback to minimal known columns if detection fails
        cols = ["id", "body", "created_at"]
    
    col_str = ", ".join(cols)
    query = f"SELECT {col_str} FROM chain_posts WHERE profile_id = %s AND deleted_at IS NULL"
    params = [profile_id]
    
    if tab == 'newest':
        query += " AND status = 'published' AND is_archived = FALSE"
        order = "created_at DESC"
    elif tab == 'oldest':
        query += " AND status = 'published' AND is_archived = FALSE"
        order = "created_at ASC"
    elif tab == 'drafts':
        query += " AND status = 'draft'"
        order = "updated_at DESC"
    elif tab == 'scheduled':
        query += " AND status = 'scheduled'"
        order = "scheduled_at ASC"
    elif tab == 'archived':
        query += " AND is_archived = TRUE"
        order = "updated_at DESC"
    elif tab == 'pinned':
        query += " AND is_pinned = TRUE"
        order = "created_at DESC"
    else:
        query += " AND status = 'published' AND is_archived = FALSE"
        order = "created_at DESC"

    if cursor:
        direction = ">" if tab == 'oldest' else "<"
        cursor_col = "created_at"
        if tab == 'drafts': cursor_col = "updated_at"
        if tab == 'scheduled': cursor_col = "scheduled_at"
        if tab == 'archived': cursor_col = "updated_at"
        
        query += f" AND {cursor_col} {direction} %s"
        params.append(cursor)
        
    query += f" ORDER BY {order} LIMIT %s"
    params.append(limit + 1)
    
    rows = fast_query(query, params)
    has_more = len(rows) > limit
    items = rows[:limit]
    
    total_res = fast_query("SELECT COUNT(*) as count FROM chain_posts WHERE profile_id = %s AND deleted_at IS NULL", [profile_id])
    total = total_res[0]['count'] if total_res else 0
    
    # Cursor logic
    next_cursor = None
    if has_more and items:
        if tab == 'drafts': next_cursor = items[-1]['updated_at'].isoformat()
        elif tab == 'scheduled': next_cursor = items[-1]['scheduled_at'].isoformat()
        elif tab == 'archived': next_cursor = items[-1]['updated_at'].isoformat()
        else: next_cursor = items[-1]['created_at'].isoformat()
        
    return {
        "items": items,
        "total": total,
        "has_more": has_more,
        "next_cursor": next_cursor
    }

def get_managed_reels(profile_id, tab='newest', limit=20, cursor=None):
    """Lists reels for management with tab-based filtering and cursor pagination."""
    cols = _ensure_content_columns().get("reels", [])
    if not cols:
        cols = ["id", "caption", "created_at"]
    
    col_str = ", ".join(cols)
    query = f"SELECT {col_str} FROM chain_reels WHERE profile_id = %s AND deleted_at IS NULL"
    params = [profile_id]
    
    # Reels usually have similar management logic
    if tab == 'newest':
        query += " AND status = 'published' AND is_archived = FALSE"
        order = "created_at DESC"
    elif tab == 'archived':
        query += " AND is_archived = TRUE"
        order = "updated_at DESC"
    elif tab == 'pinned':
        query += " AND is_pinned = TRUE"
        order = "created_at DESC"
    else:
        query += " AND status = 'published' AND is_archived = FALSE"
        order = "created_at DESC"

    if cursor:
        query += " AND created_at < %s"
        params.append(cursor)
        
    query += f" ORDER BY {order} LIMIT %s"
    params.append(limit + 1)
    
    rows = fast_query(query, params)
    has_more = len(rows) > limit
    items = rows[:limit]
    
    total_res = fast_query("SELECT COUNT(*) as count FROM chain_reels WHERE profile_id = %s AND deleted_at IS NULL", [profile_id])
    total = total_res[0]['count'] if total_res else 0
    
    next_cursor = items[-1]['created_at'].isoformat() if has_more and items else None
    
    return {
        "items": items,
        "total": total,
        "has_more": has_more,
        "next_cursor": next_cursor
    }

def update_content_status(content_type, content_id, profile_id, **updates):
    """Updates status, visibility, archiving, or pinning for a post or reel."""
    table = "chain_posts" if content_type == 'post' else "chain_reels"
    
    valid_keys = ['status', 'visibility', 'is_archived', 'is_pinned', 'scheduled_at', 'body', 'caption']
    filtered_updates = {k: v for k, v in updates.items() if k in valid_keys}
    
    if not filtered_updates:
        return {"success": False, "error": "No valid updates provided."}
        
    filtered_updates['updated_at'] = 'now()'
    
    set_clause = ", ".join([f"{k} = %s" for k in filtered_updates.keys()])
    params = list(filtered_updates.values())
    params.extend([content_id, profile_id])
    
    try:
        res = write_query(
            f"UPDATE {table} SET {set_clause} WHERE id = %s AND profile_id = %s",
            params
        )
        return {"success": True} if res else {"success": False, "error": "Content not found or unauthorized."}
    except Exception as e:
        log_error(f"update_{content_type}_failed", error=str(e))
        return {"success": False, "error": str(e)}

def delete_content(content_type, content_id, profile_id, hard_delete=False):
    """Soft or hard deletes a post or reel."""
    table = "chain_posts" if content_type == 'post' else "chain_reels"
    try:
        if hard_delete:
            res = write_query(f"DELETE FROM {table} WHERE id = %s AND profile_id = %s", [content_id, profile_id])
        else:
            res = write_query(f"UPDATE {table} SET deleted_at = now(), updated_at = now() WHERE id = %s AND profile_id = %s", [content_id, profile_id])
        return {"success": True} if res else {"success": False, "error": "Content not found or unauthorized."}
    except Exception as e:
        return {"success": False, "error": str(e)}
