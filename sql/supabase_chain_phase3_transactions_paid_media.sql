create table if not exists chain_wallet_transactions (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    transaction_type text,
    direction text,
    coins integer default 0,
    amount_nad numeric default 0,
    reference_number text,
    related_table text,
    related_id uuid,
    status text default 'completed',
    description text,
    created_at timestamptz default now()
);

alter table if exists chain_marketplace_items
    add column if not exists download_url text,
    add column if not exists preview_blur_url text,
    add column if not exists download_enabled boolean default false,
    add column if not exists approved_by uuid,
    add column if not exists approved_at timestamptz;

alter table if exists chain_media_purchases
    add column if not exists download_allowed boolean default true,
    add column if not exists purchase_status text default 'completed';

create index if not exists idx_chain_wallet_transactions_profile_id on chain_wallet_transactions(profile_id);
create index if not exists idx_chain_wallet_transactions_related on chain_wallet_transactions(related_table, related_id);
create index if not exists idx_chain_marketplace_items_approval_status on chain_marketplace_items(approval_status);
create index if not exists idx_chain_media_purchases_buyer_item on chain_media_purchases(buyer_profile_id, item_id);
