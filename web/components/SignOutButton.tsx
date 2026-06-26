"use client";
import { useRouter } from "next/navigation";
import { supabaseBrowser } from "@/lib/supabase/client";

export function SignOutButton() {
  const router = useRouter();
  async function out() {
    await supabaseBrowser().auth.signOut();
    router.push("/");
    router.refresh();
  }
  return (
    <button onClick={out} className="navlink-btn"
      style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer",
               font: "inherit", fontSize: 14 }}>
      Sign out
    </button>
  );
}
