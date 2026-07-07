-- ============================================================
-- NamVibe Live — Full Live Streaming Platform Schema
-- ============================================================

-- Live Rooms (core table)
CREATE TABLE IF NOT EXISTS chain_live_rooms (
  id            SERIAL PRIMARY KEY,
  host_id       INTEGER NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  title         VARCHAR(255) NOT NULL DEFAULT '',
  description   TEXT DEFAULT '',
  category      VARCHAR(64) DEFAULT 'entertainment',
  type          VARCHAR(32) DEFAULT 'public',
  password_hash VARCHAR(255) DEFAULT '',
  status        VARCHAR(32) DEFAULT 'scheduled',
  visibility    VARCHAR(32) DEFAULT 'public',

  video_quality VARCHAR(16) DEFAULT '1080p',
  audio_quality VARCHAR(16) DEFAULT 'hd',

  entry_fee     DECIMAL(10,2) DEFAULT 0,
  currency      VARCHAR(8) DEFAULT 'NAD',

  scheduled_at  TIMESTAMPTZ,
  started_at    TIMESTAMPTZ,
  ended_at      TIMESTAMPTZ,
  duration_secs INTEGER DEFAULT 0,

  viewer_count  INTEGER DEFAULT 0,
  peak_viewers  INTEGER DEFAULT 0,
  total_views   INTEGER DEFAULT 0,
  like_count    INTEGER DEFAULT 0,
  gift_value    DECIMAL(14,2) DEFAULT 0,

  tags          TEXT[] DEFAULT '{}',
  language      VARCHAR(8) DEFAULT 'en',
  location      VARCHAR(255) DEFAULT '',
  is_featured   BOOLEAN DEFAULT FALSE,
  is_verified   BOOLEAN DEFAULT FALSE,

  slow_mode_secs    INTEGER DEFAULT 0,
  sub_only_chat     BOOLEAN DEFAULT FALSE,
  followers_only    BOOLEAN DEFAULT FALSE,
  is_adult          BOOLEAN DEFAULT FALSE,

  recording_url TEXT DEFAULT '',
  replay_url    TEXT DEFAULT '',

  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_live_rooms_status ON chain_live_rooms(status);
CREATE INDEX IF NOT EXISTS idx_live_rooms_category ON chain_live_rooms(category);
CREATE INDEX IF NOT EXISTS idx_live_rooms_host ON chain_live_rooms(host_id);

-- Live Participants
CREATE TABLE IF NOT EXISTS chain_live_participants (
  id            SERIAL PRIMARY KEY,
  room_id       INTEGER NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
  profile_id    INTEGER NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  role          VARCHAR(32) DEFAULT 'viewer',
  is_muted      BOOLEAN DEFAULT FALSE,
  is_video_on   BOOLEAN DEFAULT TRUE,
  is_approved   BOOLEAN DEFAULT FALSE,
  is_blocked    BOOLEAN DEFAULT FALSE,
  joined_at     TIMESTAMPTZ DEFAULT NOW(),
  left_at       TIMESTAMPTZ,
  UNIQUE(room_id, profile_id)
);

-- NVC Wallet (coin balance per user)
CREATE TABLE IF NOT EXISTS chain_nvc_wallet (
  profile_id    INTEGER PRIMARY KEY REFERENCES chain_profiles(id) ON DELETE CASCADE,
  balance       DECIMAL(14,2) DEFAULT 0,
  lifetime_earned DECIMAL(14,2) DEFAULT 0,
  lifetime_spent  DECIMAL(14,2) DEFAULT 0,
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- NVC Purchase Packages
CREATE TABLE IF NOT EXISTS chain_nvc_packages (
  id            SERIAL PRIMARY KEY,
  name          VARCHAR(64) NOT NULL,
  coins         DECIMAL(10,2) NOT NULL,
  bonus_coins   DECIMAL(10,2) DEFAULT 0,
  price         DECIMAL(10,2) NOT NULL,
  currency      VARCHAR(8) DEFAULT 'NAD',
  is_popular    BOOLEAN DEFAULT FALSE,
  badge         VARCHAR(32) DEFAULT '',
  sort_order    INTEGER DEFAULT 0,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- NVC Transaction History
CREATE TABLE IF NOT EXISTS chain_nvc_transactions (
  id            SERIAL PRIMARY KEY,
  profile_id    INTEGER NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  type          VARCHAR(32) NOT NULL,
  amount        DECIMAL(14,2) NOT NULL,
  balance_after DECIMAL(14,2) NOT NULL,
  reference_type VARCHAR(64) DEFAULT '',
  reference_id  INTEGER,
  description   TEXT DEFAULT '',
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Virtual Gifts Catalog (NVC coin pricing with tiers)
CREATE TABLE IF NOT EXISTS chain_live_gifts (
  id            SERIAL PRIMARY KEY,
  name          VARCHAR(64) NOT NULL,
  emoji         VARCHAR(16) NOT NULL,
  price_nvc     DECIMAL(10,2) NOT NULL,
  tier          VARCHAR(32) DEFAULT 'bronze',
  animation_class VARCHAR(64) DEFAULT 'lv-gift-bronze',
  is_premium    BOOLEAN DEFAULT FALSE,
  is_featured   BOOLEAN DEFAULT FALSE,
  sort_order    INTEGER DEFAULT 0,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Gift Transactions (using NVC coins)
CREATE TABLE IF NOT EXISTS chain_live_gift_transactions (
  id            SERIAL PRIMARY KEY,
  room_id       INTEGER NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
  sender_id     INTEGER NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  recipient_id  INTEGER REFERENCES chain_profiles(id) ON DELETE SET NULL,
  gift_id       INTEGER REFERENCES chain_live_gifts(id),
  gift_name     VARCHAR(64),
  gift_emoji    VARCHAR(16),
  amount_nvc    DECIMAL(14,2) NOT NULL,
  quantity      INTEGER DEFAULT 1,
  message       TEXT DEFAULT '',
  is_coin_gift  BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Live Chat Messages
CREATE TABLE IF NOT EXISTS chain_live_chat_messages (
  id            SERIAL PRIMARY KEY,
  room_id       INTEGER NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
  sender_id     INTEGER NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  message_type  VARCHAR(32) DEFAULT 'text',
  body          TEXT DEFAULT '',
  emoji         VARCHAR(64) DEFAULT '',
  gift_emoji    VARCHAR(16) DEFAULT '',
  is_pinned     BOOLEAN DEFAULT FALSE,
  is_highlighted BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_live_chat_room ON chain_live_chat_messages(room_id, created_at);

-- Live Schedule
CREATE TABLE IF NOT EXISTS chain_live_schedules (
  id            SERIAL PRIMARY KEY,
  host_id       INTEGER NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  title         VARCHAR(255) NOT NULL,
  description   TEXT DEFAULT '',
  category      VARCHAR(64) DEFAULT 'entertainment',
  scheduled_at  TIMESTAMPTZ NOT NULL,
  duration_mins INTEGER DEFAULT 60,
  thumbnail_url TEXT DEFAULT '',
  is_recurring  BOOLEAN DEFAULT FALSE,
  recurring_rule VARCHAR(128) DEFAULT '',
  reminder_sent BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Live Polls
CREATE TABLE IF NOT EXISTS chain_live_polls (
  id            SERIAL PRIMARY KEY,
  room_id       INTEGER NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
  question      TEXT NOT NULL,
  options       TEXT[] DEFAULT '{}',
  votes         INTEGER[] DEFAULT '{}',
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Live Products (for shopping)
CREATE TABLE IF NOT EXISTS chain_live_products (
  id            SERIAL PRIMARY KEY,
  room_id       INTEGER NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
  product_id    INTEGER REFERENCES chain_marketplace_items(id) ON DELETE SET NULL,
  title         VARCHAR(255) NOT NULL,
  price         DECIMAL(10,2) NOT NULL,
  currency      VARCHAR(8) DEFAULT 'NAD',
  image_url     TEXT DEFAULT '',
  product_url   TEXT DEFAULT '',
  discount_pct  INTEGER DEFAULT 0,
  is_featured   BOOLEAN DEFAULT FALSE,
  sort_order    INTEGER DEFAULT 0
);

-- ============================================================
-- NVC Coin Purchase Packages
-- ============================================================
INSERT INTO chain_nvc_packages (name, coins, bonus_coins, price, currency, is_popular, badge, sort_order) VALUES
  ('Starter Pack', 50, 0, 0.99, 'NAD', FALSE, '', 1),
  ('Mini Pack', 120, 10, 1.99, 'NAD', FALSE, '', 2),
  ('Standard Pack', 300, 30, 4.99, 'NAD', TRUE, 'POPULAR', 3),
  ('Value Pack', 650, 75, 9.99, 'NAD', FALSE, '', 4),
  ('Large Pack', 1400, 200, 19.99, 'NAD', FALSE, '', 5),
  ('Mega Pack', 3200, 500, 39.99, 'NAD', FALSE, '', 6),
  ('Ultra Pack', 7000, 1200, 79.99, 'NAD', FALSE, '', 7),
  ('Premium Pack', 16000, 3000, 159.99, 'NAD', FALSE, 'BEST VALUE', 8),
  ('Legendary Pack', 40000, 10000, 349.99, 'NAD', FALSE, 'LEGENDARY', 9)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Gift Catalog — 5 Tiers of NVC-Powered Gifts
-- ============================================================
-- Tier 1: Bronze (1–10 NVC)
INSERT INTO chain_live_gifts (name, emoji, price_nvc, tier, animation_class, sort_order) VALUES
  ('Heart', '❤️', 1, 'bronze', 'lv-gift-bronze', 1),
  ('Rose', '🌹', 2, 'bronze', 'lv-gift-bronze', 2),
  ('Coffee', '☕', 3, 'bronze', 'lv-gift-bronze', 3),
  ('Cookie', '🍪', 3, 'bronze', 'lv-gift-bronze', 4),
  ('Donut', '🍩', 4, 'bronze', 'lv-gift-bronze', 5),
  ('Lollipop', '🍭', 3, 'bronze', 'lv-gift-bronze', 6),
  ('Candy', '🍬', 2, 'bronze', 'lv-gift-bronze', 7),
  ('Pizza', '🍕', 5, 'bronze', 'lv-gift-bronze', 8),
  ('Burger', '🍔', 6, 'bronze', 'lv-gift-bronze', 9),
  ('Fries', '🍟', 5, 'bronze', 'lv-gift-bronze', 10),
  ('Taco', '🌮', 6, 'bronze', 'lv-gift-bronze', 11),
  ('Popcorn', '🍿', 5, 'bronze', 'lv-gift-bronze', 12),
  ('Ice Cream', '🍦', 4, 'bronze', 'lv-gift-bronze', 13),
  ('Cake', '🎂', 8, 'bronze', 'lv-gift-bronze', 14),
  ('Beer', '🍺', 7, 'bronze', 'lv-gift-bronze', 15)
ON CONFLICT DO NOTHING;

-- Tier 2: Silver (10–50 NVC)
INSERT INTO chain_live_gifts (name, emoji, price_nvc, tier, animation_class, sort_order) VALUES
  ('Diamond', '💎', 10, 'silver', 'lv-gift-silver', 16),
  ('Lip Kiss', '💋', 12, 'silver', 'lv-gift-silver', 17),
  ('Fire', '🔥', 15, 'silver', 'lv-gift-silver', 18),
  ('100', '💯', 18, 'silver', 'lv-gift-silver', 19),
  ('Clap', '👏', 20, 'silver', 'lv-gift-silver', 20),
  ('Microphone', '🎤', 22, 'silver', 'lv-gift-silver', 21),
  ('Guitar', '🎸', 25, 'silver', 'lv-gift-silver', 22),
  ('Headphones', '🎧', 28, 'silver', 'lv-gift-silver', 23),
  ('Trophy', '🏆', 30, 'silver', 'lv-gift-silver', 24),
  ('Gold Medal', '🥇', 35, 'silver', 'lv-gift-silver', 25),
  ('Gamepad', '🎮', 40, 'silver', 'lv-gift-silver', 26),
  ('Art Palette', '🎨', 45, 'silver', 'lv-gift-silver', 27),
  ('Rocket', '🚀', 50, 'silver', 'lv-gift-silver', 28)
ON CONFLICT DO NOTHING;

-- Tier 3: Gold (50–200 NVC)
INSERT INTO chain_live_gifts (name, emoji, price_nvc, tier, animation_class, is_featured, sort_order) VALUES
  ('Crown', '👑', 60, 'gold', 'lv-gift-gold', TRUE, 29),
  ('Ring', '💍', 70, 'gold', 'lv-gift-gold', FALSE, 30),
  ('Gem', '💠', 80, 'gold', 'lv-gift-gold', FALSE, 31),
  ('Heart Eyes', '😍', 90, 'gold', 'lv-gift-gold', FALSE, 32),
  ('Kiss', '💏', 100, 'gold', 'lv-gift-gold', TRUE, 33),
  ('Love Letter', '💌', 115, 'gold', 'lv-gift-gold', FALSE, 34),
  ('Bouquet', '💐', 130, 'gold', 'lv-gift-gold', FALSE, 35),
  ('Music Notes', '🎵', 145, 'gold', 'lv-gift-gold', FALSE, 36),
  ('Party Popper', '🎉', 160, 'gold', 'lv-gift-gold', TRUE, 37),
  ('Confetti', '🎊', 175, 'gold', 'lv-gift-gold', FALSE, 38),
  ('Balloon', '🎈', 190, 'gold', 'lv-gift-gold', FALSE, 39),
  ('Gift Box', '🎁', 200, 'gold', 'lv-gift-gold', TRUE, 40)
ON CONFLICT DO NOTHING;

-- Tier 4: Diamond (200–1000 NVC)
INSERT INTO chain_live_gifts (name, emoji, price_nvc, tier, animation_class, is_premium, is_featured, sort_order) VALUES
  ('Sports Car', '🚗', 250, 'diamond', 'lv-gift-diamond', TRUE, FALSE, 41),
  ('Motorcycle', '🏍', 300, 'diamond', 'lv-gift-diamond', TRUE, FALSE, 42),
  ('Yacht', '🛥', 400, 'diamond', 'lv-gift-diamond', TRUE, FALSE, 43),
  ('Airplane', '✈️', 500, 'diamond', 'lv-gift-diamond', TRUE, TRUE, 44),
  ('Helicopter', '🚁', 600, 'diamond', 'lv-gift-diamond', TRUE, FALSE, 45),
  ('Private Jet', '🛩', 700, 'diamond', 'lv-gift-diamond', TRUE, FALSE, 46),
  ('Spaceship', '🚀', 800, 'diamond', 'lv-gift-diamond', TRUE, FALSE, 47),
  ('UFO', '🛸', 900, 'diamond', 'lv-gift-diamond', TRUE, FALSE, 48),
  ('Castle', '🏰', 1000, 'diamond', 'lv-gift-diamond', TRUE, TRUE, 49)
ON CONFLICT DO NOTHING;

-- Tier 5: Legendary (1000–10000 NVC) — Premium animated gifts
INSERT INTO chain_live_gifts (name, emoji, price_nvc, tier, animation_class, is_premium, is_featured, sort_order) VALUES
  ('Galaxy', '🌌', 1250, 'legendary', 'lv-gift-legendary lv-anim-galaxy', TRUE, FALSE, 50),
  ('Fireworks', '🎆', 1500, 'legendary', 'lv-gift-legendary lv-anim-fireworks', TRUE, TRUE, 51),
  ('Rainbow', '🌈', 2000, 'legendary', 'lv-gift-legendary lv-anim-rainbow', TRUE, FALSE, 52),
  ('Volcano', '🌋', 2500, 'legendary', 'lv-gift-legendary lv-anim-volcano', TRUE, FALSE, 53),
  ('Dragon', '🐉', 3000, 'legendary', 'lv-gift-legendary lv-anim-dragon', TRUE, FALSE, 54),
  ('Phoenix', '🦅', 4000, 'legendary', 'lv-gift-legendary lv-anim-phoenix', TRUE, FALSE, 55),
  ('Unicorn', '🦄', 5000, 'legendary', 'lv-gift-legendary lv-anim-unicorn', TRUE, TRUE, 56),
  ('Supernova', '💫', 7500, 'legendary', 'lv-gift-legendary lv-anim-supernova', TRUE, FALSE, 57),
  ('NamVibe Crown', '👑', 10000, 'legendary', 'lv-gift-legendary lv-anim-namvibe', TRUE, TRUE, 58)
ON CONFLICT DO NOTHING;

-- Auto-create wallets for existing profiles
INSERT INTO chain_nvc_wallet (profile_id, balance, lifetime_earned, lifetime_spent)
SELECT id, 0, 0, 0 FROM chain_profiles
ON CONFLICT DO NOTHING;
