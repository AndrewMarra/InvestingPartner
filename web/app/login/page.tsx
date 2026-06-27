"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabaseBrowser } from "@/lib/supabase/client";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [sent, setSent] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const supabase = supabaseBrowser();

  async function passwordAuth() {
    setErr(""); setMsg(""); setBusy(true);
    try {
      if (mode === "signin") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) { setErr(error.message); return; }
        router.push("/dashboard");
      } else {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) { setErr(error.message); return; }
        if (data.session) router.push("/dashboard");          // email confirmation off
        else setMsg("Account created. If email confirmation is on, confirm via the link we emailed, then sign in.");
      }
    } finally { setBusy(false); }
  }

  async function sendLink() {
    setErr(""); setMsg("");
    const { error } = await supabase.auth.signInWithOtp({
      email, options: { emailRedirectTo: `${location.origin}/auth/callback` },
    });
    if (error) setErr(error.message); else setSent(true);
  }

  return (
    <div className="shell" style={{ maxWidth: 420, paddingTop: 80 }}>
      <Link href="/" className="brand" style={{ fontSize: 18 }}>trading<b style={{ color: "var(--signal)" }}>buddy</b></Link>
      <h1 style={{ fontSize: 30, margin: "28px 0 6px" }}>{mode === "signin" ? "Sign in" : "Create account"}</h1>
      <p className="muted" style={{ fontSize: 14, marginBottom: 24 }}>
        Use an email + password, or get a one-tap link. You'll add your phone and API keys next.
      </p>

      <div className="field">
        <label>Email</label>
        <input className="input" type="email" value={email}
          onChange={(e) => setEmail(e.target.value)} placeholder="you@email.com" autoComplete="email" />
      </div>
      <div className="field">
        <label>Password</label>
        <input className="input" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)} placeholder="••••••••"
          autoComplete={mode === "signin" ? "current-password" : "new-password"}
          onKeyDown={(e) => { if (e.key === "Enter") passwordAuth(); }} />
      </div>

      {err && <div className="note" style={{ borderColor: "var(--loss)", color: "var(--loss)" }}>{err}</div>}
      {msg && <div className="note">{msg}</div>}

      <button className="btn" style={{ width: "100%", marginTop: 8 }} onClick={passwordAuth} disabled={busy}>
        {busy ? "…" : mode === "signin" ? "Sign in" : "Create account"}
      </button>

      <p className="muted" style={{ fontSize: 13, marginTop: 14 }}>
        {mode === "signin" ? "Need an account? " : "Already have an account? "}
        <button onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setErr(""); setMsg(""); }}
          style={{ background: "none", border: "none", padding: 0, color: "var(--signal)", cursor: "pointer", font: "inherit", textDecoration: "underline" }}>
          {mode === "signin" ? "Create one" : "Sign in"}
        </button>
      </p>

      <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "20px 0 14px" }}>
        <div style={{ flex: 1, height: 1, background: "var(--border, #2a2a2a)" }} />
        <span className="muted" style={{ fontSize: 12 }}>or</span>
        <div style={{ flex: 1, height: 1, background: "var(--border, #2a2a2a)" }} />
      </div>

      {sent ? (
        <div className="note">Check your email for the sign-in link. You can close this tab.</div>
      ) : (
        <button className="btn ghost" style={{ width: "100%" }} onClick={sendLink}>
          Email me a sign-in link instead
        </button>
      )}
    </div>
  );
}
