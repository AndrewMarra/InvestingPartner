// A single, read-only Anthropic call for the "buddy's take" on a ticker.
// Advisory only — it NEVER places a trade. Acting overrides go through the
// risk-checked Python worker (see /api/consult). Calls the REST API directly so
// the web app needs no extra SDK dependency.
import type { UserKeys } from "@/lib/keys";
import type { TickerData } from "@/lib/ticker";

const ADVISORY_TOOL = {
  name: "take",
  description: "Your honest read on one ticker. No trade is placed.",
  input_schema: {
    type: "object",
    properties: {
      verdict: { type: "string", enum: ["buy", "add", "hold", "trim", "sell", "avoid"] },
      reasoning: { type: "string" },
    },
    required: ["verdict", "reasoning"],
  },
} as const;

const SYSTEM = `You are an AI trading buddy giving a quick, honest read on ONE ticker \
for a friend who makes all real-money decisions themselves. Use ONLY the data \
provided — never invent prices, facts, or catalysts. Be candid: 'avoid' or 'hold' \
are fine answers. You have no short-term price edge, so lean on explainable setups \
(trend, momentum, valuation, catalysts) and sane risk/reward. This is not financial \
advice. Reply via the 'take' tool.`;

export async function advisoryTake(data: TickerData, keys: UserKeys, model: string)
  : Promise<{ verdict: string; reasoning: string }> {
  if (!keys.anthropic_key) throw new Error("Add your Anthropic key on the Keys page first.");

  const briefing = {
    symbol: data.symbol, quote: data.quote, technicals: data.technicals,
    recent_closes: data.closes, fundamentals: data.fundamentals,
    headlines: data.news.map((n) => n.headline),
  };

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": keys.anthropic_key,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model,
      max_tokens: 1024,
      system: SYSTEM,
      tools: [ADVISORY_TOOL],
      tool_choice: { type: "tool", name: "take" },
      messages: [{
        role: "user",
        content: "Give your take via the take tool:\n```json\n" +
          JSON.stringify(briefing, null, 2) + "\n```",
      }],
    }),
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Anthropic error ${res.status}: ${body.slice(0, 200)}`);
  }
  const j = await res.json();
  const block = (j.content ?? []).find((b: any) => b.type === "tool_use" && b.name === "take");
  if (!block) throw new Error("No take returned");
  return { verdict: String(block.input.verdict), reasoning: String(block.input.reasoning) };
}
