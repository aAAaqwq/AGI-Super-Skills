import { LitElement, html, css, type PropertyValues } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('sparkline-chart')
export class SparklineChart extends LitElement {
  @property({ type: Array }) points: number[] = [];
  @property({ type: Number }) width = 200;
  @property({ type: Number }) height = 40;
  @property({ type: String }) color = '#3b82f6';

  static styles = css`
    :host { display: inline-block; }
    canvas { width: 100%; height: 100%; }
  `;

  protected willUpdate(changed: PropertyValues<this>) {
    if (changed.has('points') && typeof this.points === 'string') {
      try { this.points = JSON.parse(this.points as any); } catch { this.points = []; }
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

    const pts = this.points;
    if (!pts || pts.length < 2) return;

    let min = Infinity, max = -Infinity;
    for (const v of pts) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
    const range = max - min || 1;
    const pad = 2;

    // Draw area
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const x = (i / (pts.length - 1)) * w;
      const y = pad + ((max - pts[i]) / range) * (h - pad * 2);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    // Stroke line
    ctx.strokeStyle = this.color;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Fill area
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = this.color + '20'; // 12% alpha
    ctx.fill();
  }

  render() {
    return html`<canvas></canvas>`;
  }
}
