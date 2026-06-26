import Link from "next/link";
import { BuddyMessage } from "@/components/BuddyMessage";

export default function Landing() {
  return (
    <div className="shell">
      <nav className="nav">
        <div className="brand">trading<b>buddy</b></div>
        <div className="navlinks">
          <Link href="/login">Sign in</Link>
          <Link href="/login" className="" style={{ color: "var(--signal)" }}>Get started</Link>
        </div>
      </nav>

      <section style={{ padding: "64px 0 40px", display: "grid", gap: 48, gridTemplateColumns: "1.1fr 1fr", alignItems: "center" }}>
        <div>
          <div className="eyebrow fade">An AI that texts you trade ideas</div>
          <h1 className="h-hero fade" style={{ margin: "16px 0 20px" }}>
            Like a friend<br />who happens to<br />trade for a living.
          </h1>
          <p className="muted fade" style={{ fontSize: 17, maxWidth: 440, lineHeight: 1.6 }}>
            Your buddy scans the market in the styles you choose, texts you a
            specific heads-up ten minutes before it acts, and lets you copy the
            trade on your own brokerage. You approve every real-money move.
          </p>
          <div className="fade" style={{ display: "flex", gap: 12, marginTop: 28 }}>
            <Link href="/login" className="btn">Start with paper trading</Link>
            <a href="#how" className="btn ghost">See how it works</a>
          </div>
          <p className="mono muted" style={{ fontSize: 12, marginTop: 18 }}>
            Bring your own keys · paper by default · not financial advice
          </p>
        </div>

        <div className="thread">
          <div className="fade"><BuddyMessage conf="72%">
            BUY ~3 shares NVDA (~$205/sh, $615). Executing in ~10 min.<br />
            Exit (auto): limit-sell $215 OR stop-sell $195.<br />
            Copy on your brokerage if you like it.
          </BuddyMessage></div>
          <div className="fade"><BuddyMessage tone="gain" conf="—">
            NVDA hit $215 — limit-sell filled. +$30 on the day. 📈
          </BuddyMessage></div>
          <div className="fade"><BuddyMessage conf="64%">
            From yesterday's QQQ buy: SELLING all shares in ~10 min (market).
            If you copied, sell yours too.
          </BuddyMessage></div>
        </div>
      </section>

      <section id="how" className="section" style={{ borderTop: "1px solid var(--line)" }}>
        <div className="cards">
          <div className="card"><div className="label">You choose the style</div>
            <p className="muted" style={{ marginTop: 8, fontSize: 14 }}>Short-term shares, day trades, long holds, or options — the buddy only trades what you enable.</p></div>
          <div className="card"><div className="label">It texts before it acts</div>
            <p className="muted" style={{ marginTop: 8, fontSize: 14 }}>A ~10-minute heads-up with share count and exit plan, by SMS or Telegram. Copy if you want.</p></div>
          <div className="card"><div className="label">You stay in control</div>
            <p className="muted" style={{ marginTop: 8, fontSize: 14 }}>Paper-traded by default. Hard risk limits and a daily loss switch the AI can't override.</p></div>
        </div>
      </section>

      <footer className="muted mono" style={{ padding: "28px 0", fontSize: 12 }}>
        Educational experiment. Trading is risky; you can lose money. Not investment advice.
      </footer>
    </div>
  );
}
