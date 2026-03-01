import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('status-badge')
export class StatusBadge extends LitElement {
  @property({ type: String }) status: 'ok' | 'warn' | 'bad' | 'unknown' = 'unknown';
  @property({ type: String }) label = '';

  static styles = css`
    :host { display: inline-flex; align-items: center; gap: 4px; }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .dot.ok { background: #22c55e; }
    .dot.warn { background: #eab308; }
    .dot.bad { background: #ef4444; }
    .dot.unknown { background: #666; }
    .text {
      font-size: 11px;
      font-weight: 500;
    }
  `;

  render() {
    return html`
      <span class="dot ${this.status}"></span>
      <span class="text">${this.label}</span>
    `;
  }
}
