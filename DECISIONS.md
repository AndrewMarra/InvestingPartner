# Decisions log

Architecture decision records — the "why" behind the build, captured so the
reasoning survives outside the original chat.

### ADR-001 — Paper-first, human-in-the-loop
The buddy never executes real money. It paper-trades for the track record and
texts the user, who copies the trade on their own brokerage. Chosen because it
removes the worst risk (autonomous real-money loss from a bad model call) while
keeping the experiment honest. **Do not** add autonomous live trading without a
deliberate, separate, heavily-gated decision.

### ADR-002 — Diversified by default, not an AI-stock pile
An early version concentrated in AI semiconductors. Reverted: "aggressive" means
best risk-adjusted return (diversification), not four correlated bets. The
candidate universe spans ETFs, sectors, large caps, and gold.

### ADR-003 — BYOK (bring your own keys)
Each user supplies their own Alpaca/Anthropic/Finnhub keys. Makes the service
free for the host and scalable (no shared API bill). Trade-off: onboarding
friction + we must store user secrets → encryption at rest is mandatory.

### ADR-004 — Fernet encryption, master key server-side only
BYOK secrets are Fernet-encrypted; the DB holds ciphertext only. The same
`MASTER_ENCRYPTION_KEY` is used by the Python worker and the Next.js server
(implemented in Node crypto, verified to decrypt with Python `cryptography`).
The key must never be exposed to the browser.

### ADR-005 — Tiered models
A cheap triage model (Haiku) runs every cycle; the decision model (Sonnet) only
runs when triage flags something. Opus is never used in the loop. Keeps per-cycle
cost near zero on quiet cycles; respects API/usage limits.

### ADR-006 — Trade styles as user-selectable modes
equity_short / equity_day / equity_long / option_short / option_long, plus a
short-term horizon. The AI only acts within enabled modes (enforced in the risk
layer, not just the prompt). Default is equity_short/daily so there's always a
working style. Later: gate advanced modes behind a paid tier.

### ADR-007 — Every BUY carries an exit plan
No open-ended entries. The AI chooses bracket/limit/stop/time/manual/hold, and
the notification states it explicitly so the user knows whether to set their own
auto-sell when copying.

### ADR-008 — Hard risk layer the AI can't override
Position/cash/trade caps, option premium caps, per-day limits, stop-loss/
take-profit, and a daily-loss kill switch live in code and clamp or reject the
AI's proposals after the fact. The AI proposes; the risk layer disposes.

### ADR-009 — No crypto
Excluded everywhere by explicit product choice.

### ADR-010 — Free hosting stack
Public GitHub repo (free unlimited Actions) runs one cron over all users.
Supabase free tier for auth + Postgres + phone. Vercel for the frontend. A
keep-alive workflow prevents Supabase's 7-day idle pause. Move to paid tiers only
when the product earns it.

### ADR-011 — Notifications: SMS + Telegram (+ email), user choice
Phone required on every account (identity + the product is "it texts you"). SMS
via Twilio costs a little; Telegram is free. Email (SMTP/BYOK) added as a third
channel. Users pick channels; phone stays required either way.

### ADR-012 — Backend chosen by env, two implementations behind one surface
The worker reads/writes SQLite locally (zero-setup, testable) and Supabase
Postgres in production, picked by `DATABASE_URL` via `storage/factory.py`. We kept
two concrete store classes with an identical method surface (rather than a query
shim) because the dialects genuinely differ (jsonb vs TEXT, booleans, `profiles`
vs `users`, ON CONFLICT vs INSERT OR REPLACE). SQLite stays the default so the
test suite needs no Postgres and `psycopg` is imported lazily.

### ADR-013 — Per-user pause is distinct from active; plus a global kill switch
`paused` (user temporarily suspends their own buddy) is separate from `active`
(deactivated/deleted). The runner skips active-and-unpaused users silently.
`BUDDY_PAUSED=true` is a coarse global stop for the whole worker. Both exist
because "stop my account" and "stop everything" are different needs.

### ADR-014 — Strict BYOK key isolation in the multi-user worker
`run-all` builds each user's secrets ONLY from their own decrypted keys — there is
no fallback to the host's environment, and the host's per-provider keys were
removed from the Actions `run-all` step. This makes it structurally impossible for
one user's cycle to run on another user's (or the host's) API keys.

### ADR-015 — User overrides loosen gating, never the safety rails
A manual override (`consult` hard_buy / conditional_buy) may bypass the
enabled-modes gate and the min-confidence gate (the user asked explicitly), but
ALWAYS goes through `risk.review` — position/cash/trade caps, no-crypto, premium
caps, and the daily-loss kill switch still bind, and every BUY still needs an
exit_plan. Conditional buys act only when the AI agrees; otherwise nothing queues.

### ADR-016 — The web never places trades directly
The explore page's "buddy's take" is a read-only Anthropic call. Acting overrides
are written to a `consult_requests` queue and executed by the risk-checked worker,
not by the browser — so the in-code risk layer (ADR-008) is never bypassed.

### ADR-017 — Server-side guardrail bounds on user settings
Per-user overrides are clamped server-side (`usercfg.clamp_settings`) so a user
can make their own setup SAFER but not recklessly less safe (e.g. 100%/position or
disabling the kill switch). The whitelist (ADR-006) controls WHICH sections are
overridable; bounds control HOW FAR.

### ADR-018 — Signals-only mode
A per-user `trading.signals_only` flag makes the buddy analyse + alert but never
place or queue any order. For users who only want the heads-up and copy manually,
this removes paper-execution entirely while keeping the full reasoning + alerts.
