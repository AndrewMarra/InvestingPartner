import { NextRequest, NextResponse } from "next/server";
import { getUserKeys } from "@/lib/keys";
import { getTickerData, normalizeSymbol } from "@/lib/ticker";

export const dynamic = "force-dynamic";

export async function GET(_req: NextRequest, { params }: { params: { symbol: string } }) {
  const symbol = normalizeSymbol(params.symbol);
  if (!symbol) return NextResponse.json({ error: "Invalid symbol" }, { status: 400 });
  try {
    const { keys } = await getUserKeys();
    if (!keys.alpaca_key || !keys.finnhub_key) {
      return NextResponse.json(
        { error: "Add your Alpaca + Finnhub keys on the Keys page first." }, { status: 400 });
    }
    const data = await getTickerData(symbol, keys);
    return NextResponse.json(data);
  } catch (e: any) {
    const msg = String(e?.message || e);
    const code = msg.includes("Not signed in") ? 401 : 500;
    return NextResponse.json({ error: msg }, { status: code });
  }
}
