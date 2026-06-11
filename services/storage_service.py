import os
import uuid
import werkzeug.utils
from utils.supabase_client import get_supabase_admin, SUPABASE_URL
from services.media_storage_service import record_media_upload_metadata
from services.supabase_storage_router import (
    upload_avatar as routed_avatar_upload,
    upload_cover as routed_cover_upload,
    upload_marketplace_image,
    upload_message_attachment,
    upload_story_media as routed_story_upload,
    upload_live_thumbnail,
)

# Configuration
ALLOWED_EXTENSIONS = {
    'images': {'jpg', 'jpeg', 'png', 'webp'},
    'audio': {'mp3', 'wav', 'm4a'},
    'video': {'mp4', 'mov', 'webm'},
    'documents': {'jpg', 'jpeg', 'png', 'pdf'}
}

MAX_FILE_SIZES = {
    'avatar': 5 * 1024 * 1024,      # 5MB
    'cover': 10 * 1024 * 1024,      # 10MB
    'music': 50 * 1024 * 1024,      # 50MB
    'video': 250 * 1024 * 1024,     # 250MB
    'proof': 10 * 1024 * 1024,      # 10MB
    'verification': 10 * 1024 * 1024 # 10MB
}

def get_storage_client():
    return get_supabase_admin().storage

def allowed_file(filename, category):
    if category not in ALLOWED_EXTENSIONS:
        return False
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS[category]

def sanitize_filename(filename):
    return werkzeug.utils.secure_filename(filename)

def build_storage_path(profile_id, upload_type, filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    unique_name = f"{uuid.uuid4()}.{ext}" if ext else str(uuid.uuid4())
    return f"{profile_id}/{upload_type}/{unique_name}"

def record_media_upload(profile_id, upload_type, bucket_name, file_path, public_url, mime_type, file_size, original_filename):
    return record_media_upload_metadata(
        profile_id=profile_id,
        upload_type=upload_type,
        bucket_name=bucket_name,
        file_path=file_path,
        public_url=public_url,
        mime_type=mime_type,
        file_size=file_size,
        original_filename=original_filename,
    )

def upload_file_to_bucket(file_obj, bucket_name, profile_id, upload_type, public=True):
    """
    General purpose upload function.
    file_obj: werkzeug.datastructures.FileStorage or similar
    """
    if not file_obj:
        return None, "No file provided"

    filename = sanitize_filename(file_obj.filename)
    
    # Check category-based extensions
    category = 'images'
    if upload_type == 'music_track':
        category = 'audio'
    elif upload_type == 'video':
        category = 'video'
    elif upload_type in ['payment_proof', 'verification_doc']:
        category = 'documents'
    
    if not allowed_file(filename, category):
        return None, f"File type not allowed for {category}"

    # Check size
    file_obj.seek(0, os.SEEK_END)
    file_size = file_obj.tell()
    file_obj.seek(0)
    
    size_limit_key = upload_type
    if upload_type == 'marketplace_media': size_limit_key = 'cover' # Default to cover size for marketplace
    if upload_type == 'payment_proof': size_limit_key = 'proof'
    if upload_type == 'verification_doc': size_limit_key = 'verification'
    
    limit = MAX_FILE_SIZES.get(size_limit_key, 10 * 1024 * 1024)
    if file_size > limit:
        return None, f"File too large. Max allowed: {limit // (1024*1024)}MB"

    storage_path = build_storage_path(profile_id, upload_type, filename)
    mime_type = file_obj.content_type
    
    routed_type = {
        "chain-avatars": "avatars",
        "chain-covers": "covers",
        "chain-marketplace": "marketplace",
        "chain-messages": "messages",
        "chain-stories": "stories",
        "chain-status": "stories",
        "chain-live": "live",
    }.get(bucket_name)
    if routed_type:
        from services.supabase_storage_router import upload_file
        result, error = upload_file(file_obj, routed_type, profile_id, public=public)
        if error:
            return None, error
        upload_id = record_media_upload(
            profile_id=profile_id,
            upload_type=upload_type,
            bucket_name=result["bucket"],
            file_path=result["path"],
            public_url=result["url"],
            mime_type=result["mime_type"],
            file_size=result["size_bytes"],
            original_filename=filename,
        )
        return {**result, "upload_id": upload_id}, None

    try:
        storage = get_storage_client()
        # Read file content
        file_data = file_obj.read()
        
        storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_data,
            file_options={"content-type": mime_type}
        )
        
        public_url = None
        if public:
            # Construct public URL manually or use storage.get_public_url
            # storage.get_public_url(bucket_name, storage_path)
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{storage_path}"
        
        upload_id = record_media_upload(
            profile_id=profile_id,
            upload_type=upload_type,
            bucket_name=bucket_name,
            file_path=storage_path,
            public_url=public_url,
            mime_type=mime_type,
            file_size=file_size,
            original_filename=filename
        )
        
        return {
            "upload_id": upload_id,
            "public_url": public_url,
            "file_path": storage_path,
            "bucket": bucket_name
        }, None
        
    except Exception as e:
        return None, str(e)

