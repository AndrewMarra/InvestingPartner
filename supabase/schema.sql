-- Supabase / Postgres schema for the multi-user product.
-- Mirrors the local SQLite tables. Run in the Supabase SQL editor.
-- Auth users come from Supabase Auth (auth.users); these tables reference them.

-- ── Per-user profile (phone is required to use notifications) ────────
create table if not exists profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  phone text,
  active boolean default true,
  created_at timestamptz default now()
);

-- ── Encrypted BYOK keys (ciphertext only; encrypt in the worker) ─────
create table if not exists user_keys (
  user_id uuid references profiles (id) on delete cascade,
  provider text not null,
  ciphertext text not null,
  primary key (user_id, provider)
);

-- ── Per-user settings (enabled modes, horizon, risk, notify prefs) ───
create table if not exists user_settings (
  user_id uuid primary key references profiles (id) on delete cascade,
  settings jsonb not null default '{}'::jsonb
);

-- ── Audit + state (namespaced by user) ───────────────────────────────
create table if not exists decisions (
  id bigserial primary key, user_id uuid, ts timestamptz, market_view text, payload jsonb);
create table if not exists trades (
  id bigserial primary key, user_id uuid, ts timestamptz, instrument text, mode text,
  action text, symbol text, detail text, confidence real, rationale text,
  adjustments jsonb, order_result jsonb);
create table if not exists pending (
  id bigserial primary key, user_id uuid, ts timestamptz, execute_after timestamptz,
  status text default 'pending', trade jsonb);
create table if not exists planned_exits (
  id bigserial primary key, user_id uuid, ts timestamptz, symbol text, exit_type text,
  due_date date, status text default 'open', note text);
create table if not exists snapshots (
  id bigserial primary key, user_id uuid, ts timestamptz, date date, equity real,
  cash real, benchmark_price real);

-- ── Row-level security: each user sees only their own rows ───────────
alter table profiles       enable row level security;
alter table user_keys      enable row level security;
alter table user_settings  enable row level security;
alter table decisions      enable row level security;
alter table trades         enable row level security;
alter table snapshots      enable row level security;
-- These are worker-only (written via the service-role key, which bypasses RLS).
-- Enabling RLS with NO policy denies all anon/authenticated access — exactly
-- what we want, so they're never exposed through the public API.
alter table pending        enable row level security;
alter table planned_exits  enable row level security;

create policy "own profile"  on profiles      for all using (auth.uid() = id);
create policy "own keys"     on user_keys     for all using (auth.uid() = user_id);
create policy "own settings" on user_settings for all using (auth.uid() = user_id);
create policy "own decisions" on decisions    for select using (auth.uid() = user_id);
create policy "own trades"   on trades        for select using (auth.uid() = user_id);
create policy "own snapshots" on snapshots    for select using (auth.uid() = user_id);

-- NOTE: the polling worker uses the service-role key (bypasses RLS) to write
-- trades/decisions for all users. The frontend uses the anon key, so RLS keeps
-- each signed-in user scoped to their own data. NEVER store the master
-- encryption key or service-role key in the frontend.
