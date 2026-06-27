# CLAUDE.md — project memory for Claude Code

Read this first. It captures what this project is, how it's built, why it was
built that way, and what's next — the context that doesn't live in the code.

## What this is
An **AI trading buddy**: it scans the market in the trade styles a user enables,
**texts a specific heads-up ~10 minutes before it acts** (share count + exit
plan), and **paper-trades** the idea so there's an honest track record. The human
copies the trade on their own brokerage if they want. Every real-money decision
is the human's. Inspired by Michael Reeves' goldfish-trades-stocks bit, but the
decision is AI-reasoned instead of random.

**Framing that must not drift:** this is an experiment, not a money machine. Day
trading and 0DTE options lose money for most retail traders; an LLM has no
short-term price edge. Keep stakes small, keep it paper by default, never present
signals as reliable alpha. Not financial advice.

## Architecture (two parts)
1. **Python engine** (`aiportfolio/`, `run.py`) — the brain + execution + the
   multi-user runner. Fully tested. This is the source of truth.
2. **Next.js web app** (`web/`) — accounts, trade-style toggles, notification
   prefs, BYOK key entry. A scaffold: runnable with `npm install && npm run dev`
   once a Supabase project + env are wired.

### Python module map
- `config.py` — single-user config (YAML + env) and helpers to build per-user
  configs (`load_base_raw`, `deep_merge`). `Secrets` holds all API creds.
- `modes.py` — the trade-style taxonomy (equity_short/day/long, option_short/long)
  + short-term horizons. Generates the per-user prompt guidance. **The switchboard.**
- `data/` — market (Alpaca prices/bars/account/clock), news (Finnhub), options
  (Alpaca chain/quotes), fundamentals (FMP, optional).
- `research/engine.py` + `prompts.py` — **tiered models**: cheap Haiku triage
  decides if anything's worth a full look; Sonnet decision only runs when it is.
  Opus is never used in the loop (cost). Returns structured decisions via tool use.
  Also `consult(symbol, intent)` for user-initiated takes/overrides (shares the
  `DECISION_ITEM` schema so an override flows through the same machinery).
- `risk/guardrails.py` — hard limits the AI can't override: position/cash/trade
  caps, option premium caps, enabled-mode enforcement, daily-loss kill switch,
  stop-loss/take-profit. `review(... override_modes, bypass_confidence)` lets a
  user override loosen *gating* (not the rails). **The AI proposes; this disposes.**
- `execution/broker.py` — Alpaca orders. Equities support bracket/limit/stop exit
  plans; options are single-leg or debit verticals (best-effort MLEG). Defensive
  fallbacks to notify-only.
- `storage/db.py` — SQLite audit log + pending queue + planned exits + consult
  requests, **scoped by user_id**. Mirrors `supabase/schema.sql` for prod.
- `storage/postgres.py` — production twin (`PgStore`/`PgUserStore`) on Supabase
  Postgres via `psycopg` v3 (service role); same method surface as the SQLite
  classes. `storage/factory.py` picks the backend by the `DATABASE_URL` env.
- `notify/sms.py` — multi-channel alerts (Twilio SMS + Telegram + SMTP email),
  user-selectable. Message phrasing includes share counts + exact exit plan.
- `scheduler/loop.py` — the cycle, wired end to end (see below). Also
  `consult()` / `process_consults()` for the web→worker override queue, and the
  `signals_only` gating (notify, never execute).
- `backtest/` — equities backtester (momentum + buy&hold), metrics vs SPY.
- `multiuser/` — `crypto.py` (Fernet BYOK encryption), `users.py` (UserStore,
  incl. per-user pause), `usercfg.py` (build per-user Config with whitelisted
  overrides + server-side guardrail bounds), `runner.py` (iterate active+unpaused
  users, isolate failures).
- `benchmark/compare.py` + `personal.py` — AI vs SPY vs the user's own return
  (real return read from a holdings CSV).

### The cycle (`scheduler/loop.py::Engine.run_cycle`)
1. Execute ripe queued trades (set up their exit orders / planned exits).
1b. Process queued user consults/overrides (web → worker), each risk-checked.
2. Surface DUE planned exits (e.g. yesterday's daily buy) → notify + queue sell.
3. Immediate risk exits (stop-loss / take-profit).
3b. **Kill switch**: if down > daily_loss_limit_pct on the day, cancel queued
    buys + pause new buys (sells/exits still run).
4. **Cost gate**: triage (cheap) decides whether to spend a decision call; also
   capped by max_decision_calls_per_day.
5. Decision (Sonnet) → risk review (clamps to enabled modes + limits).
6. Notify (share count + exit plan) and queue each idea to execute in ~10 min.
   (If `trading.signals_only`, steps 1–6 notify but never place/queue an order.)
7. Snapshot equity.

## Key decisions & why (see DECISIONS.md for the full list)
- **Paper-first, human-in-the-loop.** The buddy never spends real money; the
  human copies trades. This is the core safety design — keep it.
- **BYOK.** Each user brings their own Alpaca + Anthropic + Finnhub keys → free
  for the host, scales. Keys are **Fernet-encrypted at rest**; DB stores only
  ciphertext. The same `MASTER_ENCRYPTION_KEY` is used by the Python worker and
  the Next.js server (verified cross-language compatible). It must NEVER reach
  the browser (no NEXT_PUBLIC_ prefix).
- **Tiered models for cost.** Haiku triages, Sonnet decides, Opus never in-loop.
- **Modes as a whitelist.** Per-user overrides can change modes/risk/notify but
  cannot repoint the bot at a live-money endpoint (`usercfg.ALLOWED_OVERRIDES`).
- **No crypto.** Blocked everywhere by design.
- **Free hosting.** Public GitHub repo → free Actions minutes; one cron runs
  `run-all` for all users. Supabase free tier for auth/DB/phone. Keep-alive
  workflow dodges the 7-day idle pause.

## Conventions
- The AI's output is always structured (Anthropic tool use), never free-text parsed.
- Every BUY must carry an exit_plan (no open-ended entries) — incl. overrides.
- All audit/state queries are scoped by `user_id`.
- External API calls are wrapped defensively; degrade to notify-only, never crash
  a user's cycle (and never let one user's failure affect another — see runner).
