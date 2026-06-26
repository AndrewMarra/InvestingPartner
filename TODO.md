# TODO — post-V1 backlog

Tickets for Claude Code. The top two are specced in detail; the rest is a
prioritized backlog so nothing is lost. See CLAUDE.md for architecture context.

---

## TICKET 1 (priority) — Worker ↔ Supabase adapter

**Why.** Today the Python worker reads/writes **SQLite** (`portfolio.db`) while
the Next.js web app reads/writes **Supabase Postgres**. They're two separate
stores, so a web signup does NOT yet drive the worker. This ticket connects them.

**Goal.** Make `Store` (audit/state) and `UserStore` (accounts/keys/settings)
backend-pluggable: SQLite for local dev, **Supabase Postgres for production**,
selected by env. The `run-all` worker then operates on the same data users create
in the web app.

**Approach.**
- Add a DB backend abstraction. Keep the current SQLite classes as the
  `sqlite` backend; add a `postgres` backend using `psycopg` (v3).
- Connection from env: if `DATABASE_URL` (Supabase connection string) is set, use
  Postgres; else SQLite (`storage.db_path`). The worker connects with the
  **service-role** Postgres role (bypasses RLS — it acts for all users).
- The schema already exists in `supabase/schema.sql` and mirrors the SQLite
  tables 1:1, so only the SQL dialect/driver differs (placeholders `%s` vs `?`,
  `jsonb` vs TEXT, `serial` vs AUTOINCREMENT). Consider a tiny query-translation
  shim or just two implementations behind one interface.
- `multiuser/runner.py` already iterates `UserStore.list_active()` and builds
  per-user configs — only the store construction changes.

**Files.** `storage/db.py`, `multiuser/users.py`, new `storage/backend.py` (or
`multiuser/db.py`), `requirements.txt` (+`psycopg[binary]`), `config.py` (read
`DATABASE_URL`).

**Gotchas.**
- Keys are encrypted **in the app layer** (Fernet) regardless of backend — the
  DB only ever sees ciphertext. Don't move encryption into Postgres.
- The web writes user_keys ciphertext via the user's session (RLS "own keys");
  the worker reads it via service role. Both must use the SAME
  `MASTER_ENCRYPTION_KEY`.
- Keep SQLite working for local dev and the test suite (tests assume SQLite).

**Acceptance.** Create a user + keys + settings through the web app; run
`python run.py run-all` against the same Supabase project; the worker picks up
that user and runs their cycle. Tests still pass on SQLite.

---

## TICKET 2 — Ticker search & analysis tool (Robinhood-style)

**Why.** Users want to look up *any* ticker and see analytics, not just watch the
buddy's watchlist. The Python data layer already supports arbitrary symbols
(`data/market.simple_technicals` + `recent_bars`, `data/news.company_news`,
`data/fundamentals.snapshot`), so most plumbing exists.

**Goal.** A `/dashboard/explore` page: search a ticker → see price + day change,
a price chart, key technicals, recent headlines, basic fundamentals, and an
optional on-demand "buddy's take." Read-only — it never places trades.

**Approach (recommended: keep it on the existing free stack).**
- Next.js **route handlers** under `web/app/api/ticker/[symbol]/` that fetch
  directly from Alpaca + Finnhub using the signed-in user's **decrypted BYOK
  keys** (decrypt server-side with the master key, same as key-save). Return
  `{ quote, bars, technicals, news, fundamentals }`.
  - Mirror `simple_technicals` logic (SMA10/30, trend, 5-day move) in TS, or
    expose it from a small Python endpoint if you'd rather reuse the code (see
    alternative below).
- Reuse `EquityChart` styling for the price chart (feed it close prices).
- "Get the buddy's take" button → a route handler that runs a **single** Anthropic
  call (Sonnet) summarizing the ticker from the fetched data. This is a read, not
  a trade — do NOT route it through the trading decision/execution path.
- "Add to watchlist" → append the symbol to the user's
  `settings.research.candidate_universe` so the buddy starts considering it.

**Alternative architecture.** If you'd rather not reimplement data logic in TS,
stand up a small read-only Python service (FastAPI) exposing
`/ticker/{symbol}` that reuses `aiportfolio/data`, and have the frontend call it.
Trade-off: another deployed service vs. code reuse. Start with the Next.js route
handlers (free, one deploy) unless reuse pressure grows.

**Gotchas.**
- Rate limits: Finnhub free is ~60/min — cache responses (per symbol, short TTL).
- Degrade gracefully when a user has no FMP key (skip fundamentals).
- Validate/normalize the symbol; handle "not found" with a clear empty state.
- Keep it strictly read-only — no order placement from this surface.

**Acceptance.** A signed-in user searches any valid US ticker and sees
price/chart/technicals/news (and fundamentals if FMP is set), can optionally get
an AI take, and can add the ticker to their watchlist — with zero trades placed.

