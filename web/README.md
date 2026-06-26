# Trading Buddy — web

Next.js (App Router) + Supabase front end: accounts, trade-style toggles,
notification prefs, and BYOK key entry. Talks to the same tables the Python
worker reads (`supabase/schema.sql`).

## Run
```bash
npm install
cp .env.local.example .env.local      # fill in Supabase + MASTER_ENCRYPTION_KEY
npm run dev
```
First, apply `../supabase/schema.sql` in your Supabase SQL editor.

## How BYOK keys stay safe
The keys form posts to a server action that Fernet-encrypts each value with
`MASTER_ENCRYPTION_KEY` (server env only — never `NEXT_PUBLIC_`) and stores
ciphertext in `user_keys`. The Python worker decrypts with the same key. The
browser never sees the master key or other users' secrets (Supabase RLS).

## Status
Runnable scaffold. Implemented: email magic-link auth, dashboard overview,
trade-style settings, notification channels, phone capture, encrypted key entry.
Next: phone OTP verification, live performance chart. See ../CLAUDE.md.
