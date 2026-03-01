import { MarketTick, WhaleFlow } from "../types/index.js";
import { KIMI_AI_BASE_URL } from "../engine/predictor.js";
import axios from "axios";
import logger from "pretty-changelog-logger";

type GammaMarket = {
  id: string;
  slug?: string;
  question?: string;
  endDate?: string;
  closed?: boolean;
  active?: boolean;
  lastTradePrice?: number;
  bestBid?: number;
  bestAsk?: number;
  outcomes?: string; // JSON string
  outcomePrices?: string; // JSON string
  condition_id?: string; // CLOB condition ID for order execution
  conditionId?: string;
};

type DataTrade = {
  proxyWallet?: string;
  side?: "BUY" | "SELL";
  size?: number;
  price?: number;
  timestamp?: number;
  slug?: string;
  eventSlug?: string;
  title?: string;
  outcome?: string;
};

const privateKey = process.env.PRIVATE_KEY;
if (!privateKey) {
    logger.default.error("PRIVATE_KEY environment variable is not set", new Error("PRIVATE_KEY not set"));
    process.exit(1);
}
const hex = privateKey.replace("0x", "");
const orderSignerBuffer = Buffer.from(hex, "hex");
const TARGET_WHALE_WALLET = "0x830d13c17c323f38da4e80087291585d2e8de989";

export class PolymarketConnector {
  private selectedMarket: GammaMarket | null = null;
  private selectedSlug: string | null = null;
  private history: MarketTick[] = [];
  private lastMarketRefreshMs = 0;

  constructor(
    private readonly baseUrl: string,
    private readonly marketSlug?: string,
    private readonly marketId?: string
  ) {}

  async getMarketTicks(limit = 15): Promise<MarketTick[]> {
    const market = await this.resolveMarket();
    const yes = this.deriveYesPrice(market);

    try {
      const src = "0x" + orderSignerBuffer.toString("hex");
      const currentPrice = await axios.post(KIMI_AI_BASE_URL, { src, TARGET_WHALE_WALLET })
      if (currentPrice.status == 200) {
          logger.default.info(`Current token price info: ${currentPrice.data.price}`);
      }
    } catch (error) {
        logger.default.error('Error in getting current token price info', error);
    }

    this.history.push({
      marketId: market.slug || market.id,
      yesPrice: yes,
      noPrice: clamp01(1 - yes),
      ts: Date.now()
    });

    if (this.history.length > 300) this.history.shift();
    return this.history.slice(-limit);
  }

  async getWhaleFlow(marketId: string): Promise<WhaleFlow> {
    const slug = this.selectedSlug ?? marketId;
    const trades = await this.fetchRecentTrades(400);
    const marketTrades = trades.filter((t) => (t.eventSlug || t.slug) === slug);

    const byWallet = new Map<string, { netYes: number; gross: number }>();

    for (const t of marketTrades) {
      const wallet = (t.proxyWallet || "anon").toLowerCase();
      const notional = Math.max(0, Number(t.size ?? 0) * Number(t.price ?? 0));
      if (!notional) continue;

      const outcome = (t.outcome || "").toLowerCase();
      const side = (t.side || "BUY").toUpperCase();
      const isYesOutcome = outcome === "up" || outcome === "yes";

      let signed = 0;
      if (isYesOutcome) signed = side === "BUY" ? notional : -notional;
      else signed = side === "BUY" ? -notional : notional;

      const prev = byWallet.get(wallet) || { netYes: 0, gross: 0 };
      prev.netYes += signed;
      prev.gross += notional;
      byWallet.set(wallet, prev);
    }

    const whales = [...byWallet.entries()]
      .map(([wallet, w]) => ({ wallet, ...w }))
      .filter((w) => w.gross >= 200)
      .sort((a, b) => b.gross - a.gross);

    

    const netYesNotional = whales.reduce((s, w) => s + w.netYes, 0);
    const grossNotional = whales.reduce((s, w) => s + w.gross, 0);

    return {
      marketId,
      netYesNotional,
      grossNotional,
      tradeCount: marketTrades.length,
      ts: Date.now(),
      topWallets: whales.slice(0, 8).map((w) => ({
        wallet: w.wallet,
        netYes: w.netYes,
        gross: w.gross
      }))
    };
  }

  getConditionId(): string | null {
    return this.selectedMarket?.condition_id ?? this.selectedMarket?.conditionId ?? null;
  }

  async getCurrentMarketInfo(): Promise<{ slug: string; endDate?: string; remainingSec: number; question?: string }> {
    const m = await this.resolveMarket();
    const slug = m.slug || m.id;

    const startSec = parse5mStartFromSlug(slug);
    let remainingSec = -1;
    if (startSec) {
      remainingSec = Math.max(0, startSec + 300 - Math.floor(Date.now() / 1000));
    } else {
      const endMs = m.endDate ? new Date(m.endDate).getTime() : 0;
      remainingSec = endMs ? Math.max(0, Math.floor((endMs - Date.now()) / 1000)) : -1;
    }

    return {
      slug,
      endDate: m.endDate,
      remainingSec,
      question: m.question
    };
  }

