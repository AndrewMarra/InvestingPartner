import { supabaseServer } from "@/lib/supabase/server";
import { saveKeys } from "@/app/actions";
import { PhoneVerify } from "@/components/PhoneVerify";

export default async function Keys() {
  const supabase = supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();
  const { data: profile } = await supabase.from("profiles").select("phone")
    .eq("id", user!.id).maybeSingle();
  const { data: keyRows } = await supabase.from("user_keys").select("provider")
    .eq("user_id", user!.id);
  const have = new Set((keyRows ?? []).map((k: any) => k.provider));
  const status = (p: string) => have.has(p) ? "✓ saved" : "not set";

  return (
    <>
      <section style={{ padding: "32px 0 0" }}><div className="eyebrow">Keys & alerts</div></section>

      <section className="section">
        <h2>Your phone</h2>
        <p className="sub">Required to receive alerts. Used only to text you trade ideas.</p>
        <PhoneVerify initialPhone={profile?.phone ?? ""} />
      </section>

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
          ].map(([id, label]) => (
            <div className="field" key={id}>
              <label>{label} <span className="mono muted">· {status(id)}</span></label>
              <input className="input" name={id} type="password" autoComplete="off"
                placeholder={have.has(id) ? "•••••••• (saved)" : "paste to set"} />
            </div>
          ))}
          <button className="btn" type="submit" style={{ marginTop: 8 }}>Encrypt & save keys</button>
        </form>
      </section>
    </>
  );
}
