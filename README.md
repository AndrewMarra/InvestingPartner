# 🤖📈 AI Trading Buddy

An AI trading *buddy* you select the style for. Each cycle it scans the market
within the trade styles you've enabled, surfaces the best idea(s), **texts you a
specific heads-up ~10 minutes before it acts** (share count, exit plan, whether
to set your own auto-sell), and paper-trades it to keep an honest record. You
decide whether to copy on your real brokerage.

> Honest framing: day trading and short-dated options lose money for most retail
> traders, and an LLM has no short-term price edge. This is a bounded experiment
> — keep stakes small, sanity-check every signal. Not financial advice.

---

## Trade modes (you pick the styles)

Enable any combination in `config.yaml` → `modes.enabled`. The AI ONLY proposes
and recommends trades in enabled modes.

| Mode | What it is |
|------|-----------|
| `equity_short` | Short-term stock shares **(default)** |
| `equity_day` | Intraday stock day trades |
| `equity_long` | Long-term stock holds |
| `option_short` | Short-term options incl. 0DTE |
| `option_long` | Long-dated options (LEAPS) |

`modes.short_term_horizon` defines what "short term" means to you:
`intraday_1d | daily | multiday | weekly | monthly` (default `daily` = buy today,
exit next session). The default config ships with just `equity_short` enabled so
there's always a working trade style out of the box.

**Every BUY carries an exit plan** — the AI decides between `bracket` (auto
limit + stop), `limit`, `stop`, `time` (hold N days), `manual_next_day` (re-ping
you to sell), or `hold` (long-term). The text spells it out:

```
🤖 (75%) BUY ~3 shares NVDA (~$205/sh, $615 total). Paper-executing in ~10 min.
Exit (AUTO, set now): limit-sell $215 OR stop-sell $195. If copying, set both sells.
Why: breakout above 20-day with volume…
```

And for a manual sell the next day:

```
📉 From a prior buy of NVDA: SELLING all shares in ~10 min (market).
If you copied the buy, sell yours too.
```

---

## Cost controls (keeping it cheap)

Built to sip API budget — central to keeping this free for now:

- **Tiered models.** A cheap model (`triage_model`, default Haiku) runs every
  cycle and decides whether anything is even worth a full look. The expensive
  `decision_model` (default **Sonnet**, not Opus) only runs when triage says yes.
  Quiet cycles cost a fraction of a cent.
- **Daily cap.** `cost_controls.max_decision_calls_per_day` hard-limits expensive
  calls. Past the cap, the buddy only manages existing positions.
- **Market-hours gating.** No polling when the market's closed (after-hours is a
  toggle), so no wasted calls overnight.
- Opus is intentionally never used in the loop — too costly to poll with. (Use it
  for design/dev, like this chat.)

---

## Setup & run

```bash
pip install -r requirements.txt
cp .env.example .env      # fill in keys
python run.py status
python run.py once --force
python run.py backtest --days 180
python run.py loop
python run.py report
```

Keys (free tiers): Alpaca (paper, enable options under Account → Configure),
Anthropic, Finnhub. Optional: FMP (fundamentals), Twilio (SMS).

## Free hosting (single-user): GitHub Actions
`.github/workflows/trade.yml` runs `once` every 15 min, market-hours gated — free
on a **public** repo. Keys go in Actions **Secrets**, never committed. The bot
checks Alpaca's real clock so the UTC cron handles DST automatically.

## Backtesting
`python run.py backtest --strategy momentum --days 180` — replays daily history,
reports return/CAGR/Sharpe/drawdown vs SPY buy-and-hold. Equities only (options
backtesting needs paid minute data). Strategies are pluggable.

---

## Multi-user (BYOK) — built

Each user brings their own API keys (free for the host, scales). Per-user
settings live in a database; the engine runs each user with their own keys,
modes, risk, and notification choices, fully isolated.

```bash
# 1. One-time: generate the master key that encrypts users' BYOK secrets
python run.py users keygen           # -> set MASTER_ENCRYPTION_KEY in env/secrets

# 2. Create a user and store their (encrypted) keys
python run.py users add --email you@x.com --phone +15551234567
python run.py users setkey --user <id> --provider anthropic_key --value sk-...
python run.py users setkey --user <id> --provider alpaca_key   --value PK-...
python run.py users setkey --user <id> --provider alpaca_secret --value ...
python run.py users setkey --user <id> --provider finnhub_key  --value ...

# 3. Set their style + notification choices (JSON overrides the base config)
python run.py users settings --user <id> \
  --json '{"modes":{"enabled":["equity_short","option_short"]},"notify":{"channels":["sms","telegram"]}}'

# 4. Run one cycle for ALL active users (what the Actions cron calls)
python run.py run-all
```

How it's kept safe and free:
- **BYOK secrets are encrypted at rest** (Fernet/AES) with a server-held
  `MASTER_ENCRYPTION_KEY`. The DB only ever holds ciphertext.
- **Per-user overrides are whitelisted** — a user's settings can change modes,
  risk, notify, schedule… but can't repoint the bot at a live-money endpoint.
- **One failing user never breaks the others** — the runner isolates each.
- **Notifications: SMS (Twilio) and/or Telegram (free)**, the user picks via
  `notify.channels`. Phone is required on the account either way.

### Production stack (free tier)
- **Frontend:** Next.js on Vercel — sign up, pick modes, set notify prefs, add
  phone, paste BYOK keys.
- **Auth + DB + phone:** Supabase free tier. Apply `supabase/schema.sql`
  (tables + row-level security so each user sees only their own rows).
- **Worker:** one GitHub Actions cron runs `python run.py run-all` on a schedule.
- The frontend uses Supabase's anon key (RLS-protected); the worker uses the
  service-role key. The master encryption key lives ONLY in the worker's secrets.

## Risk & license
Education/experiment only; not investment advice; authors not liable for losses.
0DTE can lose 100% in hours — premium caps exist for a reason. Start paper, stay
paper. MIT licensed; built to be forked.
