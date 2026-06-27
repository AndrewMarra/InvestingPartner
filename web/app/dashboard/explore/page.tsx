import { supabaseServer } from "@/lib/supabase/server";
import { Explore } from "@/components/Explore";

export const dynamic = "force-dynamic";

export default async function ExplorePage() {
  const supabase = supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();
  const { data } = await supabase.from("user_settings").select("settings")
    .eq("user_id", user!.id).maybeSingle();
  const watchlist: string[] = data?.settings?.research?.candidate_universe ?? [];

  return (
    <>
      <section style={{ padding: "32px 0 0" }}>
        <div className="eyebrow">Explore</div>
      </section>
      <Explore initialWatchlist={watchlist} />
    </>
  );
}
