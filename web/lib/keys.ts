// Server-only: load + decrypt the signed-in user's BYOK keys.
// The master key never leaves the server; the browser never sees plaintext keys.
// (Only ever imported from route handlers + server actions.)
import { supabaseServer } from "@/lib/supabase/server";
import { fernetDecrypt } from "@/lib/fernet";

export type UserKeys = Record<string, string>;

export async function getUserKeys(): Promise<{ userId: string; keys: UserKeys }> {
  const supabase = supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error("Not signed in");

  const master = process.env.MASTER_ENCRYPTION_KEY;
  if (!master) throw new Error("Server missing MASTER_ENCRYPTION_KEY");

  const { data: rows } = await supabase
    .from("user_keys")
    .select("provider, ciphertext")
    .eq("user_id", user.id);

  const keys: UserKeys = {};
  for (const r of rows ?? []) {
    try {
      keys[(r as any).provider] = fernetDecrypt((r as any).ciphertext, master);
    } catch {
      /* skip a key that won't decrypt rather than failing the whole request */
    }
  }
  return { userId: user.id, keys };
}
