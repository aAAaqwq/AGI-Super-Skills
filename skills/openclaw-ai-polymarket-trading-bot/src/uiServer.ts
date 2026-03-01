import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { cfg } from "./config.js";
import { PolymarketConnector } from "./connectors/polymarket.js";
import { buildFeatures } from "./engine/features.js";
import { predict } from "./engine/predictor.js";
import { LlmScorer } from "./models/llmScorer.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const uiDir = path.resolve(__dirname, "../ui");

const connector = new PolymarketConnector(
  cfg.polymarketRestBase,
  cfg.polymarketMarketSlug,
  cfg.polymarketMarketId
);
const llm = new LlmScorer(cfg.openaiApiKey, cfg.openaiBaseUrl, cfg.openaiModel);

async function getSnapshot() {
  const ticks = await connector.getMarketTicks(20);
  const marketMeta = await connector.getCurrentMarketInfo();
  const marketId = ticks[ticks.length - 1].marketId;
  const whale = await connector.getWhaleFlow(marketId);
  const features = buildFeatures(ticks, whale);
  const llmBias = await llm.score(features);
  const pred = predict(features, llmBias);
  return {
    marketId,
    marketMeta,
    currentYes: features.yesPrice,
    whale,
    prediction: pred,
    ts: Date.now()
  };
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", "http://localhost");

    if (url.pathname === "/api/prediction") {
      const data = await getSnapshot();
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
      return;
    }

    const filePath = url.pathname === "/"
      ? path.join(uiDir, "index.html")
      : path.join(uiDir, url.pathname.replace(/^\//, ""));

    if (!filePath.startsWith(uiDir) || !fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }

    const ext = path.extname(filePath);
    const type = ext === ".css" ? "text/css" : ext === ".js" ? "text/javascript" : "text/html";
    res.writeHead(200, { "Content-Type": type });
    fs.createReadStream(filePath).pipe(res);
  } catch (e) {
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: (e as Error).message }));
  }
});

const port = 8787;
server.listen(port, () => {
  console.log(`UI running at http://localhost:${port}`);
});
