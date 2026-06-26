"use client";
import { useState } from "react";
import { saveSettings } from "@/app/actions";

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
const CHANNELS = [["sms", "Text message"], ["telegram", "Telegram"]];

export function SettingsForm({ initial }: { initial: any }) {
  const m = initial?.modes ?? {};
  const [modes, setModes] = useState<string[]>(m.enabled ?? ["equity_short"]);
  const [horizon, setHorizon] = useState<string>(m.short_term_horizon ?? "daily");
  const [channels, setChannels] = useState<string[]>(initial?.notify?.channels ?? ["sms"]);
  const [saved, setSaved] = useState(false);

  const toggle = (arr: string[], v: string, set: (x: string[]) => void) =>
    set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  async function save() {
    const next = { ...initial, modes: { enabled: modes.length ? modes : ["equity_short"], short_term_horizon: horizon },
      notify: { ...(initial?.notify ?? {}), channels } };
    await saveSettings(next);
    setSaved(true); setTimeout(() => setSaved(false), 2500);
  }

  return (
    <>
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

      <div style={{ padding: "24px 0", display: "flex", gap: 14, alignItems: "center" }}>
        <button className="btn" onClick={save}>Save changes</button>
        {saved && <span className="mono" style={{ color: "var(--gain)", fontSize: 13 }}>Saved ✓</span>}
      </div>
    </>
  );
}
