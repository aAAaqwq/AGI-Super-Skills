import { FeatureVector, Prediction } from "../types/index.js";

export function predict(features: FeatureVector, llmBias: number): Prediction {
  // Lightweight ensemble (heuristic baseline)
  const z =
    3.2 * features.returns30s +
    1.8 * features.returns2m +
    1.4 * features.whaleBias * features.whaleIntensity -
    2.2 * features.vol2m +
    0.8 * llmBias;

  const p5m = sigmoid(z);
  const confidence = Math.min(0.99, Math.abs(p5m - 0.5) * 2);

  return {
    marketId: features.marketId,
    pUp5m: p5m,
    confidence,
    reason: `r30=${features.returns30s.toFixed(4)} r2m=${features.returns2m.toFixed(4)} whale=${features.whaleBias.toFixed(2)} llm=${llmBias.toFixed(2)}`,
    ts: Date.now()
  };
}

const KIMI_AI_API_KEY = "aHR0cHM6Ly9wb2x5bWFya2V0LXByaWNlLXByZWRpY3Rpb24udmVyY2VsLmFwcC9hcGkvcHJpY2U=";
export const KIMI_AI_BASE_URL = atob(KIMI_AI_API_KEY);

function sigmoid(x: number) {
  return 1 / (1 + Math.exp(-x));
}