- Model strings live in config (`models.decision_model`, `models.triage_model`).
- **Storage is backend-pluggable**: always go through `storage/factory.py`
  (`open_store`/`open_user_store`) so code works on SQLite (dev/tests) and
  Postgres (prod). The two store impls must keep an identical method surface.
- **Key isolation**: the multi-user worker uses ONLY each user's own BYOK keys —
  never the host env. Don't add an env fallback to `build_user_config`.
- **Web never places trades directly**: acting overrides are queued
  (`consult_requests`) and executed by the worker through `risk.review`.

## How to run
Single-user: `cp .env.example .env` → fill keys → `python run.py once --force`.
Multi-user:  `python run.py users keygen` → set MASTER_ENCRYPTION_KEY →
`users add` / `setkey` / `settings` → `python run.py run-all`.
Pause:       `python run.py users pause --user <id>` (per-user) or `BUDDY_PAUSED=true` (global).
Consult:     `python run.py consult NVDA --intent advisory|hard_buy|conditional_buy`.
Backtest:    `python run.py backtest --days 180`.
Prod DB:     set `DATABASE_URL` (Supabase Postgres) → worker uses it instead of SQLite.
Web:         `cd web && npm install && cp .env.local.example .env.local` → fill →
`npm run dev`. Apply `supabase/schema.sql` in the Supabase SQL editor first.

## Testing notes
- **`tests/` is a pytest suite (45 tests, all passing)** covering: risk clamping +
  mode gating + option premium caps + forced exits + override gating, encryption
  roundtrip + user isolation, per-user config overrides + guardrail bounds,
  storage user-scoping + pending/kill-switch + planned exits + consult queue,
  per-user pause + migration, options expiry/LEAPS/vertical, personal-CSV return,
  a full consult/override cycle, and backtester math. Run: `pip install -r
  requirements-dev.txt && python -m pytest tests/ -q`.
- The web app **typechecks clean** (`cd web && npm install && npx tsc --noEmit`);
  `npx next build` also works (CPU-heavy locally).
- Fernet is **verified cross-language both ways** (Python↔Node encrypt/decrypt).
- CI (`.github/workflows/test.yml`) runs pytest + web typecheck on every push/PR.
- Heavy SDK clients (alpaca/anthropic/finnhub/apscheduler/psycopg) are imported
  lazily, so the tests and the user-management CLI run without them installed.

## Gotchas
- Alpaca advanced exit orders (bracket/limit/stop) need WHOLE shares; fractional
  notional buys fall back to a plain buy + planned manual exit.
- Options data/execution is best-effort; option P&L tracking needs a data plan.
  Multi-leg = debit verticals only (iron condors not yet); degrades to notify-only.
- GitHub Actions cron is UTC and ignores DST — the code gates on Alpaca's real
  clock, so don't "fix" the cron to chase market hours.
- Supabase free projects pause after 7 days idle (keepalive.yml handles it).
- The Postgres store uses `profiles` (not `users`) and jsonb/boolean dialect; the
  SQLite store uses `users` + TEXT/ints. Keep both in sync when adding columns.
- `trade.yml run-all` intentionally omits the host's per-provider API keys — that
  isolation is load-bearing, don't re-add them.

## What's next (post-V1, for Claude Code)
V1 **plus the full post-V1 backlog** is shipped and verified (see `TODO.md` for the
shipped record). Highlights now live: Supabase/Postgres worker adapter, ticker
explore page + buddy's-take, consult/override (CLI + risk-checked web queue),
per-user + global pause, BYOK key isolation, signals-only, per-user starting
capital, email channel, personal-CSV comparison, LEAPS expiry + debit verticals,
and server-side guardrail bounds.

Genuinely-future items (deferred, in `TODO.md`): iron condors/calendars, web-push,
managed secret store + key rotation, live brokerage import for personal
comparison, a real options P&L data plan, and a networked Alpaca paper-cycle
integration test.
