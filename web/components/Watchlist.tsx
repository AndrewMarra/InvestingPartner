"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { setWatchlist } from "@/app/actions";
import { DEFAULT_UNIVERSE } from "@/lib/universe";

const clean = (s: string) => s.trim().toUpperCase().replace(/[^A-Z.\-]/g, "").slice(0, 12);

export function Watchlist({ initial }: { initial: string[] }) {
  const [symbols, setSymbols] = useState<string[]>(initial ?? []);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  // Re-sync with the server's value when it actually changes (keyed on content,
  // not array identity, so a fresh `[]` each render doesn't clobber local state).
  const initialKey = (initial ?? []).join(",");
  useEffect(() => { setSymbols(initial ?? []); }, [initialKey]);

  const usingDefaults = symbols.length === 0;

  // Persist on every add/remove — no separate Save step, so the DB always matches.
  async function persist(next: string[]) {
    setSymbols(next);            // optimistic
    setBusy(true);
    try {
      const saved = await setWatchlist(next);
      setSymbols(saved);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  function add() {
    const s = clean(input);
    setInput("");
    if (!s) return;
    if (symbols.length === 0) {
      // First customization: seed the defaults (+ the new pick) and persist, so a
      // single add never shrinks the buddy's list to one symbol.
      persist(DEFAULT_UNIVERSE.includes(s) ? [...DEFAULT_UNIVERSE] : [...DEFAULT_UNIVERSE, s]);
      return;
    }
    if (symbols.includes(s)) return;
    persist([...symbols, s]);
  }
  function remove(s: string) { persist(symbols.filter((x) => x !== s)); }

  return (
    <section className="section">
      <h2>Watchlist {busy && <span className="mono muted" style={{ fontSize: 12 }}>· saving…</span>}</h2>
      <p className="sub">The tickers your buddy considers each cycle — saved instantly. Add them here
        or from Explore; click a tag to remove it. An empty list means your buddy uses the default set.</p>

      {usingDefaults ? (
        <div className="note" style={{ marginBottom: 14 }}>
          You're on the default watchlist: <span className="mono">{DEFAULT_UNIVERSE.join(", ")}</span>.
          {" "}Add a ticker below (or from Explore) to start your own.
        </div>
      ) : (
        <div className="chips" style={{ marginBottom: 14 }}>
          {symbols.map((s) => (
            <button key={s} className="chip on" onClick={() => remove(s)} disabled={busy} title="Remove">{s} ✕</button>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <input className="input" placeholder="Add ticker (e.g. AAPL)" value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
          style={{ textTransform: "uppercase", maxWidth: 200 }} />
        <button className="btn" onClick={add} disabled={busy}>Add</button>
      </div>
    </section>
  );
}
