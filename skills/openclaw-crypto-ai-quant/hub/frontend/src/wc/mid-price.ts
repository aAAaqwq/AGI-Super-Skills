import { LitElement, type PropertyValues, css, html } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

type FlashState = '' | 'up-a' | 'up-b' | 'down-a' | 'down-b';
type Tone = 'table' | 'accent' | 'grid';
type FlashDirection = 'up' | 'down';
type FlashPhase = 'a' | 'b';

type MidFlashTriggerDetail = {
  symbol: string;
  prev: number;
  mid: number;
  direction: FlashDirection;
  phase: FlashPhase;
  tone: Tone;
  at_ms: number;
};

@customElement('mid-price')
export class MidPrice extends LitElement {
  @property({ type: String }) symbol = '';
  @property({ type: String }) value = '';
  @property({ type: Number }) decimals = 6;
  @property({ type: String }) tone: Tone = 'table';
  @property({ type: Number, attribute: 'flash-ms' }) flashMs = 1100;

  @state() private flash: FlashState = '';

  private previousValue: number | null = null;
  private phase: 'a' | 'b' = 'a';
  private clearTimer: ReturnType<typeof setTimeout> | null = null;

  static styles = css`
    :host {
      display: inline-block;
      line-height: 1;
      font-variant-numeric: tabular-nums;
    }

    .value {
      color: var(--text);
      font-family: 'IBM Plex Mono', monospace;
      font-size: 11px;
      font-weight: 500;
    }

    .value.accent {
      color: var(--accent);
      font-size: 13px;
      font-weight: 600;
    }

    .value.grid {
      font-size: inherit;
      font-weight: inherit;
    }

    @keyframes flashUpA {
      0% { color: var(--green); }
      60% { color: var(--green); }
      100% { color: var(--text); }
    }

    @keyframes flashUpB {
      0% { color: var(--green); }
      60% { color: var(--green); }
      100% { color: var(--text); }
    }

    @keyframes flashDownA {
      0% { color: var(--red); }
      60% { color: var(--red); }
      100% { color: var(--text); }
    }

    @keyframes flashDownB {
      0% { color: var(--red); }
      60% { color: var(--red); }
      100% { color: var(--text); }
    }

    @keyframes flashUpAccentA {
      0% { color: var(--green); }
      60% { color: var(--green); }
      100% { color: var(--accent); }
    }

    @keyframes flashUpAccentB {
      0% { color: var(--green); }
      60% { color: var(--green); }
      100% { color: var(--accent); }
    }

    @keyframes flashDownAccentA {
      0% { color: var(--red); }
      60% { color: var(--red); }
      100% { color: var(--accent); }
    }

    @keyframes flashDownAccentB {
      0% { color: var(--red); }
      60% { color: var(--red); }
      100% { color: var(--accent); }
    }

    .value.flash-up-a {
      animation: flashUpA 1s ease-out forwards;
    }

    .value.flash-up-b {
      animation: flashUpB 1s ease-out forwards;
    }

    .value.flash-down-a {
      animation: flashDownA 1s ease-out forwards;
    }

    .value.flash-down-b {
      animation: flashDownB 1s ease-out forwards;
    }

    .value.accent.flash-up-a {
      animation: flashUpAccentA 1s ease-out forwards;
    }

    .value.accent.flash-up-b {
      animation: flashUpAccentB 1s ease-out forwards;
    }

    .value.accent.flash-down-a {
      animation: flashDownAccentA 1s ease-out forwards;
    }

    .value.accent.flash-down-b {
      animation: flashDownAccentB 1s ease-out forwards;
    }
  `;

  protected willUpdate(changed: PropertyValues<this>) {
    if (!changed.has('value')) return;
    const next = this.parseValue(this.value);
    if (next == null) {
      this.previousValue = null;
      return;
    }

    const prev = this.previousValue;
    this.previousValue = next;
    if (prev == null || next === prev) return;

    const dir: FlashDirection = next > prev ? 'up' : 'down';
    this.phase = this.phase === 'a' ? 'b' : 'a';
    const nextState = `${dir}-${this.phase}` as FlashState;
    this.flash = nextState;
    this.dispatchEvent(new CustomEvent<MidFlashTriggerDetail>('mid-flash-trigger', {
      detail: {
        symbol: this.symbol,
        prev,
        mid: next,
        direction: dir,
        phase: this.phase,
        tone: this.tone,
        at_ms: Date.now(),
      },
      bubbles: true,
      composed: true,
    }));

    if (this.clearTimer) clearTimeout(this.clearTimer);
    this.clearTimer = setTimeout(() => {
      if (this.flash === nextState) this.flash = '';
      this.clearTimer = null;
    }, this.flashMs);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.clearTimer) {
      clearTimeout(this.clearTimer);
      this.clearTimer = null;
    }
  }

  private parseValue(raw: string): number | null {
    const trimmed = raw?.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) return null;
    return parsed;
  }

  private formatValue(): string {
    const n = this.parseValue(this.value);
    if (n == null) return '\u2014';
    return n.toLocaleString('en-US', {
      minimumFractionDigits: this.decimals,
      maximumFractionDigits: this.decimals,
    });
  }

  render() {
    const classes = ['value'];
    if (this.tone === 'accent') classes.push('accent');
    if (this.tone === 'grid') classes.push('grid');
    if (this.flash) classes.push(`flash-${this.flash}`);
    return html`<span class="${classes.join(' ')}">${this.formatValue()}</span>`;
  }
}
