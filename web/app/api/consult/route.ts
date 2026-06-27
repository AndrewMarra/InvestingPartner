import { NextRequest, NextResponse } from "next/server";
import { getUserKeys } from "@/lib/keys";
import { getTickerData, normalizeSymbol } from "@/lib/ticker";
import { advisoryTake } from "@/lib/buddy";
import { supabaseServer } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

const MODEL = process.env.DECISION_MODEL || "claude-sonnet-4-6";
const INTENTS = new Set(["advisory", "hard_buy", "conditional_buy"]);

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const symbol = normalizeSymbol(String(body.symbol || ""));
    const intent = INTENTS.has(body.intent) ? body.intent : "advisory";
    if (!symbol) return NextResponse.json({ error: "Invalid symbol" }, { status: 400 });

    const { userId, keys } = await getUserKeys();

    // Advisory = instant, read-only AI take. No trade, no queue.
    if (intent === "advisory") {
      const data = await getTickerData(symbol, keys);
      const take = await advisoryTake(data, keys, MODEL);
      return NextResponse.json({ mode: "advisory", symbol, ...take });
    }

    // Overrides actually place trades, so they must go through the worker's
    // risk.review — we queue a request the risk-checked worker picks up next cycle.
    const supabase = supabaseServer();
    const { error } = await supabase.from("consult_requests")
      .insert({ user_id: userId, symbol, intent });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });

    return NextResponse.json({
      mode: "queued", symbol, intent,
      message: intent === "conditional_buy"
        ? "Queued. Your buddy will evaluate it and only buy if it agrees — then text you."
        : "Queued. Your buddy will risk-check it and text you before it acts.",
    });
  } catch (e: any) {
    const msg = String(e?.message || e);
    const code = msg.includes("Not signed in") ? 401 : 500;
    return NextResponse.json({ error: msg }, { status: code });
  }
}
