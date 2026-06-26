import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

// Magic-link / OTP redirect lands here; exchange the code for a session, then
// send the user to the dashboard.
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/dashboard";
  if (code) {
    const supabase = supabaseServer();
    await supabase.auth.exchangeCodeForSession(code);
  }
  return NextResponse.redirect(`${origin}${next}`);
}
