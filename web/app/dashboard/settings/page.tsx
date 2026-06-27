import { supabaseServer } from "@/lib/supabase/server";
import { SettingsForm } from "@/components/SettingsForm";

export default async function Settings() {
  const supabase = supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();
  const [{ data }, { data: profile }] = await Promise.all([
    supabase.from("user_settings").select("settings").eq("user_id", user!.id).maybeSingle(),
    supabase.from("profiles").select("paused").eq("id", user!.id).maybeSingle(),
  ]);
  return (
    <>
      <section style={{ padding: "32px 0 0" }}>
        <div className="eyebrow">Trade styles</div>
      </section>
      <SettingsForm initial={data?.settings ?? {}} initialPaused={!!profile?.paused} />
    </>
  );
}
