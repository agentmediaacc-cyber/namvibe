import os
from utils.supabase_client import SUPABASE_URL

def build_public_media_url(path, bucket='chain-posts'):
    """Builds a CDN-ready public URL for media."""
    if not path: return None
    if path.startswith(('http://', 'https://')): return path
    
    # Placeholder for future CDN (Cloudflare/Bunny/etc)
    # CDN_DOMAIN = os.getenv("CDN_DOMAIN")
    # if CDN_DOMAIN:
    #     return f"https://{CDN_DOMAIN}/{bucket}/{path}"
        
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"

def build_signed_media_url(path, bucket='chain-posts', expires_in=3600):
    """Placeholder for future signed URL support."""
    return build_public_media_url(path, bucket)

def optimize_image_url(url, width=None, height=None, quality=80):
    """Placeholder for image optimization (e.g. via ImgProxy or Supabase Image Transformation)."""
    if not url: return None
    # If using Supabase Image Transformation:
    # return f"{url}?width={width}&height={height}&quality={quality}" if width else url
    return url

def optimize_video_url(url):
    """Placeholder for HLS/DASH or video optimization."""
    return url
