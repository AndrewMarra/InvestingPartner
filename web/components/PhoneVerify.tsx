"use client";
import { useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";
import { setVerifiedPhone } from "@/app/actions";

export function PhoneVerify({ initialPhone }: { initialPhone: string }) {
  const [phone, setPhone] = useState(initialPhone || "");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"enter" | "code" | "done">(initialPhone ? "done" : "enter");
  const [msg, setMsg] = useState("");
  const supabase = supabaseBrowser();

  async function sendCode() {
    setMsg("");
    const { error } = await supabase.auth.updateUser({ phone });
    if (error) setMsg(error.message); else { setStep("code"); setMsg("Code sent. Check your texts."); }
  }
  async function verify() {
    setMsg("");
    const { error } = await supabase.auth.verifyOtp({ phone, token: code, type: "phone_change" });
    if (error) { setMsg(error.message); return; }
    await setVerifiedPhone(phone);
    setStep("done"); setMsg("Phone verified ✓");
  }

  if (step === "done") {
    return (
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 14 }}>{phone}</span>
        <span className="mono" style={{ color: "var(--gain)", fontSize: 13 }}>verified ✓</span>
        <button className="btn ghost" onClick={() => setStep("enter")}>Change</button>
      </div>
    );
  }
  return (
    <div style={{ maxWidth: 420 }}>
      {step === "enter" ? (
        <div style={{ display: "flex", gap: 12 }}>
          <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)}
            placeholder="+15551234567" />
          <button className="btn" onClick={sendCode}>Send code</button>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 12 }}>
          <input className="input" value={code} onChange={(e) => setCode(e.target.value)}
            placeholder="6-digit code" inputMode="numeric" />
          <button className="btn" onClick={verify}>Verify</button>
        </div>
      )}
      {msg && <div className="note" style={{ marginTop: 10 }}>{msg}</div>}
      <p className="mono muted" style={{ fontSize: 11, marginTop: 8 }}>
        Requires an SMS provider configured in Supabase Auth.
      </p>
    </div>
  );
}
