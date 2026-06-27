"use server";
import { supabaseServer } from "@/lib/supabase/server";
import { fernetEncrypt, isValidMasterKey } from "@/lib/fernet";
import { DEFAULT_UNIVERSE } from "@/lib/universe";
import { revalidatePath } from "next/cache";

async function uid() {
  const supabase = supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error("Not signed in");
  return { supabase, user };
}

export async function ensureProfile() {
  const { supabase, user } = await uid();
  await supabase.from("profiles").upsert({ id: user.id, email: user.email }, { onConflict: "id" });
}

export async function savePhone(formData: FormData) {
  const { supabase, user } = await uid();
  const phone = String(formData.get("phone") || "").trim();
  await supabase.from("profiles").upsert({ id: user.id, phone }, { onConflict: "id" });
  revalidatePath("/dashboard/keys");
}

export async function saveSettings(settings: any) {
  const { supabase, user } = await uid();
  await supabase.from("user_settings").upsert(
    { user_id: user.id, settings }, { onConflict: "user_id" });
  revalidatePath("/dashboard/settings");
}

// BYOK keys: encrypt with the server-held master key, store ciphertext only.
export async function saveKeys(formData: FormData) {
  const { supabase, user } = await uid();
  const master = process.env.MASTER_ENCRYPTION_KEY;
  if (!isValidMasterKey(master)) {
    // Surfaced by the Keys page banner; this guards direct/edge cases too.
    throw new Error(
      "Server is missing a valid MASTER_ENCRYPTION_KEY. Generate one with " +
      "`python run.py users keygen` and set it in web/.env.local (it must match " +
      "the Python worker's value), then restart the dev server."
    );
  }

  const providers = ["alpaca_key", "alpaca_secret", "anthropic_key", "finnhub_key",
    "fmp_key", "twilio_sid", "twilio_token", "twilio_from", "telegram_token", "telegram_chat_id",
    "smtp_host", "smtp_port", "smtp_user", "smtp_pass", "smtp_from", "email_to"];
  const rows = [];
  for (const p of providers) {
    const v = String(formData.get(p) || "").trim();
    if (!v) continue; // empty = leave existing untouched
    rows.push({ user_id: user.id, provider: p, ciphertext: fernetEncrypt(v, master) });
  }
  if (rows.length) {
    await supabase.from("user_keys").upsert(rows, { onConflict: "user_id,provider" });
  }
  revalidatePath("/dashboard/keys");
}

export async function setVerifiedPhone(phone: string) {
  const { supabase, user } = await uid();
  await supabase.from("profiles").upsert({ id: user.id, phone }, { onConflict: "id" });
}

// Pause/resume the buddy for THIS user (the worker skips paused users each cycle).
export async function setPaused(paused: boolean) {
  const { supabase, user } = await uid();
  await supabase.from("profiles").upsert({ id: user.id, paused }, { onConflict: "id" });
  revalidatePath("/dashboard");
  revalidatePath("/dashboard/settings");
}

const cleanSym = (s: string) =>
  s.trim().toUpperCase().replace(/[^A-Z.\-]/g, "").slice(0, 12);

// Add a ticker to the user's candidate universe so the buddy starts watching it.
// Seeds from the default universe on first add, so adding one symbol doesn't
// silently shrink the buddy's watchlist to just that symbol.
export async function addToWatchlist(symbol: string): Promise<string[]> {
  const { supabase, user } = await uid();
  const sym = cleanSym(symbol);
  if (!sym) return [];
  const { data } = await supabase.from("user_settings").select("settings")
    .eq("user_id", user.id).maybeSingle();
  const settings = data?.settings ?? {};
  let universe: string[] = settings?.research?.candidate_universe ?? [];
  if (universe.length === 0) universe = [...DEFAULT_UNIVERSE];
  if (!universe.includes(sym)) universe.push(sym);
  const next = { ...settings, research: { ...(settings.research ?? {}), candidate_universe: universe } };
  await supabase.from("user_settings").upsert(
    { user_id: user.id, settings: next }, { onConflict: "user_id" });
  revalidatePath("/dashboard");
  revalidatePath("/dashboard/explore");
  return universe;
}

// Replace the user's whole watchlist (used by the Watchlist manager).
export async function setWatchlist(symbols: string[]): Promise<string[]> {
  const { supabase, user } = await uid();
  const clean = Array.from(new Set(symbols.map(cleanSym).filter(Boolean)));
  const { data } = await supabase.from("user_settings").select("settings")
    .eq("user_id", user.id).maybeSingle();
  const settings = data?.settings ?? {};
  const next = { ...settings, research: { ...(settings.research ?? {}), candidate_universe: clean } };
  await supabase.from("user_settings").upsert(
    { user_id: user.id, settings: next }, { onConflict: "user_id" });
  revalidatePath("/dashboard");
  revalidatePath("/dashboard/explore");
  return clean;
}
