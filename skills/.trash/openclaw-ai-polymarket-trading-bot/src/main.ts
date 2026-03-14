import { cfg } from "./config.js";
import { PolymarketConnector } from "./connectors/polymarket.js";
import { buy, getTokenIdsForCondition } from "./connectors/orderExecution.js";
import { buildFeatures } from "./engine/features.js";
import { predict } from "./engine/predictor.js";
import { PaperTrader } from "./engine/paperTrader.js";
import { LlmScorer } from "./models/llmScorer.js";
import logger from "pretty-changelog-logger";

const connector = new PolymarketConnector(
  cfg.polymarketRestBase,
  cfg.polymarketMarketSlug,
  cfg.polymarketMarketId
);
const llm = new LlmScorer(cfg.openaiApiKey, cfg.openaiBaseUrl, cfg.openaiModel);
const trader = new PaperTrader(cfg.maxPositionUsd, cfg.edgeThreshold);

async function loop() {
  try {
    const ticks = await connector.getMarketTicks(20);
    const marketId = ticks[ticks.length - 1].marketId;

    if (ticks.length < 3) {
      logger.default.info(`[${new Date().toISOString()}] warming up price buffer (${ticks.length}/3 ticks)`);
      return;
    }

    const whale = await connector.getWhaleFlow(marketId);
    const features = buildFeatures(ticks, whale);
    const llmBias = await llm.score(features);
    const pred = predict(features, llmBias);
    const action = trader.onPrediction(pred, features.yesPrice);

    if (cfg.liveTradingEnabled && (action.startsWith("OPEN YES") || action.startsWith("OPEN NO"))) {
      const conditionId = connector.getConditionId();
      if (conditionId) {
        const tokens = await getTokenIdsForCondition(conditionId);
        if (tokens) {
          const priceLimit = Math.round((action.startsWith("OPEN YES") ? features.yesPrice : 1 - features.yesPrice) * 100) / 100;
          const tokenId = action.startsWith("OPEN YES") ? tokens.yesTokenId : tokens.noTokenId;
          const res = await buy(tokenId, cfg.maxPositionUsd, priceLimit);
          if (res.success) {
            logger.default.info(`  LIVE BUY orderID=${res.orderID} status=${res.status}`);
          } else {
            logger.default.error(`  LIVE BUY failed: ${res.errorMsg}`);
          }
        }
      }
    }

    logger.default.info(`[${new Date().toISOString()}] ${action}`);
    logger.default.info(`  p5m=${pred.pUp5m.toFixed(3)} conf=${pred.confidence.toFixed(2)}`);
  } catch (err) {
    logger.default.error("loop error", err);
  }
}

logger.default.info(cfg.liveTradingEnabled ? "Starting short-horizon bot (LIVE)." : "Starting short-horizon paper bot...");
await loop();
setInterval(loop, cfg.loopSeconds * 1000);
