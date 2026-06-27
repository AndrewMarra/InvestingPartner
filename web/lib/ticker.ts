// Read-only ticker analytics for the explore page. Fetches directly from Alpaca
// + Finnhub (+ optional FMP) using the signed-in user's decrypted BYOK keys.
// NEVER places trades. Mirrors aiportfolio/data/market.simple_technicals in TS.
import type { UserKeys } from "@/lib/keys";

export type Technicals = {
  last: number | null; sma10: number | null; sma30: number | null;
  trend: "up" | "down" | null; change_5d_pct: number | null;
};
export type TickerData = {
  symbol: string;
  quote: { price: number | null; changePct: number | null; prevClose: number | null };
  closes: number[];
  technicals: Technicals;
  news: { headline: string; source: string; url: string; summary: string }[];
  fundamentals: Record<string, any> | null;
  notFound?: boolean;
};

// Tiny in-memory cache (per server instance) to respect Finnhub's ~60/min limit.
const CACHE = new Map<string, { at: number; data: TickerData }>();
const TTL_MS = 60_000;

const num = (v: any): number | null =>
  v === null || v === undefined || isNaN(Number(v)) ? null : Number(v);

export function normalizeSymbol(raw: string): string {
  return (raw || "").trim().toUpperCase().replace(/[^A-Z.\-]/g, "").slice(0, 12);
}

export function simpleTechnicals(closes: number[]): Technicals {
  if (closes.length < 10) return { last: closes.at(-1) ?? null, sma10: null, sma30: null, trend: null, change_5d_pct: null };
  const last10 = closes.slice(-10);
  const sma10 = last10.reduce((a, b) => a + b, 0) / 10;
  const sma30 = closes.reduce((a, b) => a + b, 0) / closes.length;
  const change5d = closes.length >= 6 ? (closes.at(-1)! / closes[closes.length - 6] - 1) * 100 : null;
  const r2 = (n: number) => Math.round(n * 100) / 100;
  return {
    last: r2(closes.at(-1)!), sma10: r2(sma10), sma30: r2(sma30),
    trend: sma10 > sma30 ? "up" : "down",
    change_5d_pct: change5d === null ? null : r2(change5d),
  };
}

async function alpacaBars(symbol: string, keys: UserKeys): Promise<number[]> {
  try {
    const start = new Date(Date.now() - 60 * 86400_000).toISOString();
    const url = `https://data.alpaca.markets/v2/stocks/${encodeURIComponent(symbol)}/bars` +
      `?timeframe=1Day&limit=40&adjustment=raw&start=${encodeURIComponent(start)}`;
    const res = await fetch(url, {
      headers: { "APCA-API-KEY-ID": keys.alpaca_key, "APCA-API-SECRET-KEY": keys.alpaca_secret },
      cache: "no-store",
    });
    if (!res.ok) return [];
    const j = await res.json();
    return (j.bars ?? []).map((b: any) => Number(b.c)).filter((n: number) => !isNaN(n));
  } catch { return []; }
}

async function finnhubQuote(symbol: string, keys: UserKeys) {
  try {
    const res = await fetch(
      `https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(symbol)}&token=${keys.finnhub_key}`,
      { cache: "no-store" });
    if (!res.ok) return { price: null, changePct: null, prevClose: null };
    const j = await res.json();
    return { price: num(j.c), changePct: num(j.dp), prevClose: num(j.pc) };
  } catch { return { price: null, changePct: null, prevClose: null }; }
}

async function finnhubNews(symbol: string, keys: UserKeys) {
  try {
    const to = new Date().toISOString().slice(0, 10);
    const from = new Date(Date.now() - 7 * 86400_000).toISOString().slice(0, 10);
    const res = await fetch(
      `https://finnhub.io/api/v1/company-news?symbol=${encodeURIComponent(symbol)}&from=${from}&to=${to}&token=${keys.finnhub_key}`,
      { cache: "no-store" });
    if (!res.ok) return [];
    const j = await res.json();
    return (j ?? []).slice(0, 6).map((it: any) => ({
      headline: it.headline ?? "", source: it.source ?? "",
      url: it.url ?? "", summary: (it.summary ?? "").slice(0, 240),
    }));
  } catch { return []; }
}

async function fmpSnapshot(symbol: string, keys: UserKeys) {
  if (!keys.fmp_key) return null;
  try {
    const [profRes, ratRes] = await Promise.all([
      fetch(`https://financialmodelingprep.com/api/v3/profile/${symbol}?apikey=${keys.fmp_key}`, { cache: "no-store" }),
      fetch(`https://financialmodelingprep.com/api/v3/ratios-ttm/${symbol}?apikey=${keys.fmp_key}`, { cache: "no-store" }),
    ]);
    const prof = profRes.ok ? (await profRes.json())[0] ?? {} : {};
    const rat = ratRes.ok ? (await ratRes.json())[0] ?? {} : {};
    if (!prof.symbol) return null;
    return {
      sector: prof.sector ?? null, industry: prof.industry ?? null,
      market_cap: prof.mktCap ?? null, beta: prof.beta ?? null,
      pe: rat.peRatioTTM ?? null, roe: rat.returnOnEquityTTM ?? null,
      debt_to_equity: rat.debtEquityRatioTTM ?? null,
    };
  } catch { return null; }
}

export async function getTickerData(rawSymbol: string, keys: UserKeys): Promise<TickerData> {
  const symbol = normalizeSymbol(rawSymbol);
  if (!symbol) return emptyData(symbol, true);

  const cached = CACHE.get(symbol);
  if (cached && Date.now() - cached.at < TTL_MS) return cached.data;

  const [closes, quote, news, fundamentals] = await Promise.all([
    alpacaBars(symbol, keys), finnhubQuote(symbol, keys),
    finnhubNews(symbol, keys), fmpSnapshot(symbol, keys),
  ]);

  const notFound = closes.length === 0 && quote.price === null && news.length === 0;
  const data: TickerData = {
    symbol, quote, closes, technicals: simpleTechnicals(closes), news,
    fundamentals, notFound,
  };
  CACHE.set(symbol, { at: Date.now(), data });
  return data;
}

function emptyData(symbol: string, notFound = false): TickerData {
  return {
    symbol, quote: { price: null, changePct: null, prevClose: null }, closes: [],
    technicals: { last: null, sma10: null, sma30: null, trend: null, change_5d_pct: null },
    news: [], fundamentals: null, notFound,
  };
}
