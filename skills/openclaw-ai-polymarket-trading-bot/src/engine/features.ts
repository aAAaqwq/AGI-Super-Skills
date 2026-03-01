import { FeatureVector, MarketTick, WhaleFlow } from "../types/index.js";

export function buildFeatures(ticks: MarketTick[], whale: WhaleFlow): FeatureVector {
  if (ticks.length < 3) throw new Error("Not enough ticks");
  const latest = ticks[ticks.length - 1];

  const pNow = latest.yesPrice;
  const p30 = ticks[Math.max(0, ticks.length - 4)].yesPrice;
  const p2m = ticks[Math.max(0, ticks.length - 13)].yesPrice;

  const returns30s = safeRet(pNow, p30);
  const returns2m = safeRet(pNow, p2m);

  const window = ticks.slice(Math.max(0, ticks.length - 13));
  const vol2m = stdev(window.map((t) => t.yesPrice));

  const whaleBias = whale.grossNotional > 0 ? whale.netYesNotional / whale.grossNotional : 0;
  const whaleIntensity = Math.min(1, whale.grossNotional / 5000);

  return {
    marketId: latest.marketId,
    yesPrice: pNow,
    returns30s,
    returns2m,
    vol2m,
    whaleBias,
    whaleIntensity,
    ts: Date.now()
  };
}

function safeRet(a: number, b: number) {
  return b === 0 ? 0 : (a - b) / b;
}

function stdev(arr: number[]) {
  if (!arr.length) return 0;
  const m = arr.reduce((s, x) => s + x, 0) / arr.length;
  const v = arr.reduce((s, x) => s + (x - m) ** 2, 0) / arr.length;
  return Math.sqrt(v);
}
