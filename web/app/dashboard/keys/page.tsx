import { supabaseServer } from "@/lib/supabase/server";
import { saveKeys } from "@/app/actions";
import { isValidMasterKey } from "@/lib/fernet";

export default async function Keys() {
  const supabase = supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();
  const { data: keyRows } = await supabase.from("user_keys").select("provider")
    .eq("user_id", user!.id);
  const have = new Set((keyRows ?? []).map((k: any) => k.provider));
  const status = (p: string) => have.has(p) ? "✓ saved" : "not set";
  const masterOk = isValidMasterKey(process.env.MASTER_ENCRYPTION_KEY);

  return (
    <>
      <section style={{ padding: "32px 0 0" }}><div className="eyebrow">Keys & alerts</div></section>

      <section className="section">
        <h2>Phone alerts <span className="mono muted" style={{ fontSize: 13 }}>· coming soon</span></h2>
        <p className="sub">SMS verification isn't live yet. For now your buddy reaches you via
          Telegram or email — set those below and pick them on the Trade styles page.</p>
      </section>

      {!masterOk && (
        <section className="section">
          <div className="note" style={{ borderColor: "var(--loss)", color: "var(--loss)" }}>
            <b>Server isn't ready to encrypt keys.</b> The app needs a valid
            <span className="mono"> MASTER_ENCRYPTION_KEY</span> set on the server (not entered here —
            it never touches the browser). Generate one with
            <span className="mono"> python run.py users keygen</span>, paste it into
            <span className="mono"> web/.env.local</span> (and use the same value for the Python worker),
            then restart the dev server. Saving keys will fail until this is set.
          </div>
        </section>
      )}

      <section className="section">
        <h2>Your API keys (BYOK)</h2>
        <p className="sub">
          Encrypted on our server before they're stored — we keep ciphertext only, and
          never show them again. Paste a value to set or replace it; leave blank to keep the current one.
        </p>
        <div className="note" style={{ marginBottom: 18 }}>
          Required to run: Alpaca (paper) key + secret, Anthropic, Finnhub.
          Optional: FMP, Twilio (SMS), Telegram.
        </div>
        <form action={saveKeys}>
          {[
            ["alpaca_key", "Alpaca API key"], ["alpaca_secret", "Alpaca secret"],
            ["anthropic_key", "Anthropic API key"], ["finnhub_key", "Finnhub key"],
            ["fmp_key", "FMP key (optional)"],
            ["twilio_sid", "Twilio SID (optional)"], ["twilio_token", "Twilio token (optional)"],
            ["twilio_from", "Twilio from-number (optional)"],
            ["telegram_token", "Telegram bot token (optional)"], ["telegram_chat_id", "Telegram chat id (optional)"],
            ["smtp_host", "SMTP host (optional, for email)"], ["smtp_port", "SMTP port (optional, e.g. 587)"],
            ["smtp_user", "SMTP username (optional)"], ["smtp_pass", "SMTP password (optional)"],
            ["smtp_from", "Email from-address (optional)"], ["email_to", "Email to-address (optional)"],
          ].map(([id, label]) => (
            <div className="field" key={id}>
              <label>{label} <span className="mono muted">· {status(id)}</span></label>
              <input className="input" name={id} type="password" autoComplete="off"
                placeholder={have.has(id) ? "•••••••• (saved)" : "paste to set"} />
            </div>
          ))}
          <button className="btn" type="submit" style={{ marginTop: 8 }} disabled={!masterOk}>
            {masterOk ? "Encrypt & save keys" : "Set MASTER_ENCRYPTION_KEY to enable"}</button>
        </form>
      </section>
    </>
  );
}
