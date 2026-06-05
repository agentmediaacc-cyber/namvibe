from flask import Blueprint, render_template, request, jsonify, session, current_app
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.neon_service import fast_query, write_query
from services.wallet_engine import get_wallet_summary
import json
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    """Main user dashboard page"""
    viewer = get_current_profile()
    if not viewer:
        return redirect(url_for('auth.login'))
    
    # Get real-time stats
    profile_id = viewer['id']
    
    stats = fast_query('''
        SELECT 
            (SELECT COUNT(*) FROM chain_follows WHERE following_profile_id = %s) as followers,
            (SELECT COUNT(*) FROM chain_follows WHERE follower_profile_id = %s) as following,
            (SELECT COUNT(*) FROM chain_posts WHERE profile_id = %s) as posts,
            (SELECT COALESCE(SUM(likes_count), 0) FROM chain_posts WHERE profile_id = %s) as 
total_likes,
            (SELECT COUNT(*) FROM chain_profile_views WHERE profile_id = %s AND viewed_at > 
NOW() - INTERVAL '7 days') as views_last_7d
    ''', [profile_id, profile_id, profile_id, profile_id, profile_id])[0]
    
    # Engagement rate = (likes + comments) / followers * 100
    engagement_rate = 0
    if stats['followers'] > 0:
        posts = fast_query('SELECT likes_count, comments_count FROM chain_posts WHERE profile_id = %s', [profile_id])
        total_engagement = sum((p.get('likes_count',0) or 0) + (p.get('comments_count',0) or 0) for p in posts)
        engagement_rate = round((total_engagement / stats['followers']) * 100, 1)
    
    # Mutual friends (profiles that follow both viewer and this profile - for own dashboard it's just followers)
    mutual = fast_query('''
        SELECT COUNT(*) FROM chain_follows f1
        JOIN chain_follows f2 ON f1.follower_profile_id = f2.following_profile_id
        WHERE f1.following_profile_id = %s AND f2.follower_profile_id = %s
    ''', [profile_id, profile_id])[0]['count']
    
    stats['engagement_rate'] = engagement_rate
    stats['mutual_friends'] = mutual
    
    # Wallet balance
    wallet = get_wallet_balance(profile_id)
    wallet_balance = wallet.get('balance', 0) if wallet else 0
    
    # Creator earnings (if creator mode)
    earnings = fast_query('''
        SELECT 
            COALESCE(SUM(amount), 0) as lifetime,
            COALESCE(SUM(CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN amount ELSE 0 
END), 0) as monthly
        FROM chain_wallet_transactions
        WHERE profile_id = %s AND type = 'earning'
    ''', [profile_id])[0]
    
    # Top performing post
    top_post = fast_query('''
        SELECT id, media_url, caption, likes_count, comments_count
        FROM chain_posts WHERE profile_id = %s
        ORDER BY (likes_count + comments_count) DESC LIMIT 1
    ''', [profile_id])
    top_post = top_post[0] if top_post else None
    
    # Badges (achievements)
    badges = []
    if viewer.get('is_verified'): badges.append({'icon': 'fa-check-circle', 'name': 
'Verified', 'color': 'blue'})
    if viewer.get('is_premium'): badges.append({'icon': 'fa-crown', 'name': 'Premium', 
'color': 'yellow'})
    if stats['followers'] > 1000: badges.append({'icon': 'fa-fire', 'name': 'Top Creator', 
'color': 'orange'})
    # Add more badge logic as needed
    
    # Privacy settings
    settings = fast_query('''
        SELECT profile_visibility, show_activity_status, allow_messages_from, 
allow_video_calls
        FROM chain_profiles WHERE id = %s
    ''', [profile_id])
    privacy = settings[0] if settings else {}
    
    # Dating profile if enabled
    dating_enabled = viewer.get('dating_mode_enabled', False)
    dating_profile = None
    if dating_enabled:
        dating_profile = fast_query('''
            SELECT looking_for, interests, height, zodiac, education, work, photos
            FROM chain_dating_profiles WHERE profile_id = %s
        ''', [profile_id])
        dating_profile = dating_profile[0] if dating_profile else {}
    
    # Marketplace items
    marketplace_items = fast_query('''
        SELECT id, title, price, media_url, is_digital
        FROM chain_marketplace_items WHERE profile_id = %s AND status = 'active'
        LIMIT 12
    ''', [profile_id])
    
    # AI Features data (empty placeholders)
    ai_suggestions = {
        'bio': "✨ AI can help improve your bio!",
        'caption': "Generate viral captions with AI"
    }
    
    return render_template('dashboard/complete_dashboard.html',
        profile=viewer,
        stats=stats,
        wallet_balance=wallet_balance,
        earnings=earnings,
        top_post=top_post,
        badges=badges,
        privacy=privacy,
        dating_enabled=dating_enabled,
        dating_profile=dating_profile,
        marketplace_items=marketplace_items,
        ai_suggestions=ai_suggestions
    )

