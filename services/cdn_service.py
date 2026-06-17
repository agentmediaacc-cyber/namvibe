import os
from utils.supabase_client import SUPABASE_URL

def _cdn_domain():
    return os.getenv("CDN_DOMAIN") or os.getenv("SUPABASE_URL") or SUPABASE_URL

def build_public_media_url(path, bucket='chain-posts'):
    """Builds a CDN-ready public URL for media."""
    if not path: return None
    if path.startswith(('http://', 'https://')): return path
    domain = _cdn_domain()
    return f"{domain}/storage/v1/object/public/{bucket}/{path}"

def build_signed_media_url(path, bucket='chain-posts', expires_in=3600):
    """Builds a URL with a cache-busting timestamp for CDN invalidation."""
    url = build_public_media_url(path, bucket)
    import time
    return f"{url}?_={int(time.time())}"

def optimize_image_url(url, width=None, height=None, quality=80):
    """Appends Supabase image transformation params if supported."""
    if not url: return None
    if width or height:
        params = []
        if width: params.append(f"width={width}")
        if height: params.append(f"height={height}")
        if quality and quality != 80: params.append(f"quality={quality}")
        return f"{url}?{'&'.join(params)}" if params else url
    return url

def optimize_video_url(url):
    """Returns the original URL; HLS transcoding requires async job."""
    return url
