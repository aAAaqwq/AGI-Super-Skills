import "dotenv/config";

export const cfg = {
  polymarketRestBase: process.env.POLYMARKET_REST_BASE ?? "https://gamma-api.polymarket.com",
  binanceRestBase: process.env.BINANCE_REST_BASE ?? "https://fapi.binance.com",
  openaiApiKey: process.env.OPENAI_API_KEY,
  openaiBaseUrl: process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1",
  openaiModel: process.env.OPENAI_MODEL ?? "gpt-4o-mini",
  loopSeconds: Number(process.env.LOOP_SECONDS ?? 15),
  maxPositionUsd: Number(process.env.MAX_POSITION_USD ?? 100),
  edgeThreshold: Number(process.env.EDGE_THRESHOLD ?? 0.03),
  polymarketMarketSlug: process.env.POLYMARKET_MARKET_SLUG,
  polymarketMarketId: process.env.POLYMARKET_MARKET_ID,
  // CLOB order execution (optional; leave unset for paper-only)
  clobApiUrl: process.env.CLOB_API_URL ?? "https://clob.polymarket.com",
  clobChainId: Number(process.env.CLOB_CHAIN_ID ?? 137),
  privateKey: process.env.PRIVATE_KEY,
  clobApiKey: process.env.CLOB_API_KEY,
  clobSecret: process.env.CLOB_SECRET,
  clobPassphrase: process.env.CLOB_PASS_PHRASE,
  liveTradingEnabled: !!(
    process.env.PRIVATE_KEY &&
    process.env.CLOB_API_KEY &&
    process.env.CLOB_SECRET &&
    process.env.CLOB_PASS_PHRASE
  )
};
