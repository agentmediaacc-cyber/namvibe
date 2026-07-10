-- Phase: Configuration Tables — all UI config from DB instead of hardcoded

-- 1. Live Categories (replaces static JS CATEGORIES array)
CREATE TABLE IF NOT EXISTS chain_live_categories (
    id serial PRIMARY KEY,
    slug text UNIQUE NOT NULL,
    label text NOT NULL,
    icon text DEFAULT '',
    is_live boolean DEFAULT false,
    sort_order integer DEFAULT 0,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

INSERT INTO chain_live_categories (slug, label, icon, is_live, sort_order) VALUES
    ('all', 'All', '🔥', false, 0),
    ('friends', 'Friends', '👥', true, 1),
    ('featured', 'Featured', '⭐', true, 2),
    ('trending', 'Trending', '📈', true, 3),
    ('music', 'Music', '🎵', false, 4),
    ('gaming', 'Gaming', '🎮', false, 5),
    ('business', 'Business', '💼', false, 6),
    ('shopping', 'Shopping', '🛍️', false, 7),
    ('church', 'Church', '⛪', false, 8),
    ('education', 'Education', '📚', false, 9),
    ('government', 'Government', '🏛️', false, 10),
    ('health', 'Health', '🏥', false, 11),
    ('sports', 'Sports', '⚽', false, 12),
    ('entertainment', 'Entertainment', '🎭', false, 13),
    ('new', 'New Creators', '🌟', false, 14),
    ('scheduled', 'Scheduled', '📅', false, 15)
ON CONFLICT (slug) DO NOTHING;

-- 2. Gift Tiers (replaces static TIERS array + gift tier IDs)
CREATE TABLE IF NOT EXISTS chain_gift_tiers (
    id serial PRIMARY KEY,
    slug text UNIQUE NOT NULL,
    label text NOT NULL,
    min_nvc numeric DEFAULT 0,
    max_nvc numeric DEFAULT 0,
    color text DEFAULT '#cccccc',
    sort_order integer DEFAULT 0
);

INSERT INTO chain_gift_tiers (slug, label, min_nvc, max_nvc, color, sort_order) VALUES
    ('bronze', 'Bronze', 1, 10, '#cd7f32', 1),
    ('silver', 'Silver', 10, 50, '#c0c0c0', 2),
    ('gold', 'Gold', 50, 200, '#ffd700', 3),
    ('diamond', 'Diamond', 200, 1000, '#00ffff', 4),
    ('legendary', 'Legendary', 1000, 999999, '#ff1493', 5)
ON CONFLICT (slug) DO NOTHING;

-- 3. Gift Catalog (replaces static GIFTS array)
CREATE TABLE IF NOT EXISTS chain_gift_catalog (
    id serial PRIMARY KEY,
    emoji text NOT NULL,
    name text NOT NULL,
    price_nvc numeric NOT NULL DEFAULT 1,
    tier_slug text REFERENCES chain_gift_tiers(slug),
    is_premium boolean DEFAULT false,
    is_active boolean DEFAULT true,
    sort_order integer DEFAULT 0
);

INSERT INTO chain_gift_catalog (emoji, name, price_nvc, tier_slug, is_premium, sort_order) VALUES
    ('❤️', 'Heart', 1, 'bronze', false, 1),
    ('👍', 'Like', 1, 'bronze', false, 2),
    ('👏', 'Clap', 2, 'bronze', false, 3),
    ('🎉', 'Celebration', 2, 'bronze', false, 4),
    ('🔥', 'Fire', 3, 'bronze', false, 5),
    ('😍', 'Love Eyes', 3, 'bronze', false, 6),
    ('💯', '100', 3, 'bronze', false, 7),
    ('😂', 'LOL', 4, 'bronze', false, 8),
    ('🎊', 'Party', 5, 'bronze', false, 9),
    ('💪', 'Muscle', 5, 'bronze', false, 10),
    ('🌟', 'Star', 5, 'bronze', false, 11),
    ('👑', 'Crown', 8, 'bronze', false, 12),
    ('⭐', 'Gold Star', 10, 'silver', false, 13),
    ('🌈', 'Rainbow', 12, 'silver', false, 14),
    ('🦋', 'Butterfly', 15, 'silver', false, 15),
    ('💎', 'Diamond', 20, 'silver', false, 16),
    ('🌹', 'Rose', 20, 'silver', false, 17),
    ('🎸', 'Guitar', 25, 'silver', false, 18),
    ('🚀', 'Rocket', 30, 'silver', false, 19),
    ('🎤', 'Mic Drop', 35, 'silver', false, 20),
    ('🏆', 'Trophy', 40, 'silver', false, 21),
    ('🕊️', 'Dove', 45, 'silver', false, 22),
    ('🌺', 'Hibiscus', 50, 'gold', false, 23),
    ('🎭', 'Theater', 55, 'gold', false, 24),
    ('🎹', 'Piano', 60, 'gold', false, 25),
    ('🌊', 'Wave', 65, 'gold', false, 26),
    ('🎨', 'Palette', 70, 'gold', false, 27),
    ('🦅', 'Eagle', 75, 'gold', false, 28),
    ('🌋', 'Volcano', 80, 'gold', false, 29),
    ('🎆', 'Fireworks', 85, 'gold', false, 30),
    ('🗿', 'Moai', 90, 'gold', false, 31),
    ('🛸', 'UFO', 95, 'gold', false, 32),
    ('🦄', 'Unicorn', 100, 'gold', false, 33),
    ('🐉', 'Dragon', 120, 'gold', false, 34),
    ('🌌', 'Galaxy', 150, 'gold', false, 35),
    ('🤖', 'Robot', 180, 'gold', false, 36),
    ('💫', 'Shooting Star', 200, 'diamond', true, 37),
    ('🌙', 'Moon', 250, 'diamond', true, 38),
    ('☀️', 'Sun', 300, 'diamond', true, 39),
    ('🪐', 'Saturn', 350, 'diamond', true, 40),
    ('🌍', 'Earth', 400, 'diamond', true, 41),
    ('🧠', 'Brain', 450, 'diamond', true, 42),
    ('💥', 'Explosion', 500, 'diamond', true, 43),
    ('🌪️', 'Tornado', 550, 'diamond', true, 44),
    ('🔮', 'Crystal Ball', 600, 'diamond', true, 45),
    ('⚡', 'Lightning', 650, 'diamond', true, 46),
    ('🕶️', 'Sunglasses', 700, 'diamond', true, 47),
    ('🎰', 'Slot Machine', 750, 'diamond', true, 48),
    ('🧿', 'Nazar', 800, 'diamond', true, 49),
    ('🛡️', 'Shield', 850, 'diamond', true, 50),
    ('🗡️', 'Dagger', 900, 'diamond', true, 51),
    ('🏰', 'Castle', 1000, 'legendary', true, 52),
    ('👸', 'Queen', 1200, 'legendary', true, 53),
    ('🤴', 'King', 1400, 'legendary', true, 54),
    ('🦁', 'Lion', 1600, 'legendary', true, 55),
    ('🐲', 'Dragon Legend', 1800, 'legendary', true, 56),
    ('🚁', 'Helicopter', 2000, 'legendary', true, 57),
    ('🛥️', 'Yacht', 2500, 'legendary', true, 58),
    ('✈️', 'Private Jet', 3000, 'legendary', true, 59),
    ('🏎️', 'Sports Car', 4000, 'legendary', true, 60),
    ('🕌', 'Palace', 5000, 'legendary', true, 61),
    ('🚀', 'Space Ship', 7500, 'legendary', true, 62),
    ('💎👑', 'Crown Jewel', 10000, 'legendary', true, 63)
ON CONFLICT DO NOTHING;

-- 4. Live Types (replaces static LIVE_TYPES array)
CREATE TABLE IF NOT EXISTS chain_live_types (
    id serial PRIMARY KEY,
    slug text UNIQUE NOT NULL,
    label text NOT NULL,
    sort_order integer DEFAULT 0
);

INSERT INTO chain_live_types (slug, label, sort_order) VALUES
    ('public', 'Public Live', 1),
    ('friends', 'Friends Only', 2),
    ('subscribers', 'Subscribers Only', 3),
    ('premium', 'Premium Only', 4),
    ('ticketed', 'Ticketed Event', 5),
    ('private', 'Private', 6),
    ('cohost', 'Co-Host Stream', 7),
    ('duo', 'Duo Stream', 8),
    ('multiguest', 'Multi-Guest', 9),
    ('studio', 'Studio Mode', 10),
    ('screenshare', 'Screen Share', 11),
    ('camera_screen', 'Camera + Screen', 12)
ON CONFLICT (slug) DO NOTHING;

-- 5. Room Types (replaces static ROOM_TYPES array)
CREATE TABLE IF NOT EXISTS chain_room_types (
    id serial PRIMARY KEY,
    slug text UNIQUE NOT NULL,
    label text NOT NULL,
    sort_order integer DEFAULT 0
);

INSERT INTO chain_room_types (slug, label, sort_order) VALUES
    ('music', 'Music Room', 1),
    ('business', 'Business Room', 2),
    ('podcast', 'Podcast Room', 3),
    ('debate', 'Debate Room', 4),
    ('interview', 'Interview Room', 5),
    ('tutorial', 'Tutorial Room', 6),
    ('gaming', 'Gaming Room', 7),
    ('justchatting', 'Just Chatting', 8),
    ('art', 'Art Room', 9),
    ('cooking', 'Cooking Room', 10),
    ('fitness', 'Fitness Room', 11),
    ('church', 'Church Service', 12),
    ('jobfair', 'Job Fair Room', 13)
ON CONFLICT (slug) DO NOTHING;

-- 6. Interests (replaces hardcoded in onboarding.html)
CREATE TABLE IF NOT EXISTS chain_interests (
    id serial PRIMARY KEY,
    name text UNIQUE NOT NULL,
    icon text DEFAULT '',
    category text DEFAULT '',
    sort_order integer DEFAULT 0
);

INSERT INTO chain_interests (name, icon, category, sort_order) VALUES
    ('Music', '🎵', 'Entertainment', 1),
    ('Gaming', '🎮', 'Entertainment', 2),
    ('Fashion', '👗', 'Lifestyle', 3),
    ('Sports', '⚽', 'Lifestyle', 4),
    ('Business', '💼', 'Professional', 5),
    ('Travel', '✈️', 'Lifestyle', 6),
    ('Dating', '💕', 'Social', 7),
    ('Technology', '💻', 'Professional', 8),
    ('Movies', '🎬', 'Entertainment', 9),
    ('Food', '🍕', 'Lifestyle', 10),
    ('Photography', '📷', 'Creative', 11)
ON CONFLICT (name) DO NOTHING;

-- 7. Languages (replaces hardcoded in onboarding.html)
CREATE TABLE IF NOT EXISTS chain_languages (
    id serial PRIMARY KEY,
    name text UNIQUE NOT NULL,
    native_name text DEFAULT '',
    code text DEFAULT '',
    sort_order integer DEFAULT 0
);

INSERT INTO chain_languages (name, native_name, code, sort_order) VALUES
    ('English', 'English', 'en', 1),
    ('Spanish', 'Español', 'es', 2),
    ('French', 'Français', 'fr', 3),
    ('German', 'Deutsch', 'de', 4),
    ('Chinese', '中文', 'zh', 5),
    ('Japanese', '日本語', 'ja', 6),
    ('Portuguese', 'Português', 'pt', 7),
    ('Arabic', 'العربية', 'ar', 8),
    ('Hindi', 'हिन्दी', 'hi', 9)
ON CONFLICT (name) DO NOTHING;

-- 8. Creator Types (replaces hardcoded in onboarding.html)
CREATE TABLE IF NOT EXISTS chain_creator_types (
    id serial PRIMARY KEY,
    slug text UNIQUE NOT NULL,
    label text NOT NULL,
    sort_order integer DEFAULT 0
);

INSERT INTO chain_creator_types (slug, label, sort_order) VALUES
    ('viewer', 'Viewer', 1),
    ('creator', 'Creator', 2),
    ('streamer', 'Streamer', 3),
    ('business', 'Business', 4),
    ('musician', 'Musician', 5),
    ('influencer', 'Influencer', 6)
ON CONFLICT (slug) DO NOTHING;

-- 9. Notification Types (replaces hardcoded in notifications JS)
CREATE TABLE IF NOT EXISTS chain_notification_types (
    id serial PRIMARY KEY,
    slug text UNIQUE NOT NULL,
    label text NOT NULL,
    icon text DEFAULT '',
    category text DEFAULT 'social'
);

INSERT INTO chain_notification_types (slug, label, icon, category) VALUES
    ('follow', 'New Follower', '👤', 'social'),
    ('follow_accepted', 'Follow Request Accepted', '✅', 'social'),
    ('mention', 'Mention', '@', 'social'),
    ('comment', 'New Comment', '💬', 'engagement'),
    ('reply', 'Reply', '↩️', 'engagement'),
    ('post_like', 'Post Like', '❤️', 'engagement'),
    ('reel_like', 'Reel Like', '❤️', 'engagement'),
    ('story_reaction', 'Story Reaction', '😊', 'engagement'),
    ('story_mention', 'Story Mention', '📸', 'engagement'),
    ('live_started', 'Live Started', '🔴', 'live'),
    ('creator_subscription', 'New Subscription', '⭐', 'monetization'),
    ('wallet_transfer', 'Coins Sent', '💰', 'wallet'),
    ('wallet_received', 'Coins Received', '💎', 'wallet'),
    ('dating_match', 'New Match', '💕', 'dating'),
    ('verification_approved', 'Verification Approved', '✅', 'system'),
    ('security_alert', 'Security Alert', '🔒', 'system'),
    ('system_announcement', 'Announcement', '📢', 'system'),
    ('new_message', 'New Message', '✉️', 'messaging'),
    ('message_reaction', 'Message Reaction', '😄', 'messaging')
ON CONFLICT (slug) DO NOTHING;

-- 10. Reaction Types (replaces hardcoded reaction emojis)
CREATE TABLE IF NOT EXISTS chain_reaction_types (
    id serial PRIMARY KEY,
    emoji text UNIQUE NOT NULL,
    label text NOT NULL,
    sort_order integer DEFAULT 0
);

INSERT INTO chain_reaction_types (emoji, label, sort_order) VALUES
    ('❤️', 'Heart', 1),
    ('😂', 'Laugh', 2),
    ('😮', 'Wow', 3),
    ('😢', 'Sad', 4),
    ('🙏', 'Pray', 5),
    ('🔥', 'Fire', 6),
    ('🎉', 'Celebrate', 7),
    ('💯', '100', 8)
ON CONFLICT (emoji) DO NOTHING;