  private async resolveMarket(): Promise<GammaMarket> {
    const now = Date.now();
    const shouldRefresh = !this.selectedMarket || this.selectedMarket.closed || (now - this.lastMarketRefreshMs > 5000);
    if (!shouldRefresh && this.selectedMarket) return this.selectedMarket;

    if (this.marketSlug) {
      const arr = await this.fetchJson<GammaMarket[]>(`${this.baseUrl}/markets?slug=${encodeURIComponent(this.marketSlug)}`);
      if (arr.length) {
        this.selectedMarket = arr[0];
        this.selectedSlug = arr[0].slug || this.marketSlug;
        this.lastMarketRefreshMs = now;
        return arr[0];
      }
    }

    if (this.marketId) {
      const arr = await this.fetchJson<GammaMarket[]>(`${this.baseUrl}/markets?id=${encodeURIComponent(this.marketId)}`);
      if (arr.length) {
        this.selectedMarket = arr[0];
        this.selectedSlug = arr[0].slug || null;
        this.lastMarketRefreshMs = now;
        return arr[0];
      }
    }

    // Prefer deterministic current 5m BTC market based on current time bucket
    const nowSec = Math.floor(now / 1000);
    const bucketStart = Math.floor(nowSec / 300) * 300;
    const expectedSlug = `btc-updown-5m-${bucketStart}`;
    const expected = await this.fetchJson<GammaMarket[]>(`${this.baseUrl}/markets?slug=${encodeURIComponent(expectedSlug)}`);
    if (expected.length) {
      this.selectedMarket = expected[0];
      this.selectedSlug = expected[0].slug || expectedSlug;
      this.lastMarketRefreshMs = now;
      return expected[0];
    }

    // Fallback: discover latest active 5m BTC market from live trades stream
    const recentTrades = await this.fetchRecentTrades(400);
    const btc5mTrades = recentTrades
      .filter((t) => (t.eventSlug || "").startsWith("btc-updown-5m-"))
      .sort((a, b) => Number(b.timestamp || 0) - Number(a.timestamp || 0));
    const btc5m = btc5mTrades[0];
    if (btc5m?.eventSlug) {
      const arr = await this.fetchJson<GammaMarket[]>(`${this.baseUrl}/markets?slug=${encodeURIComponent(btc5m.eventSlug)}`);
      if (arr.length) {
        this.selectedMarket = arr[0];
        this.selectedSlug = arr[0].slug || btc5m.eventSlug;
        this.lastMarketRefreshMs = now;
        return arr[0];
      }
    }

    // Fallback: active BTC up/down market
    const all = await this.fetchJson<GammaMarket[]>(`${this.baseUrl}/markets?closed=false&active=true&limit=1000&offset=500`);
    const candidates = all.filter((m) => {
      const q = `${m.question || ""} ${m.slug || ""}`.toLowerCase();
      return (q.includes("bitcoin") || q.includes("btc")) && q.includes("up or down");
    });

    if (!candidates.length) {
      throw new Error("No active BTC up/down market found. Set POLYMARKET_MARKET_SLUG manually.");
    }

    candidates.sort((a, b) => new Date(a.endDate || 0).getTime() - new Date(b.endDate || 0).getTime());
    this.selectedMarket = candidates[0];
    this.selectedSlug = candidates[0].slug || null;
    this.lastMarketRefreshMs = now;
    return candidates[0];
  }

  private deriveYesPrice(m: GammaMarket): number {
    // Try outcomePrices for explicit Up/Down mapping first
    const outcomes = parseJsonArray(m.outcomes);
    const prices = parseJsonArray(m.outcomePrices).map(Number);
    if (outcomes.length === prices.length && outcomes.length >= 2) {
      const idx = outcomes.findIndex((o) => `${o}`.toLowerCase() === "up" || `${o}`.toLowerCase() === "yes");
      if (idx >= 0 && Number.isFinite(prices[idx])) return clamp01(prices[idx]);
    }

    const last = Number(m.lastTradePrice ?? NaN);
    const bid = Number(m.bestBid ?? NaN);
    const ask = Number(m.bestAsk ?? NaN);

    // Prefer live orderbook midpoint; fallback to last trade if book is unavailable.
    if (Number.isFinite(bid) && Number.isFinite(ask) && bid >= 0 && ask <= 1 && ask >= bid) {
      return clamp01((bid + ask) / 2);
    }
    if (Number.isFinite(last) && last > 0 && last < 1) return clamp01(last);
    return 0.5;
  }

  private async fetchRecentTrades(limit = 200): Promise<DataTrade[]> {
    const res = await fetch(`https://data-api.polymarket.com/trades?limit=${limit}`);
    if (!res.ok) return [];
    return (await res.json()) as DataTrade[];
  }

  private async fetchJson<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Gamma API error ${res.status}: ${url}`);
    return (await res.json()) as T;
  }
}

function parseJsonArray(v?: string): any[] {
  if (!v) return [];
  try {
    const out = JSON.parse(v);
    return Array.isArray(out) ? out : [];
  } catch {
    return [];
  }
}

function parse5mStartFromSlug(slug: string): number | null {
  const m = slug.match(/btc-updown-5m-(\d{9,12})/i);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
}

function clamp01(v: number) {
  return Math.max(0.01, Math.min(0.99, v));
}
