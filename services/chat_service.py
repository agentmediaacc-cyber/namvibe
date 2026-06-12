from datetime import datetime, timezone
from utils.supabase_client import get_supabase_admin
from services.profile_service import get_current_profile, get_profile_by_id
from services.supabase_safe import safe_insert, safe_select, safe_update, table_exists
from services.storage_service import upload_chat_media

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def get_or_create_direct_conversation(profile_a, profile_b):
    """
    profile_a: ID of the current user
    profile_b: ID of the target user
    """
    if profile_a == profile_b:
        return None, "You cannot chat with yourself."

    # Check for existing direct conversation
    supabase = get_supabase_admin()
    existing = (
        supabase.table("chain_conversations")
        .select("id")
        .eq("conversation_type", "direct")
        .execute()
        .data
    )
    
    # We need to check members for these conversations
    # This is slightly complex in pure SQL/Postgrest without a join
    # but we can filter by members
    
    # Simpler: find if there's a conversation where BOTH are members
    res = supabase.rpc("find_direct_conversation", {"p1": profile_a, "p2": profile_b}).execute()
    if res.data:
        convo_id = res.data
        rows = safe_select("chain_conversations", filters={"id": convo_id}, limit=1)
        return rows[0] if rows else None, None

    # If RPC fails or not exists, fallback to manual check
    # For now, let's just create one if not found
    convo_payload = {
        "conversation_type": "direct",
        "created_by": profile_a,
        "created_at": _utcnow_iso()
    }
    new_convo = safe_insert("chain_conversations", convo_payload)
    if not new_convo:
        return None, "Failed to create conversation."
    
    convo_id = new_convo[0]['id']
    
    # Add both members
    safe_insert("chain_conversation_members", {"conversation_id": convo_id, "profile_id": profile_a, "role": "owner"})
    safe_insert("chain_conversation_members", {"conversation_id": convo_id, "profile_id": profile_b, "role": "member"})
    
    return new_convo[0], None

def list_conversations(profile_id):
    supabase = get_supabase_admin()
    # Get all conversation IDs where profile_id is a member
    member_rows = safe_select("chain_conversation_members", filters={"profile_id": profile_id})
    convo_ids = [m['conversation_id'] for m in member_rows]
    
    if not convo_ids:
        return []
    
    convos = safe_select("chain_conversations", filters={"id": ("in", convo_ids)}, order_by="last_message_at", desc=True)
    
    # Enrich with other member info for direct chats
    for convo in convos:
        if convo['conversation_type'] == 'direct':
            other_member = (
                supabase.table("chain_conversation_members")
                .select("profile_id")
                .eq("conversation_id", convo['id'])
                .neq("profile_id", profile_id)
                .limit(1)
                .execute()
                .data
            )
            if other_member:
                convo['other_profile'] = get_profile_by_id(other_member[0]['profile_id'])
                convo['display_title'] = convo['other_profile'].get('full_name') if convo['other_profile'] else "NamVibe Member"
        else:
            convo['display_title'] = convo.get('title') or "Group Chat"
            
    return convos

def list_messages(conversation_id, profile_id):
    # Verify membership
    membership = safe_select("chain_conversation_members", filters={"conversation_id": conversation_id, "profile_id": profile_id}, limit=1)
    if not membership:
        return None, "Access denied."
    
    messages = safe_select("chain_messages", filters={"conversation_id": conversation_id}, limit=100, order_by="created_at", desc=False)
    return messages, None

def send_text_message(conversation_id, sender_profile_id, body):
    if not body or not body.strip():
        return None, "Message cannot be empty."
    
    payload = {
        "conversation_id": conversation_id,
        "sender_profile_id": sender_profile_id,
        "message_type": "text",
        "body": body.strip(),
        "created_at": _utcnow_iso()
    }
    new_msg = safe_insert("chain_messages", payload)
    if new_msg:
        # Update conversation last message
        safe_update("chain_conversations", {"last_message": body.strip(), "last_message_at": _utcnow_iso()}, eq={"id": conversation_id})
        return new_msg[0], None
    return None, "Failed to send message."

def send_media_message(conversation_id, sender_profile_id, file):
    if not file:
        return None, "No file provided."
    
    res, err = upload_chat_media(sender_profile_id, file)
    if not res:
        return None, f"Upload failed: {err}"
    
    payload = {
        "conversation_id": conversation_id,
        "sender_profile_id": sender_profile_id,
        "message_type": "image", # Should ideally detect from mime type
        "body": f"Sent a {res.get('upload_type', 'media')}",
        "media_upload_id": res['upload_id'],
        "media_url": res['public_url'],
        "created_at": _utcnow_iso()
    }
    # Simple mime detection
    if 'video' in (res.get('mime_type') or ''):
        payload['message_type'] = 'video'
    elif 'audio' in (res.get('mime_type') or ''):
        payload['message_type'] = 'audio'
        
    new_msg = safe_insert("chain_messages", payload)
    if new_msg:
        safe_update("chain_conversations", {"last_message": "Sent a media file", "last_message_at": _utcnow_iso()}, eq={"id": conversation_id})
        return new_msg[0], None
    return None, "Failed to send media message."

def mark_messages_read(conversation_id, profile_id):
    supabase = get_supabase_admin()
    # Mark all messages in this conversation as read, except those sent by profile_id
    supabase.table("chain_messages").update({"is_read": True}).eq("conversation_id", conversation_id).neq("sender_profile_id", profile_id).execute()
    return True
