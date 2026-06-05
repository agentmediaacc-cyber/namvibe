import os
import uuid
from abc import ABC, abstractmethod
from utils.supabase_client import get_supabase_admin, SUPABASE_URL

class MediaStorageProvider(ABC):
    @abstractmethod
    def upload(self, file_obj, bucket, path, mime_type):
        pass

    @abstractmethod
    def get_url(self, bucket, path):
        pass

    @abstractmethod
    def delete(self, bucket, path):
        pass

class SupabaseStorageProvider(MediaStorageProvider):
    def __init__(self):
        self.client = get_supabase_admin().storage
        self.cdn_base = os.getenv("MEDIA_CDN_URL")

    def upload(self, file_obj, bucket, path, mime_type):
        res = self.client.from_(bucket).upload(
            path=path,
            file=file_obj,
            file_options={"content-type": mime_type}
        )
        return res

    def get_url(self, bucket, path):
        if self.cdn_base:
            return f"{self.cdn_base.rstrip('/')}/{bucket}/{path}"
        return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"

    def delete(self, bucket, path):
        return self.client.from_(bucket).remove([path])

class CloudflareR2Provider(MediaStorageProvider):
    # Stub for future implementation
    def upload(self, file_obj, bucket, path, mime_type):
        raise NotImplementedError("Cloudflare R2 support coming soon")
    
    def get_url(self, bucket, path):
        return f"https://cdn.chain.social/{bucket}/{path}"

    def delete(self, bucket, path):
        pass

# Factory
def get_storage_provider():
    provider_type = os.getenv("MEDIA_STORAGE_PROVIDER", "supabase").lower()
    if provider_type == "supabase":
        return SupabaseStorageProvider()
    elif provider_type == "r2":
        return CloudflareR2Provider()
    return SupabaseStorageProvider()

def build_unique_path(profile_id, category, filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    unique_id = uuid.uuid4().hex
    return f"{profile_id}/{category}/{unique_id}.{ext}" if ext else f"{profile_id}/{category}/{unique_id}"
