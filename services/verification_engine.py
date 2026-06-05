import uuid
from services.neon_service import fast_query, write_query
from services.media_storage_service import upload_media_file

def submit_verification(profile_id, file=None, request_type='creator', notes=None):
    """Submits a verification request."""
    if not file:
        return None, "Document file is required"

    # 1. Upload Document
    res, error = upload_media_file(file, bucket_name='chain-verification', profile_id=profile_id, upload_type='verification_doc')
    if error:
        # Fallback to chain-posts if bucket missing
        res, error = upload_media_file(file, bucket_name='chain-posts', profile_id=profile_id, upload_type='verification_doc')
        if error:
            return None, "setup_required: Storage bucket missing"

    request_id = str(uuid.uuid4())
    sql = """
        INSERT INTO chain_verification_requests (
            id, profile_id, request_type, status, document_url, storage_bucket, storage_path, notes, created_at
        ) VALUES (%s, %s, %s, 'pending', %s, %s, %s, %s, now())
        RETURNING id
    """
    params = (request_id, profile_id, request_type, res['public_url'], res['bucket'], res['file_path'], notes)
    try:
        write_query(sql, params)
        return request_id, None
    except Exception as e:
        print(f"[verification_engine] Failed to submit verification: {e}")
        return None, str(e)

def get_verification_status(profile_id):
    """Gets verification status for a profile."""
    sql = "SELECT * FROM chain_verification_requests WHERE profile_id = %s ORDER BY created_at DESC LIMIT 1"
    rows = fast_query(sql, (profile_id,))
    return rows[0] if rows else None

def list_pending_verifications(limit=50):
    """Lists pending verification requests for admin."""
    sql = "SELECT v.*, p.username FROM chain_verification_requests v JOIN chain_profiles p ON v.profile_id = p.id WHERE v.status = 'pending' ORDER BY v.created_at ASC LIMIT %s"
    return fast_query(sql, (limit,))

def update_verification_status(request_id, status, reviewer_profile_id=None, notes=None):
    """Updates verification status."""
    sql = """
        UPDATE chain_verification_requests 
        SET status = %s, reviewed_by_profile_id = %s, notes = %s, reviewed_at = now(), updated_at = now()
        WHERE id = %s
    """
    write_query(sql, (status, reviewer_profile_id, notes, request_id))
    
    # If approved, update profile
    if status == 'approved':
        req = fast_query("SELECT profile_id FROM chain_verification_requests WHERE id = %s", (request_id,))
        if req:
            write_query("UPDATE chain_profiles SET is_verified = TRUE, verified = TRUE WHERE id = %s", (req[0]['profile_id'],))
    
    return True
