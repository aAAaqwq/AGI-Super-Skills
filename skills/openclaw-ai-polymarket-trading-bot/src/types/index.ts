export type Side = "YES" | "NO";

export interface MarketTick {
  marketId: string;
  yesPrice: number; // 0..1
  noPrice: number;  // 0..1
  ts: number;
}

export interface WhaleFlow {
  marketId: string;
  netYesNotional: number; // + means YES-biased flow
  grossNotional: number;
  tradeCount: number;
  ts: number;
  topWallets?: Array<{
    wallet: string;
    netYes: number;
    gross: number;
  }>;
}

export interface FeatureVector {
  marketId: string;
  yesPrice: number;
  returns30s: number;
  returns2m: number;
  vol2m: number;
  whaleBias: number; // -1..1
  whaleIntensity: number; // 0..1
  ts: number;
}

export interface Prediction {
  marketId: string;
  pUp5m: number;
  confidence: number;
  reason: string;
  ts: number;
}

export interface Position {
  marketId: string;
  side: Side;
  entryPrice: number;
  sizeUsd: number;
  openedAt: number;
}
