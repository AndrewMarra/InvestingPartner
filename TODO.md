# TODO — status

The post-V1 backlog has been implemented. This file now records WHAT shipped and
WHERE it lives, plus the handful of items deliberately left for later. See
DECISIONS.md for the "why" and CLAUDE.md for architecture.

---

## ✅ Shipped

### Priority — per-user pause + key isolation (user request)
- **Per-user pause.** `paused` flag on users/`profiles` (distinct from `active`),
  with an auto-migration for old SQLite DBs. `UserStore.list_active()` skips
  paused users; `list_all()` still shows them. CLI: `run.py users pause/resume
  --user <id>`. Web: a "Buddy is running / paused" toggle in dashboard settings.
  Files: `multiuser/users.py`, `storage/postgres.py`, `web/.../SettingsForm.tsx`,
  `web/app/actions.ts` (`setPaused`), `supabase/schema.sql`.
- **Global pause.** `BUDDY_PAUSED=true` stops every cycle (single- and
  multi-user). Wired in `run.py` (`_globally_paused`) and `trade.yml`.
- **Key isolation.** `run-all` is strictly BYOK — `build_user_config` builds
  secrets ONLY from a user's own decrypted keys (no env fallback), and the
  host's per-provider API keys were removed from the `trade.yml` `run-all` step,
  so another user's cycle can never use them. Covered by tests.

### Ticket 1 — Worker ↔ Supabase/Postgres adapter
- Backend chosen by env: `DATABASE_URL` set → Postgres (`storage/postgres.py`,
  `psycopg` v3, service role), else SQLite. Selected via `storage/factory.py`
  (`open_store` / `open_user_store`), used by the loop, runner, and CLI. SQLite
  stays the default for local dev + tests. `psycopg[binary]` added to requirements.

### Ticket 2 — Ticker explore page (Robinhood-style)
- `/dashboard/explore`: search any ticker → price + day change, price chart
  (reuses `EquityChart`), technicals (SMA10/30, trend, 5-day move), headlines,
  fundamentals (if FMP set). Read-only.
- Next.js route handler `app/api/ticker/[symbol]` fetches Alpaca + Finnhub (+FMP)
  using the user's decrypted BYOK keys (`lib/keys.ts` + new `fernetDecrypt`),
  with a short per-symbol cache. "Add to watchlist" appends to the user's
  `research.candidate_universe`.

### Ticket 3 — Buddy's take + manual override (consult)
- `research/engine.consult(symbol, intent)` + `scheduler/loop.consult(...)`,
  `intent ∈ {advisory, hard_buy, conditional_buy}`, portfolio-aware. Overrides
  reuse the SAME `risk.review` → enqueue → notify path (hard caps + kill switch
  always bind; overrides may bypass the enabled-modes gate + min-confidence).
  CLI: `run.py consult SYMBOL --intent ...`.
- Web: advisory take is an instant read-only Anthropic call (`lib/buddy.ts`,
  `app/api/consult`); acting overrides are queued to `consult_requests` and
  processed by the **risk-checked worker** (`Engine.process_consults`) — never a
  direct order from the browser.

### Backlog
- **Per-user pause toggle** — see Priority above.
- **Personal-portfolio comparison** — `benchmark/personal.py` computes your real
  return from a holdings CSV (`benchmark.personal_csv`); falls back to the typed
  `personal_return_pct`.
- **Option vertical spreads (multi-leg)** — `strategy:"vertical"` + `short_strike`
  in the decision/consult schema, risk handling, and a best-effort MLEG order in
  `execution/broker._buy_vertical` (degrades to notify-only).
- **True LEAPS expiry** — `data/options._expiry_window("leaps")` scans ~9–24 months
  and picks the farthest near-strike contract; `option_long` labels as LEAPS.
- **Option P&L tracking** — `OptionsData.position_marks` (mid-price marks for held
  contracts), surfaced in `run.py status` (best-effort; Alpaca already returns
  option position P&L).
- **Per-user starting capital** — `portfolio` is now overridable (bounded) and
  surfaced in settings.
- **Signals-only mode** — `trading.signals_only`: analyse + alert, never execute.
  Wired through the whole loop + consult; toggle in settings.
- **Email channel** — SMTP added to `notify/sms.py` (+ `Secrets`, BYOK providers,
  Keys page); enable via `notify.channels: [..., email]`.
- **Settings validation** — `usercfg.clamp_settings` bounds risk-relevant numbers
  server-side so users can't loosen their own guardrails to absurd levels.
- **Integration test** — `tests/test_consult.py` drives a full consult/override
  cycle (risk + store + notifier) with a faked market + model.

---

## Still future (deliberately deferred)
- **More multi-leg options** — iron condors / calendars (only debit verticals ship).
- **Web-push notifications** — SMS, Telegram, and email ship; web-push is the next
  channel (extend `notify/sms.py` + a service worker).
- **Secrets hardening** — `MASTER_ENCRYPTION_KEY` still lives in env/Actions
  secrets; a managed secret store + automated key-rotation plan remain future.
- **Live brokerage import for personal comparison** — currently a CSV; a read-only
  brokerage connection would make it fully automatic.
- **Real options P&L data plan** — accurate held-contract P&L needs an options
  data subscription.
- **Paper-cycle integration test against Alpaca's live paper API** (network-gated).
