"use server";
import { supabaseServer } from "@/lib/supabase/server";
import { fernetEncrypt } from "@/lib/fernet";
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
  if (!master) throw new Error("Server missing MASTER_ENCRYPTION_KEY");

  const providers = ["alpaca_key", "alpaca_secret", "anthropic_key", "finnhub_key",
    "fmp_key", "twilio_sid", "twilio_token", "twilio_from", "telegram_token", "telegram_chat_id"];
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
