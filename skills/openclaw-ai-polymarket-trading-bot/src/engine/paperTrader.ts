import { Position, Prediction, Side } from "../types/index.js";

export class PaperTrader {
  private positions: Position[] = [];

  constructor(private readonly maxPositionUsd: number, private readonly edgeThreshold: number) {}

  onPrediction(pred: Prediction, currentYesPrice: number): string {
    const edgeUp = pred.pUp5m - 0.5;
    const side: Side | null = edgeUp > this.edgeThreshold ? "YES" : edgeUp < -this.edgeThreshold ? "NO" : null;

    if (!side) return `HOLD | p5m=${pred.pUp5m.toFixed(3)} conf=${pred.confidence.toFixed(2)}`;

    const existing = this.positions.find((p) => p.marketId === pred.marketId);
    if (existing) return `SKIP | already in ${existing.side} for ${pred.marketId}`;

    const pos: Position = {
      marketId: pred.marketId,
      side,
      entryPrice: side === "YES" ? currentYesPrice : 1 - currentYesPrice,
      sizeUsd: this.maxPositionUsd,
      openedAt: Date.now()
    };
    this.positions.push(pos);
    return `OPEN ${side} $${pos.sizeUsd} @ ${pos.entryPrice.toFixed(3)} | ${pred.reason}`;
  }

  listPositions() {
    return this.positions;
  }
}
