-- Phase 62 — Marketplace & Shop Ecosystem
-- Idempotent — safe to re-run

-- 1. Shops
CREATE TABLE IF NOT EXISTS chain_shops (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid UNIQUE REFERENCES chain_profiles(id) ON DELETE CASCADE,
    shop_type text NOT NULL DEFAULT 'personal',
    name text NOT NULL,
    logo_url text DEFAULT '',
    banner_url text DEFAULT '',
    description text DEFAULT '',
    category text DEFAULT 'general',
    contact_email text DEFAULT '',
    contact_phone text DEFAULT '',
    whatsapp text DEFAULT '',
    location text DEFAULT '',
    is_verified boolean DEFAULT false,
    followers_count int DEFAULT 0,
    products_count int DEFAULT 0,
    services_count int DEFAULT 0,
    rating numeric(3,2) DEFAULT 0,
    review_count int DEFAULT 0,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_shops_profile ON chain_shops (profile_id);
CREATE INDEX IF NOT EXISTS idx_shops_category ON chain_shops (category);
CREATE INDEX IF NOT EXISTS idx_shops_active ON chain_shops (is_active);
CREATE INDEX IF NOT EXISTS idx_shops_type ON chain_shops (shop_type);

-- 2. Products
CREATE TABLE IF NOT EXISTS chain_products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id uuid REFERENCES chain_shops(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    title text NOT NULL,
    description text DEFAULT '',
    images text[] DEFAULT '{}',
    price_cents bigint DEFAULT 0,
    currency text DEFAULT 'NAD',
    stock int DEFAULT 0,
    category text DEFAULT 'general',
    subcategory text DEFAULT '',
    location text DEFAULT '',
    condition text DEFAULT 'new',
    tags text[] DEFAULT '{}',
    is_active boolean DEFAULT true,
    is_featured boolean DEFAULT false,
    sales_count int DEFAULT 0,
    rating numeric(3,2) DEFAULT 0,
    review_count int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_shop ON chain_products (shop_id);
CREATE INDEX IF NOT EXISTS idx_products_profile ON chain_products (profile_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON chain_products (category);
CREATE INDEX IF NOT EXISTS idx_products_active ON chain_products (is_active);
CREATE INDEX IF NOT EXISTS idx_products_featured ON chain_products (is_featured);

-- 3. Services
CREATE TABLE IF NOT EXISTS chain_services (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id uuid REFERENCES chain_shops(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    title text NOT NULL,
    description text DEFAULT '',
    images text[] DEFAULT '{}',
    hourly_rate_cents bigint DEFAULT 0,
    currency text DEFAULT 'NAD',
    service_area text DEFAULT '',
    availability text DEFAULT '',
    category text DEFAULT 'general',
    tags text[] DEFAULT '{}',
    is_active boolean DEFAULT true,
    is_featured boolean DEFAULT false,
    booking_count int DEFAULT 0,
    rating numeric(3,2) DEFAULT 0,
    review_count int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_services_shop ON chain_services (shop_id);
CREATE INDEX IF NOT EXISTS idx_services_profile ON chain_services (profile_id);
CREATE INDEX IF NOT EXISTS idx_services_category ON chain_services (category);
CREATE INDEX IF NOT EXISTS idx_services_active ON chain_services (is_active);

-- 4. Bookings
CREATE TABLE IF NOT EXISTS chain_bookings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id uuid REFERENCES chain_services(id) ON DELETE CASCADE,
    shop_id uuid REFERENCES chain_shops(id) ON DELETE CASCADE,
    client_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    provider_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending',
    requested_date timestamptz,
    scheduled_date timestamptz,
    completed_date timestamptz,
    notes text DEFAULT '',
    client_notes text DEFAULT '',
    amount_cents bigint DEFAULT 0,
    currency text DEFAULT 'NAD',
    is_paid boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bookings_service ON chain_bookings (service_id);
CREATE INDEX IF NOT EXISTS idx_bookings_client ON chain_bookings (client_profile_id);
CREATE INDEX IF NOT EXISTS idx_bookings_provider ON chain_bookings (provider_profile_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON chain_bookings (status);
CREATE INDEX IF NOT EXISTS idx_bookings_shop ON chain_bookings (shop_id);

-- 5. Reviews
CREATE TABLE IF NOT EXISTS chain_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reviewer_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    target_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    shop_id uuid REFERENCES chain_shops(id) ON DELETE CASCADE,
    product_id uuid REFERENCES chain_products(id) ON DELETE CASCADE,
    service_id uuid REFERENCES chain_services(id) ON DELETE CASCADE,
    booking_id uuid REFERENCES chain_bookings(id) ON DELETE SET NULL,
    rating int NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title text DEFAULT '',
    body text DEFAULT '',
    image_url text DEFAULT '',
    is_verified_purchase boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON chain_reviews (reviewer_profile_id);
CREATE INDEX IF NOT EXISTS idx_reviews_target ON chain_reviews (target_profile_id);
CREATE INDEX IF NOT EXISTS idx_reviews_shop ON chain_reviews (shop_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product ON chain_reviews (product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_service ON chain_reviews (service_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON chain_reviews (rating);
CREATE INDEX IF NOT EXISTS idx_reviews_active ON chain_reviews (is_active);

-- 6. Saved Products (wishlist)
CREATE TABLE IF NOT EXISTS chain_saved_products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    product_id uuid REFERENCES chain_products(id) ON DELETE CASCADE,
    service_id uuid REFERENCES chain_services(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_unique_product
    ON chain_saved_products (profile_id, product_id) WHERE product_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_unique_service
    ON chain_saved_products (profile_id, service_id) WHERE service_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_saved_profile ON chain_saved_products (profile_id);
CREATE INDEX IF NOT EXISTS idx_saved_product ON chain_saved_products (product_id);
CREATE INDEX IF NOT EXISTS idx_saved_service ON chain_saved_products (service_id);
