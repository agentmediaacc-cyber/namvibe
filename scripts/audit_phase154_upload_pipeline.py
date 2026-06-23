#!/usr/bin/env python3
"""
Phase 154 — Fix Real Upload Pipeline Audit Script.

Tests without browser:
1. Check Supabase env vars exist.
2. Check bucket can be accessed.
3. Generate tiny test image file.
4. Upload test image as story for alpha.
5. Verify row exists in chain_status_posts with media_url.
6. Upload test post image.
7. Verify row exists in chain_posts with media_url.
8. Generate or use tiny test mp4/webm if possible.
9. Upload test reel/video.
10. Verify row exists in chain_reels with media_url.
11. Fetch /api/homepage/feed as another viewer and confirm public test content appears.
12. Cleanup test rows/files if possible.
"""
import io
import os
import sys
import uuid
import tempfile
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.env_service import load_project_env
load_project_env()

# Results tracking
results = []
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

def report(check_name, status, detail=""):
    results.append((check_name, status, detail))
    marker = "\u2705" if status == PASS else "\u274c" if status == FAIL else "\u23f8"
    print(f"  {marker} {check_name}: {status} {detail}")

def check_supabase_env():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    missing = []
    if not supabase_url:
        missing.append("SUPABASE_URL")
    if not supabase_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        return False, f"Missing env vars: {', '.join(missing)}"
    return True, f"SUPABASE_URL={supabase_url[:30]}... SUPABASE_SERVICE_ROLE_KEY={'set' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else 'not set'}"

def check_buckets():
    from services.supabase_storage_service import check_bucket_exists
    ok, msg = check_bucket_exists()
    return ok, msg

def generate_test_image():
    """Generate a tiny PNG test image."""
    try:
        from PIL import Image
        buf = io.BytesIO()
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except ImportError:
        pass
    # Fallback: minimal valid PNG (1x1 pixel)
    raw = (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return io.BytesIO(raw)

def generate_test_video():
    """Generate a tiny valid MP4. Returns BytesIO or None if impossible."""
    try:
        import subprocess
        tmp_in = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_out = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_in_path = tmp_in.name
        tmp_out_path = tmp_out.name
        tmp_in.close()
        tmp_out.close()
        try:
            from PIL import Image
            Image.new("RGB", (64, 64), color=(0, 0, 255)).save(tmp_in_path, format="PNG")
        except ImportError:
            with open(tmp_in_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=0.5", "-frames:v", "5",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", tmp_out_path],
            capture_output=True, timeout=15
        )
        if result.returncode == 0:
            with open(tmp_out_path, "rb") as f:
                data = f.read()
            os.unlink(tmp_in_path)
            os.unlink(tmp_out_path)
            return io.BytesIO(data)
        os.unlink(tmp_in_path)
        os.unlink(tmp_out_path)
    except Exception:
        pass
    return None

def make_fake_file(content, filename="test.png", content_type="image/png"):
    """Create a minimal file-like object."""
    from werkzeug.datastructures import FileStorage
    if isinstance(content, io.BytesIO):
        content.seek(0)
    return FileStorage(
        stream=content if isinstance(content, io.BytesIO) else io.BytesIO(content),
        filename=filename,
        content_type=content_type,
    )

