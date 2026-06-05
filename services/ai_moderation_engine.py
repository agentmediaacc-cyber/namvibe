import re

# Simple heuristic moderation rules
BANNED_KEYWORDS = [
    r'scam', r'crypto.*invest', r'whatsapp\s*\d', r'telegram\s*@',
    r'offensive_word_1', r'offensive_word_2' # Placeholder for real list
]

def moderate_text(text):
    """Heuristic text moderation."""
    if not text:
        return "clean", 0
    
    score = 0
    text_lower = text.lower()
    
    # 1. Keyword check
    for pattern in BANNED_KEYWORDS:
        if re.search(pattern, text_lower):
            return "blocked", 100
            
    # 2. Link check (DM spam)
    links = re.findall(r'http[s]?://', text_lower)
    if len(links) > 2:
        return "warning", 50
        
    # 3. All caps check (harassment/shouting)
    if len(text) > 20 and text.isupper():
        score += 20
        
    if score >= 80:
        return "blocked", score
    if score >= 40:
        return "review_required", score
        
    return "clean", score

def moderate_caption(caption):
    return moderate_text(caption)

def moderate_message(body):
    return moderate_text(body)

def moderate_username(username):
    # Usernames shouldn't have links or extreme patterns
    return moderate_text(username)

def moderate_media_placeholder(media_url, type='image'):
    """Placeholder for future AI vision moderation (Cloudinary/AWS Rekognition/etc)."""
    return "clean", 0
