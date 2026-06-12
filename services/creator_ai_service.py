from datetime import datetime, timezone, timedelta
import random

def get_caption_suggestions(content_type, topic):
    """
    Simulates AI caption generation based on content type and topic.
    In a real app, this would call OpenAI or a similar LLM.
    """
    templates = {
        "reel": [
            f"POV: You found the best {topic} in Windhoek! ✨",
            f"This {topic} is a total game changer. Who else needs this? 👇",
            f"Just another day of absolute {topic} vibes. #NamVibeCreators",
            f"Wait for the end... {topic} level 100! 🚀"
        ],
        "live": [
            f"Going LIVE! Talking all things {topic}. Join NamVibe! ❤️",
            f"Exclusive {topic} session. Q&A starts now! 🎤",
            f"Special guest joining for a {topic} deep dive. Don't miss out!",
            f"Real talk about {topic}. Grab your virtual front row seat. 💎"
        ]
    }
    
    selected = templates.get(content_type, ["Check this out! #NamVibe"])
    return random.sample(selected, min(3, len(selected)))

def generate_trending_hashtags(topic):
    """Suggests optimized hashtags for discovery"""
    base = ["#NamVibe", "#NamVibePremium", "#CreatorEconomy"]
    topic_tags = [f"#{topic.replace(' ', '')}", f"#{topic.split()[0]}Vibes"]
    trending = ["#TrendingNow", "#ExplorePage", "#ViralCreator"]
    
    return list(set(base + topic_tags + trending))[:8]

def suggest_best_posting_time(profile_id):
    """
    Analyzes historical engagement to suggest the best time to post.
    Simplified: Returns a time 3 hours from now.
    """
    now = datetime.now(timezone.utc)
    suggested = now + timedelta(hours=3)
    return {
        "suggested_time": suggested.isoformat(),
        "reason": "Highest audience activity predicted for your timezone."
    }

def get_stream_title_suggestions(category):
    """AI title ideas for live rooms"""
    titles = [
        f"The {category} Deep Dive",
        f"Late Night {category} Vibing",
        f"Unfiltered {category} Chat",
        f"Exclusive: {category} Secrets Revealed"
    ]
    return titles
