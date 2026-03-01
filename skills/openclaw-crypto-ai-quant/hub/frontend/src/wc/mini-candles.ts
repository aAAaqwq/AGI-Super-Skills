import { LitElement, html, css, type PropertyValues } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import type { CandleData } from '../lib/api';

@customElement('mini-candles')
export class MiniCandles extends LitElement {
  @property({ type: Array }) candles: CandleData[] = [];
  @property({ type: Number }) width = 200;
  @property({ type: Number }) height = 56;
  @property({ type: Boolean }) live = false;

  static styles = css`
    :host { display: inline-block; }
    canvas { width: 100%; height: 100%; }
  `;

  protected willUpdate(changed: PropertyValues<this>) {
    if (changed.has('candles') && typeof this.candles === 'string') {
      try { this.candles = JSON.parse(this.candles as any); } catch { this.candles = []; }
    }
  }

  updated() {
    this.draw();
  }

  private draw() {
    const canvas = this.shadowRoot?.querySelector('canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = this.width;
    const h = this.height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const bars = this.candles;
    if (!bars || bars.length < 2) return;

    // Price range with 4% padding
    let pMin = Infinity, pMax = -Infinity;
    let vMax = 0;
    for (const b of bars) {
      if (b.l < pMin) pMin = b.l;
      if (b.h > pMax) pMax = b.h;
      if (b.v > vMax) vMax = b.v;
    }
    const pRange = pMax - pMin || 1;
    const pad = pRange * 0.04;
    pMin -= pad;
    pMax += pad;
    const totalRange = pMax - pMin;

    const volZone = h * 0.18;
    const priceH = h - volZone;

    const n = bars.length;
    const slot = w / n;
    const barW = Math.max(1, Math.min(slot * 0.7, 6));
    const halfBar = barW / 2;

    const GREEN = '#22c55e';
    const RED = '#ef4444';

    // Volume bars (bottom zone)
    if (vMax > 0) {
      for (let i = 0; i < n; i++) {
        const b = bars[i];
        const x = (i + 0.5) * slot;
        const up = b.c >= b.o;
        const vh = (b.v / vMax) * volZone;
        ctx.fillStyle = up ? 'rgba(34,197,94,0.18)' : 'rgba(239,68,68,0.18)';
        ctx.fillRect(x - halfBar, h - vh, barW, vh);
      }
    }

    // Price candles
    for (let i = 0; i < n; i++) {
      const b = bars[i];
      const x = (i + 0.5) * slot;
      const up = b.c >= b.o;
      const isLast = this.live && i === n - 1;

      const yHigh = ((pMax - b.h) / totalRange) * priceH;
      const yLow = ((pMax - b.l) / totalRange) * priceH;
      const yOpen = ((pMax - b.o) / totalRange) * priceH;
      const yClose = ((pMax - b.c) / totalRange) * priceH;

      const bodyTop = Math.min(yOpen, yClose);
      const bodyH = Math.max(1, Math.abs(yClose - yOpen));
      const color = up ? GREEN : RED;

      if (isLast) {
        ctx.globalAlpha = 0.55;
      }

      // Wick
      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, yHigh);
      ctx.lineTo(x, yLow);
      ctx.stroke();

      // Body
      ctx.fillStyle = color;
      ctx.fillRect(x - halfBar, bodyTop, barW, bodyH);

      if (isLast) {
        ctx.globalAlpha = 1;
        // Subtle glow stroke for live candle
        ctx.strokeStyle = color;
        ctx.lineWidth = 0.5;
        ctx.strokeRect(x - halfBar - 0.5, bodyTop - 0.5, barW + 1, bodyH + 1);
      }
    }
  }

  render() {
    return html`<canvas></canvas>`;
  }
}
