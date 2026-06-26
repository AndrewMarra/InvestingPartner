"use client";
import { useState } from "react";
import Link from "next/link";
import { supabaseBrowser } from "@/lib/supabase/client";

export default function Login() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");

  async function sendLink() {
    setErr("");
    const supabase = supabaseBrowser();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${location.origin}/auth/callback` },
    });
    if (error) setErr(error.message); else setSent(true);
  }

  return (
    <div className="shell" style={{ maxWidth: 420, paddingTop: 80 }}>
      <Link href="/" className="brand" style={{ fontSize: 18 }}>trading<b style={{ color: "var(--signal)" }}>buddy</b></Link>
      <h1 style={{ fontSize: 30, margin: "28px 0 6px" }}>Sign in</h1>
      <p className="muted" style={{ fontSize: 14, marginBottom: 24 }}>
        We'll email you a one-tap sign-in link. You'll add your phone and API keys next.
      </p>
      {sent ? (
        <div className="note">Check your email for the sign-in link. You can close this tab.</div>
      ) : (
        <>
          <div className="field">
            <label>Email</label>
            <input className="input" type="email" value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="you@email.com" />
          </div>
          {err && <div className="note" style={{ borderColor: "var(--loss)", color: "var(--loss)" }}>{err}</div>}
          <button className="btn" style={{ width: "100%", marginTop: 8 }} onClick={sendLink}>
            Email me a sign-in link
          </button>
        </>
      )}
    </div>
  );
}