@dashboard_bp.route('/follow/<profile_id>', methods=['POST'])
@login_required
def ajax_follow(profile_id):
    """AJAX follow/unfollow toggle"""
    viewer = get_current_profile()
    if not viewer or viewer['id'] == profile_id:
        return jsonify({'error': 'Invalid'}), 400
    
    existing = fast_query('SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s',
                          [viewer['id'], profile_id])
    if existing:
        write_query('DELETE FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s',
                    [viewer['id'], profile_id])
        following = False
    else:
        write_query('INSERT INTO chain_follows (follower_profile_id, following_profile_id, created_at) VALUES (%s, %s, NOW())',
                    [viewer['id'], profile_id])
        following = True
    
    new_count = fast_query('SELECT COUNT(*) as count FROM chain_follows WHERE following_profile_id = %s', [profile_id])[0]['count']
    return jsonify({'status': 'ok', 'following': following, 'followers_count': new_count})

@dashboard_bp.route('/send-gift', methods=['POST'])
@login_required
def send_gift():
    data = request.json
    sender = get_current_profile()
    recipient_id = data.get('recipient_id')
    amount = data.get('amount', 1)
    # Implement gift logic - deduct from wallet, add to recipient, record transaction
    return jsonify({'status': 'ok', 'message': f'Gift of {amount} sent!'})

@dashboard_bp.route('/update-privacy', methods=['POST'])
@login_required
def update_privacy():
    viewer = get_current_profile()
    data = request.json
    updates = {}
    if 'visibility' in data:
        updates['profile_visibility'] = data['visibility']
    if 'show_status' in data:
        updates['show_activity_status'] = data['show_status']
    if 'allow_messages' in data:
        updates['allow_messages_from'] = data['allow_messages']
    if updates:
        write_query('UPDATE chain_profiles SET {} WHERE id = %s'.format(', '.join(f"{k}=%s" 
for k in updates.keys())),
                    list(updates.values()) + [viewer['id']])
    return jsonify({'status': 'ok'})

@dashboard_bp.route('/ai-bio', methods=['POST'])
@login_required
def ai_bio_generator():
    """AI bio suggestion endpoint"""
    data = request.json
    interests = data.get('interests', '')
    # Mock AI response - integrate with real AI service later
    suggestions = [
        f"🚀 Building the future of {interests} | Creator | Live Streamer",
        f"✨ {interests} enthusiast sharing daily inspiration",
        f"💡 Helping you grow in {interests} - Join the journey"
    ]
    return jsonify({'suggestions': suggestions})

@dashboard_bp.route('/ai-caption', methods=['POST'])
@login_required
def ai_caption_writer():
    data = request.json
    topic = data.get('topic', '')
    # Mock AI response
    captions = [
        f"🔥 Dropping some {topic} vibes today! Who's with me?",
        f"✨ New {topic} alert! Double tap if you're ready",
        f"💯 The grind never stops. {topic} mode: ON"
    ]
    return jsonify({'captions': captions})

