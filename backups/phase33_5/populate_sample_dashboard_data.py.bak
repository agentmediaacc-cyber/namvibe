#!/usr/bin/env python3
from services.neon_service import write_query
from services.profile_service import get_current_profile
import random

def add_sample_posts(profile_id):
    for i in range(5):
        write_query("INSERT INTO chain_posts (profile_id, caption, media_url, created_at) 
VALUES (%s, %s, %s, NOW())",
                    [profile_id, f"Sample post {i+1}", "https://picsum.photos/400/400?random=" 
+ str(random.randint(1,1000))])
    print("Sample posts added.")

def add_sample_reels(profile_id):
    for i in range(3):
        write_query("INSERT INTO chain_reels (profile_id, caption, media_url, views_count, 
created_at) VALUES (%s, %s, %s, %s, NOW())",
                    [profile_id, f"Reel {i+1}", 
"https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4", 
random.randint(10,200)])
    print("Sample reels added.")

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        profile = get_current_profile()
        if profile:
            add_sample_posts(profile['id'])
            add_sample_reels(profile['id'])
        else:
            print("No user logged in. Run this after logging in.")
