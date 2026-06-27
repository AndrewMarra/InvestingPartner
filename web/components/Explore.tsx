"use client";
import { useState } from "react";
import { EquityChart } from "@/components/EquityChart";
import { addToWatchlist } from "@/app/actions";

type Data = {
  symbol: string;
  quote: { price: number | null; changePct: number | null; prevClose: number | null };
  closes: number[];
  technicals: { last: number | null; sma10: number | null; sma30: number | null; trend: string | null; change_5d_pct: number | null };
  news: { headline: string; source: string; url: string }[];
  fundamentals: Record<string, any> | null;
  notFound?: boolean;
};

const fmt = (n: number | null | undefined, d = 2) =>
  n === null || n === undefined ? "—" : Number(n).toFixed(d);

export function Explore({ initialWatchlist }: { initialWatchlist: string[] }) {
  const [q, setQ] = useState("");
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [watchlist, setWatchlist] = useState<string[]>(initialWatchlist);

  const [take, setTake] = useState<{ verdict: string; reasoning: string } | null>(null);
  const [takeBusy, setTakeBusy] = useState(false);
  const [overrideMsg, setOverrideMsg] = useState("");

  async function search(e?: React.FormEvent, override?: string) {
    e?.preventDefault();
    const sym = (override ?? q).trim().toUpperCase();
    if (!sym) return;
    setQ(sym);
    setLoading(true); setErr(""); setData(null); setTake(null); setOverrideMsg("");
    try {
      const res = await fetch(`/api/ticker/${encodeURIComponent(sym)}`);
      const j = await res.json();
      if (!res.ok) { setErr(j.error || "Lookup failed"); return; }
      setData(j);
      if (j.notFound) setErr(`No data for ${sym}. Check the symbol.`);
    } catch { setErr("Network error"); }
    finally { setLoading(false); }
  }

  async function getTake() {
    if (!data) return;
    setTakeBusy(true); setTake(null); setErr("");
    try {
      const res = await fetch("/api/consult", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ symbol: data.symbol, intent: "advisory" }),
      });
      const j = await res.json();
      if (!res.ok) { setErr(j.error || "Couldn't get a take"); return; }
      setTake({ verdict: j.verdict, reasoning: j.reasoning });
    } catch { setErr("Network error"); }
    finally { setTakeBusy(false); }
  }

  async function override(intent: "hard_buy" | "conditional_buy") {
    if (!data) return;
    setOverrideMsg("Sending…");
    try {
      const res = await fetch("/api/consult", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ symbol: data.symbol, intent }),
      });
      const j = await res.json();
      setOverrideMsg(res.ok ? (j.message || "Queued.") : (j.error || "Failed"));
    } catch { setOverrideMsg("Network error"); }
  }

  async function watch() {
    if (!data) return;
    const next = await addToWatchlist(data.symbol);
    if (next.length) setWatchlist(next);
  }

  const inWatchlist = data ? watchlist.includes(data.symbol) : false;
  const up = (data?.quote.changePct ?? 0) >= 0;

  return (
    <>
      <section className="section">
        <h2>Explore any ticker</h2>
        <p className="sub">Look up price, trend, news and fundamentals — then ask your buddy. Read-only; no trades are placed here.</p>
        <form onSubmit={search} style={{ display: "flex", gap: 10 }}>
          <input className="input" placeholder="e.g. NVDA" value={q}
            onChange={(e) => setQ(e.target.value)} autoComplete="off"
            style={{ textTransform: "uppercase", maxWidth: 220 }} />
          <button className="btn" type="submit" disabled={loading}>{loading ? "Looking…" : "Search"}</button>
        </form>
        {err && <div className="note" style={{ marginTop: 14, color: "var(--loss)" }}>{err}</div>}
        {watchlist.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div className="mono muted" style={{ fontSize: 12, marginBottom: 6 }}>Your watchlist · tap to view</div>
            <div className="chips">
              {watchlist.map((s) => (
                <button key={s} className="chip" onClick={() => search(undefined, s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
      </section>

      {data && !data.notFound && (
        <>
          <section className="section">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
              <h2 style={{ margin: 0 }}>{data.symbol}</h2>
              <div>
                <span className="val" style={{ fontSize: 26 }}>${fmt(data.quote.price)}</span>{" "}
                <span className={`mono ${up ? "pos" : "neg"}`}>
                  {data.quote.changePct === null ? "" : `${up ? "+" : ""}${fmt(data.quote.changePct)}% today`}
                </span>
              </div>
            </div>
            <div style={{ marginTop: 16 }}><EquityChart values={data.closes} /></div>
            <div className="cards" style={{ marginTop: 16 }}>
              <div className="card"><div className="label">Trend</div><div className="val">{data.technicals.trend ?? "—"}</div></div>
              <div className="card"><div className="label">SMA 10 / 30</div><div className="val" style={{ fontSize: 18 }}>${fmt(data.technicals.sma10)} / ${fmt(data.technicals.sma30)}</div></div>
              <div className="card"><div className="label">5-day move</div>
                <div className={`val ${(data.technicals.change_5d_pct ?? 0) >= 0 ? "pos" : "neg"}`} style={{ fontSize: 18 }}>
                  {data.technicals.change_5d_pct === null ? "—" : `${fmt(data.technicals.change_5d_pct)}%`}</div></div>
            </div>
            <div style={{ marginTop: 16, display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button className="btn" onClick={getTake} disabled={takeBusy}>
                {takeBusy ? "Thinking…" : "Get the buddy's take"}</button>
              <button className={`chip ${inWatchlist ? "on" : ""}`} onClick={watch} disabled={inWatchlist}>
                {inWatchlist ? "✓ In watchlist" : "+ Add to watchlist"}</button>
            </div>
          </section>

          {take && (
            <section className="section">
              <h2>Buddy's take: <span style={{ color: "var(--signal)" }}>{take.verdict.toUpperCase()}</span></h2>
              <p className="sub">{take.reasoning}</p>
              <div className="note" style={{ marginTop: 12 }}>
                Want to act? These go to your buddy, which risk-checks them and texts you before anything happens —
                no trade is placed from this page.
                <div style={{ marginTop: 12, display: "flex", gap: 12, flexWrap: "wrap" }}>
                  <button className="chip" onClick={() => override("conditional_buy")}>Buy — only if you agree</button>
                  <button className="chip" onClick={() => override("hard_buy")}>Buy it (my call)</button>
                </div>
                {overrideMsg && <div className="mono" style={{ marginTop: 12, color: "var(--gain)" }}>{overrideMsg}</div>}
              </div>
            </section>
          )}

          {data.fundamentals && (
            <section className="section">
              <h2>Fundamentals</h2>
              <div className="cards">
                <div className="card"><div className="label">Sector</div><div className="val" style={{ fontSize: 16 }}>{data.fundamentals.sector ?? "—"}</div></div>
                <div className="card"><div className="label">P/E (TTM)</div><div className="val" style={{ fontSize: 18 }}>{fmt(data.fundamentals.pe)}</div></div>
                <div className="card"><div className="label">Beta</div><div className="val" style={{ fontSize: 18 }}>{fmt(data.fundamentals.beta)}</div></div>
              </div>
            </section>
          )}

          <section className="section">
            <h2>Recent headlines</h2>
            {data.news.length === 0 && <div className="note">No recent headlines.</div>}
            <div className="thread">
              {data.news.map((n, i) => (
                <a key={i} href={n.url} target="_blank" rel="noreferrer" className="row" style={{ display: "block" }}>
                  <div className="name">{n.headline}</div>
                  <div className="desc">{n.source}</div>
                </a>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  );
}