---

## TICKET 3 — "Buddy's take" + manual override (user-initiated requests)

**Why.** Users want to point the buddy at a specific stock and either get its
read or direct it to act — including a conditional "buy this, but only if you
also think it's smart." That last one is the valuable pattern: the AI acts as a
check on the user's impulse instead of a pure order-taker.

**Goal.** Three user-initiated interactions on a chosen ticker, all
portfolio-aware (the buddy considers whether it's already held, at what cost,
and the current P&L):
1. **Advisory** — "What's your take on X?" → a read with a verdict
   (buy / add / hold / trim / sell / avoid) + reasoning. No action.
2. **Hard override** — "I want X, buy it." → the buddy buys it (respecting risk
   limits), and still attaches a sensible exit plan.
3. **Conditional override** — "Buy X, but only if you also think it's smart." →
   the buddy evaluates and acts ONLY if it agrees; either way it tells the user
   its reasoning. If it declines, nothing is queued.

**Approach.**
- Add a `consult(symbol, intent)` path to `research/engine.py` using the decision
  model, where `intent` ∈ {advisory, hard_buy, conditional_buy}. Build a focused
  briefing for that one symbol (price, technicals, news, fundamentals) **plus the
  user's current position in it** (held?, qty, avg cost, unrealized P&L) so the
  take is portfolio-aware.
- New structured output (a `consult` tool) returning: `verdict`, `agree` (bool,
  for conditional), `reasoning`, and — when it will act — the SAME decision
  fields an autonomous idea produces (`mode`, `notional`, `exit_plan`,
  `confidence`, `rationale`) so it flows through the existing machinery unchanged.
- **Reuse, don't fork, the action path:** when the buddy will act (hard override,
  or conditional where `agree=true`), run the proposed trade through
  `risk.review()` and the normal enqueue → notify (~10-min) → execute flow. The
  user gets the same detailed "buying ~N shares, exit plan…" text.
- Surface it on the ticker explorer (Ticket 2): a "Get the buddy's take" button
  (advisory) and a prompt/box for override requests. Could also be a small chat
  input.

**Key rules (important).**
- **Hard risk limits ALWAYS apply** — even a hard override goes through
  `risk.review`: position/cash/trade caps, no-crypto, and the daily-loss kill
  switch all still bind. A user override loosens *gating* (see next point), not
  the safety rails.
- A manual override MAY bypass triage and the enabled-modes gate (the user asked
  explicitly), but the trade still needs a valid mode tag and an **exit_plan**
  (the no-open-ended-entries invariant holds).
- For `conditional_buy`, if `agree=false`, queue nothing and just return the
  reasoning — the whole point is the AI can talk the user out of it.
- Log consults (and their verdicts) to the audit trail alongside autonomous
  decisions, so the record shows who initiated what.

**Files.** `research/engine.py` (+`consult`), `research/prompts.py` (consult
tool + system text), `scheduler/loop.py` (a `consult`/`override` entry point that
reuses risk+enqueue+notify), a CLI verb (`python run.py consult SYMBOL --intent
...`) for testing, and the web explore page (Ticket 2) for the UI.

**Acceptance.**
- "Take on TSLA" returns a portfolio-aware verdict + reasoning, no trade.
- "Buy TSLA" queues a risk-checked, exit-planned buy with the normal alert.
- "Buy TSLA only if smart" queues it when the AI agrees, and when it doesn't,
  places nothing and explains why.
- All three respect risk caps and the kill switch; all are logged.

---

## Backlog (smaller / later)

- **Personal-portfolio comparison (original goal).** Replace the manually-typed
  `benchmark.personal_return_pct` with an actual read of the user's real holdings
  (e.g., a read-only brokerage connection or a positions CSV import) so "AI vs my
  portfolio" is automatic.
- **Option spreads (multi-leg)** — verticals/iron condors; safer than naked 0DTE.
  Extend `execution/broker.py` + the decision schema.
- **True LEAPS expiry selection** for `option_long` — `data/options._next_expiry`
  currently only does 0DTE / nearest-weekly.
- **Option P&L tracking** — needs an options data plan (quotes for held contracts).
- **Per-user starting capital** — add `portfolio` to `usercfg.ALLOWED_OVERRIDES`
  and surface it in settings; reconcile with the Alpaca paper account balance
  (Alpaca paper defaults to $100k — document or auto-set).
- **"Signals-only" mode** — notify but never paper-execute, per user.
- **Email / web-push channels** — extend `notify/sms.py` (currently SMS+Telegram).
- **Secrets hardening** — move `MASTER_ENCRYPTION_KEY` to a managed secrets store;
  add a key-rotation plan; document the BYOK trust model in a privacy policy.
- **Settings validation** — bound user-supplied risk values server-side so users
  can't loosen their own guardrails to absurd levels.
- **Integration test** — exercise one full cycle against Alpaca's paper API.
