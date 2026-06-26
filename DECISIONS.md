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

### ADR-011 — Notifications: SMS + Telegram, user choice
Phone required on every account (identity + the product is "it texts you"). SMS
via Twilio costs a little; Telegram is free. Users pick channels; phone stays
required either way.