def upload_avatar(profile_id, file):
    result, error = routed_avatar_upload(file, profile_id)
    if error:
        return None, error
    upload_id = record_media_upload(profile_id, "avatar", result["bucket"], result["path"], result["url"], result["mime_type"], result["size_bytes"], file.filename)
    return {**result, "upload_id": upload_id}, None

def upload_cover(profile_id, file):
    result, error = routed_cover_upload(file, profile_id)
    if error:
        return None, error
    upload_id = record_media_upload(profile_id, "cover", result["bucket"], result["path"], result["url"], result["mime_type"], result["size_bytes"], file.filename)
    return {**result, "upload_id": upload_id}, None

def upload_marketplace_media(profile_id, file):
    result, error = upload_marketplace_image(file, profile_id)
    if error:
        return None, error
    upload_id = record_media_upload(profile_id, "marketplace_media", result["bucket"], result["path"], result["url"], result["mime_type"], result["size_bytes"], file.filename)
    return {**result, "upload_id": upload_id}, None

def upload_music_track(profile_id, file):
    return upload_file_to_bucket(file, 'chain-music', profile_id, 'music_track', public=True)

def upload_payment_proof(profile_id, file):
    # Payment proofs are private
    return upload_file_to_bucket(file, 'chain-payment-proofs', profile_id, 'payment_proof', public=False)

def upload_verification_file(profile_id, file, upload_type='verification_doc'):
    # Verification docs are private
    return upload_file_to_bucket(file, 'chain-verifications', profile_id, upload_type, public=False)

def upload_chat_media(profile_id, file):
    result, error = upload_message_attachment(file, profile_id)
    if error:
        return None, error
    upload_id = record_media_upload(profile_id, "chat_media", result["bucket"], result["path"], result["url"], result["mime_type"], result["size_bytes"], file.filename)
    return {**result, "upload_id": upload_id}, None

def upload_status_media(profile_id, file):
    result, error = routed_story_upload(file, profile_id)
    if error:
        return None, error
    upload_id = record_media_upload(profile_id, "status_media", result["bucket"], result["path"], result["url"], result["mime_type"], result["size_bytes"], file.filename)
    return {**result, "upload_id": upload_id}, None

def upload_story_media(profile_id, file):
    return upload_status_media(profile_id, file)

def upload_live_music(profile_id, file):
    return upload_file_to_bucket(file, 'chain-music', profile_id, 'live_music', public=True)

def upload_live_cover(profile_id, file):
    result, error = upload_live_thumbnail(file, profile_id)
    if error:
        return None, error
    upload_id = record_media_upload(profile_id, "live_cover", result["bucket"], result["path"], result["url"], result["mime_type"], result["size_bytes"], file.filename)
    return {**result, "upload_id": upload_id}, None