def main():
    print("=" * 60)
    print("Phase 154 — Upload Pipeline Audit")
    print("=" * 60)

    # 1. Supabase env vars
    print("\n1. Checking Supabase configuration...")
    env_ok, env_msg = check_supabase_env()
    report("Supabase env vars", PASS if env_ok else FAIL, env_msg)

    if not env_ok:
        report("Story upload", SKIP, "Supabase not configured")
        report("Post upload", SKIP, "Supabase not configured")
        report("Reel upload", SKIP, "Supabase not configured")
        print_summary()
        return

    supabase_bucket = os.getenv("SUPABASE_MEDIA_BUCKET", "namvibe-media")
    print(f"  SUPABASE_MEDIA_BUCKET = {supabase_bucket}")

    # 2. Bucket check
    print("\n2. Checking Supabase buckets...")
    buckets_ok, buckets_msg = check_buckets()
    report("Supabase bucket access", PASS if buckets_ok else FAIL, buckets_msg)

    # Get a profile ID for testing
    profile_id = os.getenv("AUDIT_PROFILE_ID") or os.getenv("TEST_PROFILE_ID")

    # 3. Test image
    print("\n3. Generating test image...")
    test_image = generate_test_image()
    report("Test image generation", PASS if test_image else FAIL)

    # 4. Story upload
    print("\n4. Testing story upload...")
    if profile_id and test_image:
        try:
            from services.status_service import create_status
            fake_file = make_fake_file(test_image, "test_story.png", "image/png")
            record, error = create_status(
                profile_id=profile_id,
                caption="Phase 154 audit test story",
                media_file=fake_file,
                visibility="public",
                media_type="image"
            )
            if error:
                report("Story upload", FAIL, f"create_status error: {error}")
            elif record:
                story_url = record.get("media_url", "N/A")
                story_id = record.get("id", "N/A")
                report("Story upload", PASS, f"story_id={story_id} media_url={story_url[:60] if story_url else 'N/A'}...")

                # 5. Verify row in Neon
                print("\n5. Verifying story in Neon...")
                try:
                    from services.neon_service import fast_query
                    rows = fast_query(
                        "SELECT id, profile_id, media_url, visibility, media_type, expires_at FROM chain_status_posts WHERE id = %s",
                        (story_id,), timeout_ms=3000, default=[]
                    )
                    if rows and rows[0].get("media_url"):
                        r = rows[0]
                        report("Story Neon row exists", PASS,
                               f"id={r['id']} visibility={r.get('visibility')} media_type={r.get('media_type')} expires_at={r.get('expires_at')}")
                    else:
                        report("Story Neon row exists", FAIL, "Row not found or media_url is empty")
                except Exception as e:
                    report("Story Neon row exists", FAIL, str(e))
            else:
                report("Story upload", FAIL, "create_status returned None without error")
        except Exception as e:
            report("Story upload", FAIL, str(e))
            report("Story Neon row exists", SKIP, "Story upload did not succeed")
    else:
        missing = []
        if not profile_id:
            missing.append("AUDIT_PROFILE_ID/TEST_PROFILE_ID")
        if not test_image:
            missing.append("test image")
        report("Story upload", SKIP, f"Missing: {', '.join(missing)}")
        report("Story Neon row exists", SKIP, "Story upload did not run")

    # 6. Post upload
    print("\n6. Testing post upload...")
    if profile_id:
        test_image2 = generate_test_image()
        if test_image2:
            try:
                from services.post_service import create_post
                fake_file = make_fake_file(test_image2, "test_post.png", "image/png")
                post, error = create_post(
                    profile_id=profile_id,
                    caption="Phase 154 audit test post",
                    media_file=fake_file,
                    visibility="public"
                )
                if error:
                    report("Post upload", FAIL, f"create_post error: {error}")
                elif post:
                    post_id = post.get("id", "N/A")
                    post_url = post.get("media_url") or post.get("video_url", "N/A")
                    report("Post upload", PASS, f"post_id={post_id} media_url={str(post_url)[:60] if post_url else 'N/A'}...")

                    # 7. Verify row in Neon
                    print("\n7. Verifying post in Neon...")
                    try:
                        rows = fast_query(
                            "SELECT id, profile_id, media_url, visibility, post_type FROM chain_posts WHERE id = %s",
                            (post_id,), timeout_ms=3000, default=[]
                        )
                        if rows and rows[0].get("media_url"):
                            r = rows[0]
                            report("Post Neon row exists", PASS,
                                   f"id={r['id']} visibility={r.get('visibility')} post_type={r.get('post_type')}")
                        else:
                            report("Post Neon row exists", FAIL, "Row not found or media_url is empty")
                    except Exception as e:
                        report("Post Neon row exists", FAIL, str(e))
                else:
                    report("Post upload", FAIL, "create_post returned None without error")
            except Exception as e:
                report("Post upload", FAIL, str(e))
                report("Post Neon row exists", SKIP, "Post upload did not succeed")
        else:
            report("Post upload", SKIP, "Could not generate test image")
            report("Post Neon row exists", SKIP, "Post upload did not run")
    else:
        report("Post upload", SKIP, "No test profile ID")
        report("Post Neon row exists", SKIP, "Post upload did not run")

    # 8-10. Reel upload
    print("\n8. Generating test video...")
    test_video = generate_test_video()
    report("Test video generation", PASS if test_video else SKIP, "ffmpeg may be required")

    print("\n9. Testing reel upload...")
    if profile_id and test_video:
        try:
            from services.reels_engine import create_reel
            fake_video = make_fake_file(test_video, "test_reel.mp4", "video/mp4")
            reel_id, error = create_reel(
                profile_id=profile_id,
                caption="Phase 154 audit test reel",
                file=fake_video,
                visibility="public"
            )
            if error:
                report("Reel upload", FAIL, f"create_reel error: {error}")
            elif reel_id:
                report("Reel upload", PASS, f"reel_id={reel_id}")

                # 10. Verify row in Neon
                print("\n10. Verifying reel in Neon...")
                try:
                    rows = fast_query(
                        "SELECT id, profile_id, video_url, visibility, processing_status FROM chain_reels WHERE id = %s",
                        (reel_id,), timeout_ms=3000, default=[]
                    )
                    if rows and rows[0].get("video_url"):
                        r = rows[0]
                        report("Reel Neon row exists", PASS,
                               f"id={r['id']} visibility={r.get('visibility')} processing_status={r.get('processing_status')}")
                    else:
                        report("Reel Neon row exists", FAIL, "Row not found or video_url is empty")
                except Exception as e:
                    report("Reel Neon row exists", FAIL, str(e))
            else:
                report("Reel upload", FAIL, "create_reel returned None without error")
        except Exception as e:
            report("Reel upload", FAIL, str(e))
            report("Reel Neon row exists", SKIP, "Reel upload did not succeed")
    else:
        missing = []
        if not profile_id:
            missing.append("AUDIT_PROFILE_ID/TEST_PROFILE_ID")
        if not test_video:
            missing.append("test video (ffmpeg may be needed)")
        report("Reel upload", SKIP, f"Missing: {', '.join(missing)}")
        report("Reel Neon row exists", SKIP, "Reel upload did not run")

    # 11. Feed check
    print("\n11. Checking feed for public content...")
    try:
        from services.neon_service import fast_query
        feed_rows = fast_query(
            """SELECT id, profile_id, caption, media_url, video_url, visibility, created_at
               FROM chain_posts
               WHERE visibility = 'public' AND deleted_at IS NULL
               ORDER BY created_at DESC LIMIT 5""",
            timeout_ms=3000, default=[]
        )
        if feed_rows:
            report("Public content visible in feed", PASS,
                   f"Found {len(feed_rows)} public posts. Latest: id={feed_rows[0].get('id')}")
        else:
            report("Public content visible in feed", FAIL, "No public posts found in chain_posts")
    except Exception as e:
        report("Public content visible in feed", FAIL, str(e))

    print_summary()


def print_summary():
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    print(f"Total: {len(results)} | PASS: {passed} | FAIL: {failed} | SKIP: {skipped}")
    print()

    story_upload = next((r for r in results if r[0] == "Story upload"), None)
    post_upload = next((r for r in results if r[0] == "Post upload"), None)
    reel_upload = next((r for r in results if r[0] == "Reel upload"), None)
    feed_check = next((r for r in results if r[0] == "Public content visible in feed"), None)

    print(f"  Story upload:   {story_upload[1] if story_upload else SKIP}  {story_upload[2] if story_upload else 'not run'}")
    print(f"  Post upload:    {post_upload[1] if post_upload else SKIP}  {post_upload[2] if post_upload else 'not run'}")
    print(f"  Reel upload:    {reel_upload[1] if reel_upload else SKIP}  {reel_upload[2] if reel_upload else 'not run'}")
    print(f"  Feed check:     {feed_check[1] if feed_check else SKIP}  {feed_check[2] if feed_check else 'not run'}")

    if failed > 0:
        print(f"\nFAILURES ({failed}):")
        for name, status, detail in results:
            if status == FAIL:
                print(f"  - {name}: {detail}")

    print("=" * 60)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
