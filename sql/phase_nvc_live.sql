-- NamVibe NVC Coin System & Live Schema — Neon UUID-Compatible
-- This migrates the NVC wallet/gift system to match existing UUID-based schema

-- NVC Wallet (coin balance per profile)
CREATE TABLE IF NOT EXISTS chain_nvc_wallet (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id      UUID NOT NULL,
  balance         DECIMAL(14,2) DEFAULT 0,
  lifetime_earned DECIMAL(14,2) DEFAULT 0,
  lifetime_spent  DECIMAL(14,2) DEFAULT 0,
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(profile_id)
);

-- NVC Transaction History
CREATE TABLE IF NOT EXISTS chain_nvc_transactions (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  profile_id      UUID NOT NULL,
  type            VARCHAR(32) NOT NULL,
  amount          DECIMAL(14,2) NOT NULL,
  balance_after   DECIMAL(14,2) NOT NULL,
  reference_type  VARCHAR(64) DEFAULT '',
  reference_id    VARCHAR(64) DEFAULT '',
  description     TEXT DEFAULT '',
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nvc_tx_profile ON chain_nvc_transactions(profile_id, created_at DESC);

-- NVC Gift Catalog (58 gifts across 5 tiers)
CREATE TABLE IF NOT EXISTS chain_live_gift_catalog (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name            VARCHAR(64) NOT NULL,
  emoji           VARCHAR(16) NOT NULL,
  price_nvc       DECIMAL(10,2) NOT NULL,
  tier            VARCHAR(32) DEFAULT 'bronze',
  animation_class VARCHAR(64) DEFAULT 'lv-gift-bronze',
  is_premium      BOOLEAN DEFAULT FALSE,
  is_featured     BOOLEAN DEFAULT FALSE,
  sort_order      INTEGER DEFAULT 0,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed gift catalog (15 bronze + 13 silver + 12 gold + 9 diamond + 9 legendary = 58)
INSERT INTO chain_live_gift_catalog (name, emoji, price_nvc, tier, animation_class, sort_order) VALUES
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

INSERT INTO chain_live_gift_catalog (name, emoji, price_nvc, tier, animation_class, sort_order) VALUES
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

INSERT INTO chain_live_gift_catalog (name, emoji, price_nvc, tier, animation_class, is_featured, sort_order) VALUES
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

INSERT INTO chain_live_gift_catalog (name, emoji, price_nvc, tier, animation_class, is_premium, is_featured, sort_order) VALUES
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

INSERT INTO chain_live_gift_catalog (name, emoji, price_nvc, tier, animation_class, is_premium, is_featured, sort_order) VALUES
  ('Galaxy', '🌌', 1250, 'legendary', 'lv-gift-legendary', TRUE, FALSE, 50),
  ('Fireworks', '🎆', 1500, 'legendary', 'lv-gift-legendary', TRUE, TRUE, 51),
  ('Rainbow', '🌈', 2000, 'legendary', 'lv-gift-legendary', TRUE, FALSE, 52),
  ('Volcano', '🌋', 2500, 'legendary', 'lv-gift-legendary', TRUE, FALSE, 53),
  ('Dragon', '🐉', 3000, 'legendary', 'lv-gift-legendary', TRUE, FALSE, 54),
  ('Phoenix', '🦅', 4000, 'legendary', 'lv-gift-legendary', TRUE, FALSE, 55),
  ('Unicorn', '🦄', 5000, 'legendary', 'lv-gift-legendary', TRUE, TRUE, 56),
  ('Supernova', '💫', 7500, 'legendary', 'lv-gift-legendary', TRUE, FALSE, 57),
  ('NamVibe Crown', '👑', 10000, 'legendary', 'lv-gift-legendary', TRUE, TRUE, 58)
ON CONFLICT DO NOTHING;

-- Seed wallet for existing profiles (0 balance)
INSERT INTO chain_nvc_wallet (profile_id, balance, lifetime_earned, lifetime_spent)
SELECT id, 0, 0, 0 FROM chain_profiles
ON CONFLICT DO NOTHING;
