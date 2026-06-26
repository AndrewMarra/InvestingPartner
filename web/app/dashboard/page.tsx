import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";
import { BuddyMessage } from "@/components/BuddyMessage";
import { EquityChart } from "@/components/EquityChart";

export default async function Overview() {
  const supabase = supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();

  const [{ data: trades }, { data: snaps }, { data: profile }, { data: settings }, { data: keys }] =
    await Promise.all([
      supabase.from("trades").select("*").order("id", { ascending: false }).limit(8),
      supabase.from("snapshots").select("equity").order("id", { ascending: true }),
      supabase.from("profiles").select("phone").eq("id", user!.id).maybeSingle(),
      supabase.from("user_settings").select("settings").eq("user_id", user!.id).maybeSingle(),
      supabase.from("user_keys").select("provider").eq("user_id", user!.id),
    ]);

  const equity = (snaps ?? []).map((s: any) => s.equity);
  const start = equity[0] ?? 1000;
  const now = equity[equity.length - 1] ?? start;
  const ret = (now / start - 1) * 100;

  const haveKeys = new Set((keys ?? []).map((k: any) => k.provider));
  const required = ["alpaca_key", "alpaca_secret", "anthropic_key", "finnhub_key"];
  const steps = [
    { done: required.every((r) => haveKeys.has(r)), label: "Add your API keys", href: "/dashboard/keys" },
    { done: !!profile?.phone, label: "Add your phone for alerts", href: "/dashboard/keys" },
    { done: !!settings?.settings?.modes?.enabled?.length, label: "Choose your trade styles", href: "/dashboard/settings" },
  ];
  const ready = steps.every((s) => s.done);

  return (
    <>
      {!ready && (
        <section style={{ padding: "28px 0 0" }}>
          <div className="eyebrow">Finish setup</div>
          <div className="card" style={{ marginTop: 14 }}>
            {steps.map((s) => (
              <Link key={s.label} href={s.href} className="row" style={{ display: "flex" }}>
                <span className="name" style={{ color: s.done ? "var(--muted)" : "var(--text)" }}>
                  {s.done ? "✓ " : "○ "}{s.label}
                </span>
                {!s.done && <span className="mono" style={{ color: "var(--signal)", fontSize: 13 }}>Set up →</span>}
              </Link>
            ))}
          </div>
        </section>
      )}

      <section style={{ padding: "32px 0 8px" }}>
        <div className="eyebrow">Your buddy's paper book</div>
        <div className="cards" style={{ marginTop: 16 }}>
          <div className="card"><div className="label">Equity</div><div className="val">${now.toFixed(2)}</div></div>
          <div className="card"><div className="label">Return</div>
            <div className={`val ${ret >= 0 ? "pos" : "neg"}`}>{ret >= 0 ? "+" : ""}{ret.toFixed(2)}%</div></div>
          <div className="card"><div className="label">Trades logged</div><div className="val">{trades?.length ?? 0}</div></div>
        </div>
        <div style={{ marginTop: 16 }}><EquityChart values={equity} /></div>
      </section>

      <section className="section">
        <h2>Recent messages</h2>
        <p className="sub">Everything your buddy flagged, newest first.</p>
        <div className="thread">
          {(trades ?? []).length === 0 && (
            <div className="note">No activity yet. Once your keys are in and the market's open,
              your buddy starts texting you ideas — and they'll show up here too.</div>
          )}
          {(trades ?? []).map((t: any) => (
            <BuddyMessage key={t.id} conf={t.confidence ? `${Math.round(t.confidence * 100)}%` : undefined}
              tone={t.action === "SELL" ? "gain" : "signal"}>
              <b>{t.action} {t.symbol}</b> {t.detail ? `· ${t.detail}` : ""} <span className="muted">[{t.mode}]</span>
              <br />{t.rationale}
            </BuddyMessage>
          ))}
        </div>
      </section>
    </>
  );
}
