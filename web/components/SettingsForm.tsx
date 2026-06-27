"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { saveSettings, setPaused as setPausedAction } from "@/app/actions";

const MODES = [
  ["equity_short", "Short-term shares", "Hold for days to weeks"],
  ["equity_day", "Day trades", "In and out the same day"],
  ["equity_long", "Long-term holds", "Positions held for months"],
  ["option_short", "Short-term options", "Includes 0DTE — high risk"],
  ["option_long", "Long-dated options", "LEAPS, months out"],
];
const HORIZONS = [
  ["intraday_1d", "Intraday"], ["daily", "Daily"], ["multiday", "A few days"],
  ["weekly", "Weekly"], ["monthly", "Monthly"],
];
const CHANNELS = [["sms", "Text message"], ["telegram", "Telegram"], ["email", "Email"]];

export function SettingsForm({ initial, initialPaused = false }: { initial: any; initialPaused?: boolean }) {
  const m = initial?.modes ?? {};
  const [modes, setModes] = useState<string[]>(m.enabled ?? ["equity_short"]);
  const [horizon, setHorizon] = useState<string>(m.short_term_horizon ?? "daily");
  const [channels, setChannels] = useState<string[]>(initial?.notify?.channels ?? ["sms"]);
  const [signalsOnly, setSignalsOnly] = useState<boolean>(!!initial?.trading?.signals_only);
  const [capital, setCapital] = useState<string>(String(initial?.portfolio?.starting_capital ?? 100000));
  const [paused, setPaused] = useState<boolean>(initialPaused);
  const [pausing, setPausing] = useState(false);
  const [saved, setSaved] = useState(false);
  const router = useRouter();

  // Re-sync with the server's value whenever the page re-renders with fresh data
  // (after revalidation or a cached/prefetched navigation), so the pause label can
  // never get stuck on a stale state like it could when seeded only once.
  useEffect(() => { setPaused(initialPaused); }, [initialPaused]);

  const toggle = (arr: string[], v: string, set: (x: string[]) => void) =>
    set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  async function togglePause() {
    if (pausing) return;
    const next = !paused;
    setPaused(next);                 // optimistic flip
    setPausing(true);
    try {
      await setPausedAction(next);
      router.refresh();              // reconcile the label with the server truth
    } finally {
      setPausing(false);
    }
  }

  async function save() {
    const cap = Math.max(1000, Math.min(10_000_000, Number(capital) || 100000));
    const next = {
      ...initial,
      modes: { enabled: modes.length ? modes : ["equity_short"], short_term_horizon: horizon },
      notify: { ...(initial?.notify ?? {}), channels },
      trading: { ...(initial?.trading ?? {}), signals_only: signalsOnly },
      portfolio: { ...(initial?.portfolio ?? {}), starting_capital: cap },
    };
    await saveSettings(next);
    setSaved(true); setTimeout(() => setSaved(false), 2500);
  }

  return (
    <>
      <section className="section">
        <div className="row">
          <div>
            <div className="name">{paused ? "Buddy is paused" : "Buddy is running"}</div>
            <div className="desc">Pause to stop your buddy from analysing or trading. It resumes the moment you switch this back on.</div>
          </div>
          <button className={`switch ${paused ? "" : "on"}`} onClick={togglePause}
            disabled={pausing} aria-pressed={!paused} aria-label="Buddy running"><span className="knob" /></button>
        </div>
      </section>

      <section className="section">
        <h2>Trade styles</h2>
        <p className="sub">Your buddy only proposes and trades the styles you turn on.</p>
        {MODES.map(([id, name, desc]) => (
          <div className="row" key={id}>
            <div><div className="name">{name}</div><div className="desc">{desc}</div></div>
            <button className={`switch ${modes.includes(id) ? "on" : ""}`}
              onClick={() => toggle(modes, id, setModes)} aria-pressed={modes.includes(id)}
              aria-label={name}><span className="knob" /></button>
          </div>
        ))}
      </section>

      <section className="section">
        <h2>What "short term" means to you</h2>
        <p className="sub">Sets the default hold time for short-term trades.</p>
        <div className="chips">
          {HORIZONS.map(([id, label]) => (
            <button key={id} className={`chip ${horizon === id ? "on" : ""}`}
              onClick={() => setHorizon(id)}>{label}</button>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>How you get alerts</h2>
        <p className="sub">A phone number is required (add it on Keys & alerts). Pick any channels.</p>
        <div className="chips">
          {CHANNELS.map(([id, label]) => (
            <button key={id} className={`chip ${channels.includes(id) ? "on" : ""}`}
              onClick={() => toggle(channels, id, setChannels)}>{label}</button>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>Signals only</h2>
        <p className="sub">When on, your buddy still texts you its ideas but never paper-trades them — pure heads-up mode.</p>
        <div className="row">
          <div><div className="name">Don't paper-trade, just alert me</div></div>
          <button className={`switch ${signalsOnly ? "on" : ""}`} onClick={() => setSignalsOnly(!signalsOnly)}
            aria-pressed={signalsOnly} aria-label="Signals only"><span className="knob" /></button>
        </div>
      </section>

      <section className="section">
        <h2>Starting capital</h2>
        <p className="sub">The paper book size used to measure your buddy's return. ($1,000 – $10,000,000.)</p>
        <input className="input" type="number" min={1000} max={10000000} step={1000}
          value={capital} onChange={(e) => setCapital(e.target.value)} style={{ maxWidth: 220 }} />
      </section>

      <div style={{ padding: "24px 0", display: "flex", gap: 14, alignItems: "center" }}>
        <button className="btn" onClick={save}>Save changes</button>
        {saved && <span className="mono" style={{ color: "var(--gain)", fontSize: 13 }}>Saved ✓</span>}
      </div>
    </>
  );
}
