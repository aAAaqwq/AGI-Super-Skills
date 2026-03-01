import { LitElement, html, css, nothing, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  tradePreview,
  tradeExecute,
  tradeClose,
  tradeCancel,
  tradeOpenOrders,
  tradeJobResult,
} from '../lib/api';

type OrdType = 'market' | 'limit_ioc' | 'limit_gtc';

@customElement('trade-panel')
export class TradePanel extends LitElement {
  /* ── Props (HTML attributes — always strings) ─────────────────────────────── */
  @property({ type: String }) symbol = '';
  @property({ type: String }) position = '';
  @property({ type: String }) mid = '';
  @property({ type: String }) mode = '';
  @property({ type: String, attribute: 'engine-running' }) engineRunning = 'false';

  /* ── Internal reactive state ──────────────────────────────────────────────── */
  @state() private expanded = false;
  @state() private tab: 'open' | 'close' = 'open';

  // Open form
  @state() private ordType: OrdType = 'market';
  @state() private side: 'long' | 'short' = 'long';
  @state() private notional = '500';
  @state() private lev = '10';
  @state() private limPx = '';

  // Close form
  @state() private closePct = 100;
  @state() private closeCustom = '';
  @state() private closeOrdType: OrdType = 'market';
  @state() private closeLimPx = '';

  // Preview results
  @state() private openPrev: any = null;
  @state() private openTok = '';
  @state() private closePrev: any = null;
  @state() private closeTok = '';

  // Feedback
  @state() private openBusy = false;
  @state() private openErr = '';
  @state() private openOk = '';
  @state() private closeBusy = false;
  @state() private closeErr = '';
  @state() private closeOk = '';

  // GTC orders
  @state() private orders: any[] = [];

  private _pos: any = null;
  private _poll: ReturnType<typeof setInterval> | null = null;
  private _prevSym = '';

  /* ── Styles ───────────────────────────────────────────────────────────────── */
  static styles = css`
    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 12px;
      color: var(--text, #e0e0e0);
    }

    .panel {
      border: 1px solid var(--border, rgba(255,255,255,0.08));
      border-radius: var(--radius-md, 6px);
      background: var(--surface, #16213e);
      margin-top: 8px;
      overflow: hidden;
    }

    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      cursor: pointer;
      user-select: none;
      background: rgba(255, 170, 0, 0.15);
      border-bottom: 1px solid rgba(255, 170, 0, 0.3);
    }
    .header:hover { background: rgba(255, 170, 0, 0.22); }

    .header-label {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.1em;
      color: #ffaa00;
      font-family: 'IBM Plex Mono', monospace;
    }
    .toggle {
      font-size: 10px;
      color: #ffaa00;
    }

    .warning {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      background: rgba(255, 215, 64, 0.08);
      border-bottom: 1px solid rgba(255, 215, 64, 0.15);
      color: var(--yellow, #ffd740);
      font-size: 11px;
      font-weight: 500;
    }

    .tabs {
      display: flex;
      border-bottom: 1px solid var(--border, rgba(255,255,255,0.08));
    }
    .tab {
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text-muted, #8892b0);
      padding: 7px 0;
      font-size: 10px;
      font-weight: 700;
      font-family: 'IBM Plex Mono', monospace;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      cursor: pointer;
      transition: all 0.15s;
      border-bottom: 2px solid transparent;
    }
    .tab:hover { color: var(--text, #e0e0e0); }
    .tab.active {
      color: var(--accent, #00d4ff);
      border-bottom-color: var(--accent, #00d4ff);
    }
    .tab:disabled {
      opacity: 0.3;
      cursor: not-allowed;
    }

    .body { padding: 10px 12px; }

    .section { margin-bottom: 14px; }
    .section:last-child { margin-bottom: 0; }

    .section-title {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-dim, #5a6a8a);
      margin-bottom: 8px;
      padding-bottom: 4px;
      border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.04));
    }

    .field {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }
    .field label {
      width: 72px;
      flex-shrink: 0;
      font-size: 11px;
      color: var(--text-muted, #8892b0);
    }
    .field .suffix {
      font-size: 11px;
      color: var(--text-muted, #8892b0);
      flex-shrink: 0;
    }

    input[type="text"],
    input[type="number"] {
      flex: 1;
      min-width: 0;
      background: var(--bg, #1a1a2e);
      border: 1px solid var(--border, rgba(255,255,255,0.08));
      color: var(--text, #e0e0e0);
      padding: 5px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-family: 'IBM Plex Mono', monospace;
      -moz-appearance: textfield;
    }
    input:focus {
      outline: none;
      border-color: var(--accent, #00d4ff);
    }
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
      -webkit-appearance: none;
      margin: 0;
    }

    .btn-group {
      display: flex;
      gap: 2px;
      flex: 1;
      background: var(--bg, #1a1a2e);
      border-radius: 4px;
      padding: 2px;
    }
    .btn-group button {
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text-muted, #8892b0);
      padding: 4px 6px;
      font-size: 10px;
      font-weight: 600;
      font-family: 'IBM Plex Mono', monospace;
      cursor: pointer;
      border-radius: 3px;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .btn-group button:hover { color: var(--text, #e0e0e0); }
    .btn-group button.on {
      background: var(--accent, #00d4ff);
      color: var(--bg, #1a1a2e);
    }
    .btn-group button.long.on { background: var(--green, #00e676); }
    .btn-group button.short.on { background: var(--red, #ff5252); }

    .close-pct {
      display: flex;
      gap: 2px;
      flex: 1;
    }
    .close-pct button {
      flex: 1;
      background: var(--bg, #1a1a2e);
      border: 1px solid var(--border, rgba(255,255,255,0.08));
      color: var(--text-muted, #8892b0);
      padding: 4px 6px;
      font-size: 10px;
      font-weight: 600;
      font-family: 'IBM Plex Mono', monospace;
      cursor: pointer;
      border-radius: 3px;
      transition: all 0.15s;
    }
    .close-pct button:hover { color: var(--text, #e0e0e0); }
    .close-pct button.on {
      background: var(--accent, #00d4ff);
      color: var(--bg, #1a1a2e);
      border-color: transparent;
    }
    .close-pct .cust {
      display: flex;
      align-items: center;
      flex: 1;
      gap: 1px;
    }
    .close-pct .cust input {
      width: 40px;
      padding: 3px 4px;
      font-size: 10px;
      text-align: center;
    }
    .close-pct .cust span {
      font-size: 10px;
      color: var(--text-muted, #8892b0);
    }

    .preview-box {
      background: var(--bg, #1a1a2e);
      border: 1px solid var(--border, rgba(255,255,255,0.08));
      border-radius: 4px;
      padding: 8px 10px;
      margin: 8px 0;
    }
    .kv {
      display: flex;
      justify-content: space-between;
      padding: 2px 0;
      font-size: 11px;
    }
    .kv .k { color: var(--text-muted, #8892b0); }
    .kv .v {
      font-family: 'IBM Plex Mono', monospace;
      font-weight: 500;
    }

    .actions {
      display: flex;
      gap: 8px;
      margin-top: 8px;
    }
    .btn {
      padding: 6px 14px;
      border: none;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      font-family: 'IBM Plex Mono', monospace;
      cursor: pointer;
      transition: all 0.15s;
      letter-spacing: 0.02em;
    }
    .btn:disabled {
      opacity: 0.35;
      cursor: not-allowed;
    }
    .btn-secondary {
      background: var(--surface-hover, rgba(255,255,255,0.06));
      color: var(--text, #e0e0e0);
      border: 1px solid var(--border, rgba(255,255,255,0.08));
    }
    .btn-secondary:hover:not(:disabled) { background: rgba(255,255,255,0.1); }
    .btn-danger {
      background: var(--red, #ff5252);
      color: #fff;
    }
    .btn-danger:hover:not(:disabled) { filter: brightness(1.1); }

    .msg {
      padding: 5px 8px;
      border-radius: 4px;
      font-size: 11px;
      margin-top: 6px;
    }
    .msg.err {
      background: rgba(255, 82, 82, 0.1);
      border: 1px solid rgba(255, 82, 82, 0.2);
      color: var(--red, #ff5252);
    }
    .msg.ok {
      background: rgba(0, 230, 118, 0.1);
      border: 1px solid rgba(0, 230, 118, 0.2);
      color: var(--green, #00e676);
    }

    .order-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 5px 0;
      font-size: 11px;
      font-family: 'IBM Plex Mono', monospace;
      border-bottom: 1px solid var(--border-subtle, rgba(255,255,255,0.04));
    }
    .order-row:last-child { border-bottom: none; }
    .order-info {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .order-side {
      font-weight: 600;
      font-size: 10px;
      padding: 1px 4px;
      border-radius: 2px;
    }
    .order-side.buy {
      color: var(--green, #00e676);
      background: rgba(0, 230, 118, 0.1);
    }
    .order-side.sell {
      color: var(--red, #ff5252);
      background: rgba(255, 82, 82, 0.1);
    }
    .btn-cancel {
      background: transparent;
      border: 1px solid rgba(255, 82, 82, 0.3);
      color: var(--red, #ff5252);
      padding: 2px 8px;
      border-radius: 3px;
      font-size: 10px;
      font-family: 'IBM Plex Mono', monospace;
      cursor: pointer;
      font-weight: 500;
    }
    .btn-cancel:hover { background: rgba(255, 82, 82, 0.1); }

    .spinner {
      display: inline-block;
      width: 12px;
      height: 12px;
      border: 2px solid rgba(255,255,255,0.2);
      border-top-color: var(--text, #e0e0e0);
      border-radius: 50%;
      animation: spin 0.6s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `;

  /* ── Lifecycle ────────────────────────────────────────────────────────────── */
  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopPoll();
  }

  protected willUpdate(changed: PropertyValues<this>) {
    if (changed.has('position')) {
      try {
        const raw = this.position?.trim();
        this._pos = raw && raw !== 'null' ? JSON.parse(raw) : null;
      } catch { this._pos = null; }
      if (!this._pos && this.tab === 'close') this.tab = 'open';
    }
    if (changed.has('symbol') && this.symbol !== this._prevSym) {
      this._prevSym = this.symbol;
      this._resetOpen();
      this._resetClose();
      this.orders = [];
      if (this.expanded && this.symbol) this._fetchOrders();
    }
  }

  protected updated() {
    const want = this.expanded && !!this.symbol;
    if (want && !this._poll) {
      this._fetchOrders();
      this._poll = setInterval(() => this._fetchOrders(), 10_000);
    } else if (!want && this._poll) {
      this._stopPoll();
    }
  }

  /* ── Helpers ──────────────────────────────────────────────────────────────── */
  private _stopPoll() {
    if (this._poll) { clearInterval(this._poll); this._poll = null; }
  }

  private _resetOpen() {
    this.openPrev = null;
    this.openTok = '';
    this.openErr = '';
    this.openOk = '';
  }

  private _resetClose() {
    this.closePrev = null;
    this.closeTok = '';
    this.closeErr = '';
    this.closeOk = '';
  }

  private _fmt(v: number | null | undefined, dp = 2): string {
    if (v == null || !Number.isFinite(v)) return '\u2014';
    return v.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }

  private _midNum(): number {
    const n = Number(this.mid);
    return Number.isFinite(n) ? n : 0;
  }

  private get _isEngine(): boolean {
    return this.engineRunning === 'true';
  }

  /* ── Job result polling ───────────────────────────────────────────────────── */

  /** Poll GET /api/trade/{id}/result until the job finishes (up to ~10s). */
  private async _awaitJobResult(jobId: string, maxMs = 10_000): Promise<any> {
    const start = Date.now();
    const interval = 400;
    while (Date.now() - start < maxMs) {
      await new Promise(r => setTimeout(r, interval));
      try {
        return await tradeJobResult(jobId);
      } catch {
        // 400 "job still running" — keep polling
      }
    }
    return null; // timed out
  }

  /* ── API calls ────────────────────────────────────────────────────────────── */
  private _openBody(): Record<string, any> {
    const body: Record<string, any> = {
      symbol: this.symbol,
      side: this.side === 'long' ? 'BUY' : 'SELL',
      notional_usd: Number(this.notional) || 0,
      leverage: Number(this.lev) || 1,
      order_type: this.ordType,
    };
    if (this.ordType !== 'market') body.limit_price = Number(this.limPx) || 0;
    return body;
  }

  private async _doOpenPreview() {
    this._resetOpen();
    this.openBusy = true;
    try {
      const res = await tradePreview(this._openBody());
      this.openTok = res?.confirm_token || '';
      // Poll for subprocess result (server-side estimates)
      if (res?.job_id) {
        const result = await this._awaitJobResult(res.job_id);
        if (result && result.ok) {
          this.openPrev = result;
        } else if (result && result.error) {
          this.openErr = result.error;
          this.openTok = ''; // invalidate — preview failed
        } else {
          // Timeout — no result received
          this.openErr = 'Preview timed out, please retry';
          this.openTok = '';
        }
      }
    } catch (e: any) {
      this.openErr = e?.message || 'Preview failed';
    } finally {
      this.openBusy = false;
    }
  }

  private async _doOpenExecute() {
    if (!this.openTok) return;
    this.openBusy = true;
    this.openErr = '';
    try {
      const res = await tradeExecute({ ...this._openBody(), confirm_token: this.openTok });
      // Poll for execution result
      if (res?.job_id) {
        const result = await this._awaitJobResult(res.job_id, 15_000);
        if (result && result.ok) {
          this.openOk = `Order submitted: ${result.intent_id || ''} ${result.order_type || ''}`.trim();
        } else if (result && result.error) {
          this.openErr = result.error;
        } else {
          this.openOk = 'Order submitted (result pending)';
        }
      } else {
        this.openOk = 'Order submitted';
      }
      this.openTok = '';
      this.openPrev = null;
      this.dispatchEvent(new CustomEvent('tradedone', { bubbles: true, composed: true }));
    } catch (e: any) {
      this.openErr = e?.message || 'Execution failed';
    } finally {
      this.openBusy = false;
    }
  }

  private _closeBody(): Record<string, any> {
    const pct = this.closePct === -1 ? (Number(this.closeCustom) || 0) : this.closePct;
    const body: Record<string, any> = {
      symbol: this.symbol,
      close_pct: pct,
      order_type: this.closeOrdType,
    };
    if (this.closeOrdType !== 'market') body.limit_price = Number(this.closeLimPx) || 0;
    return body;
  }

  private async _doClosePreview() {
    this._resetClose();
    this.closeBusy = true;
    try {
      const res = await tradeClose(this._closeBody());
      this.closePrev = res;
      this.closeTok = res?.confirm_token || '';
    } catch (e: any) {
      this.closeErr = e?.message || 'Preview failed';
    } finally {
      this.closeBusy = false;
    }
  }

  private async _doCloseExecute() {
    if (!this.closeTok) return;
    this.closeBusy = true;
    this.closeErr = '';
    try {
      const res = await tradeClose({ ...this._closeBody(), confirm_token: this.closeTok });
      if (res?.job_id) {
        const result = await this._awaitJobResult(res.job_id, 15_000);
        if (result && result.ok) {
          this.closeOk = `Close submitted: ${result.close_size ?? ''} ${result.symbol ?? ''}`.trim();
        } else if (result && result.error) {
          this.closeErr = result.error;
        } else {
          this.closeOk = 'Close submitted (result pending)';
        }
      } else {
        this.closeOk = 'Close submitted';
      }
      this.closeTok = '';
      this.closePrev = null;
      this.dispatchEvent(new CustomEvent('tradedone', { bubbles: true, composed: true }));
    } catch (e: any) {
      this.closeErr = e?.message || 'Close failed';
    } finally {
      this.closeBusy = false;
    }
  }

  private async _doCancelOrder(oid: string) {
    try {
      const res = await tradeCancel({ oid, symbol: this.symbol });
      if (res?.job_id) {
        const result = await this._awaitJobResult(res.job_id, 8_000);
        if (result?.ok) {
          this.orders = this.orders.filter(o => String(o.oid) !== String(oid));
        }
        // If cancel failed, next poll will reconcile
      } else {
        this.orders = this.orders.filter(o => String(o.oid) !== String(oid));
      }
    } catch { /* next poll will reconcile */ }
  }

  private async _fetchOrders() {
    if (!this.symbol) return;
    try {
      const res = await tradeOpenOrders(this.symbol);
      if (res?.job_id) {
        const result = await this._awaitJobResult(res.job_id, 8_000);
        this.orders = result?.orders || [];
      } else {
        this.orders = Array.isArray(res) ? res : (res?.orders || []);
      }
    } catch { /* ignore */ }
  }

  /* ── Render ───────────────────────────────────────────────────────────────── */
  render() {
    return html`
      <div class="panel">
        <div class="header" @click=${() => { this.expanded = !this.expanded; }}>
          <span class="header-label">MANUAL TRADE</span>
          <span class="toggle">${this.expanded ? '\u25B2' : '\u25BC'}</span>
        </div>
        ${this.expanded ? this._renderBody() : nothing}
      </div>
    `;
  }

  private _renderBody() {
    const hasPos = !!this._pos;
    return html`
      ${this._isEngine ? html`
        <div class="warning">\u26A0 Live engine is running \u2014 manual trades may conflict with automated strategy</div>
      ` : nothing}
      <div class="tabs">
        <button class="tab ${this.tab === 'open' ? 'active' : ''}"
          @click=${() => { this.tab = 'open'; }}>Open</button>
        <button class="tab ${this.tab === 'close' ? 'active' : ''}"
          ?disabled=${!hasPos}
          @click=${() => { this.tab = 'close'; }}>Close${hasPos ? '' : ' (no pos)'}</button>
      </div>
      <div class="body">
        ${this.tab === 'open' ? this._renderOpen() : nothing}
        ${this.tab === 'close' && hasPos ? this._renderClose() : nothing}
        ${this._renderOrders()}
      </div>
    `;
  }

  private _renderOpen() {
    const midNum = this._midNum();
    const notionalNum = Number(this.notional) || 0;
    const levNum = Number(this.lev) || 1;
    return html`
      <div class="section">
        <div class="field">
          <label>Order Type</label>
          <div class="btn-group">
            <button class=${this.ordType === 'market' ? 'on' : ''} @click=${() => { this.ordType = 'market'; this._resetOpen(); }}>Market</button>
            <button class=${this.ordType === 'limit_ioc' ? 'on' : ''} @click=${() => { this.ordType = 'limit_ioc'; this._resetOpen(); }}>Limit IOC</button>
            <button class=${this.ordType === 'limit_gtc' ? 'on' : ''} @click=${() => { this.ordType = 'limit_gtc'; this._resetOpen(); }}>Limit GTC</button>
          </div>
        </div>

        <div class="field">
          <label>Direction</label>
          <div class="btn-group">
            <button class="long ${this.side === 'long' ? 'on' : ''}" @click=${() => { this.side = 'long'; this._resetOpen(); }}>Long \u25B2</button>
            <button class="short ${this.side === 'short' ? 'on' : ''}" @click=${() => { this.side = 'short'; this._resetOpen(); }}>Short \u25BC</button>
          </div>
        </div>

        <div class="field">
          <label>Notional $</label>
          <input type="number" .value=${this.notional}
            @input=${(e: Event) => { this.notional = (e.target as HTMLInputElement).value; this._resetOpen(); }} />
        </div>

        <div class="field">
          <label>Leverage</label>
          <input type="number" .value=${this.lev}
            @input=${(e: Event) => { this.lev = (e.target as HTMLInputElement).value; this._resetOpen(); }} />
          <span class="suffix">x</span>
        </div>

        ${this.ordType !== 'market' ? html`
          <div class="field">
            <label>Limit Px</label>
            <input type="number" .value=${this.limPx}
              placeholder=${midNum ? this._fmt(midNum, 4) : ''}
              @input=${(e: Event) => { this.limPx = (e.target as HTMLInputElement).value; this._resetOpen(); }} />
          </div>
        ` : nothing}

        <div class="preview-box">
          <div class="kv"><span class="k">Mid Price</span><span class="v">${midNum > 0 ? '$' + this._fmt(midNum, 4) : '\u2014'}</span></div>
          ${midNum > 0 && notionalNum > 0 ? html`
            <div class="kv"><span class="k">Est. Size</span><span class="v">~${this._fmt(notionalNum / midNum, 6)}</span></div>
            <div class="kv"><span class="k">Est. Margin</span><span class="v">~$${this._fmt(notionalNum / levNum)}</span></div>
            <div class="kv"><span class="k">Est. Fee</span><span class="v">~$${this._fmt(notionalNum * 0.00035, 4)}</span></div>
          ` : nothing}
        </div>

        ${this.openPrev ? html`
          <div class="preview-box" style="border-color: var(--accent, #00d4ff);">
            <div class="kv"><span class="k">Server Est. Size</span><span class="v">${this._fmt(this.openPrev.est_size, 6)} ${this.symbol}</span></div>
            <div class="kv"><span class="k">Est. Margin</span><span class="v">$${this._fmt(this.openPrev.est_margin_usd)}</span></div>
            <div class="kv"><span class="k">Est. Fee</span><span class="v">$${this._fmt(this.openPrev.est_fee_usd, 4)}</span></div>
            ${this.openPrev.account_value_usd != null ? html`
              <div class="kv"><span class="k">Account Value</span><span class="v">$${this._fmt(this.openPrev.account_value_usd)}</span></div>
            ` : nothing}
          </div>
        ` : nothing}

        <div class="actions">
          <button class="btn btn-secondary" @click=${this._doOpenPreview} ?disabled=${this.openBusy}>
            ${this.openBusy && !this.openTok ? html`<span class="spinner"></span>` : 'Preview'}
          </button>
          <button class="btn btn-danger" @click=${this._doOpenExecute} ?disabled=${!this.openTok || this.openBusy}>
            ${this.openBusy && !!this.openTok ? html`<span class="spinner"></span>` : '\u26A0 EXECUTE'}
          </button>
        </div>

        ${this.openErr ? html`<div class="msg err">${this.openErr}</div>` : nothing}
        ${this.openOk ? html`<div class="msg ok">${this.openOk}</div>` : nothing}
      </div>
    `;
  }

  private _renderClose() {
    return html`
      <div class="section">
        <div class="field">
          <label>Close</label>
          <div class="close-pct">
            ${[100, 50, 25].map(pct => html`
              <button class=${this.closePct === pct ? 'on' : ''}
                @click=${() => { this.closePct = pct; this._resetClose(); }}>${pct}%</button>
            `)}
            <div class="cust">
              <input type="number" placeholder="Custom"
                .value=${this.closePct === -1 ? this.closeCustom : ''}
                @focus=${() => { this.closePct = -1; this._resetClose(); }}
                @input=${(e: Event) => { this.closePct = -1; this.closeCustom = (e.target as HTMLInputElement).value; this._resetClose(); }} />
              <span>%</span>
            </div>
          </div>
        </div>

        <div class="field">
          <label>Type</label>
          <div class="btn-group">
            <button class=${this.closeOrdType === 'market' ? 'on' : ''} @click=${() => { this.closeOrdType = 'market'; this._resetClose(); }}>Market</button>
            <button class=${this.closeOrdType === 'limit_ioc' ? 'on' : ''} @click=${() => { this.closeOrdType = 'limit_ioc'; this._resetClose(); }}>Limit IOC</button>
            <button class=${this.closeOrdType === 'limit_gtc' ? 'on' : ''} @click=${() => { this.closeOrdType = 'limit_gtc'; this._resetClose(); }}>Limit GTC</button>
          </div>
        </div>

        ${this.closeOrdType !== 'market' ? html`
          <div class="field">
            <label>Limit Px</label>
            <input type="number" .value=${this.closeLimPx}
              @input=${(e: Event) => { this.closeLimPx = (e.target as HTMLInputElement).value; this._resetClose(); }} />
          </div>
        ` : nothing}

        ${this.closeTok && this._pos ? (() => {
          const pct = this.closePct === -1 ? (Number(this.closeCustom) || 0) : this.closePct;
          const posSize = Number(this._pos.size) || 0;
          const entryPx = Number(this._pos.entry_price) || 0;
          const midNum = this._midNum();
          const closeSize = posSize * (pct / 100);
          const dirSign = this._pos.type === 'LONG' ? 1 : -1;
          const estPnl = midNum > 0 && entryPx > 0 ? closeSize * (midNum - entryPx) * dirSign : 0;
          const estFee = closeSize * midNum * 0.00035;
          return html`
            <div class="preview-box" style="border-color: var(--accent, #00d4ff);">
              <div class="kv"><span class="k">Close Size</span><span class="v">~${this._fmt(closeSize, 6)} ${this.symbol}</span></div>
              <div class="kv"><span class="k">Est. PnL</span>
                <span class="v" style="color: ${estPnl >= 0 ? 'var(--green, #00e676)' : 'var(--red, #ff5252)'}">
                  $${this._fmt(estPnl)}
                </span>
              </div>
              <div class="kv"><span class="k">Est. Fee</span><span class="v">~$${this._fmt(estFee, 4)}</span></div>
            </div>
          `;
        })() : nothing}

        <div class="actions">
          <button class="btn btn-secondary" @click=${this._doClosePreview} ?disabled=${this.closeBusy}>
            ${this.closeBusy && !this.closeTok ? html`<span class="spinner"></span>` : 'Preview Close'}
          </button>
          <button class="btn btn-danger" @click=${this._doCloseExecute} ?disabled=${!this.closeTok || this.closeBusy}>
            ${this.closeBusy && !!this.closeTok ? html`<span class="spinner"></span>` : '\u26A0 CLOSE'}
          </button>
        </div>

        ${this.closeErr ? html`<div class="msg err">${this.closeErr}</div>` : nothing}
        ${this.closeOk ? html`<div class="msg ok">${this.closeOk}</div>` : nothing}
      </div>
    `;
  }

  private _renderOrders() {
    if (this.orders.length === 0) return nothing;
    return html`
      <div class="section">
        <div class="section-title">Pending GTC Orders</div>
        ${this.orders.map(o => html`
          <div class="order-row">
            <div class="order-info">
              <span class="order-side ${(o.side || '').toLowerCase() === 'buy' ? 'buy' : 'sell'}">${o.side || '?'}</span>
              <span>${this._fmt(o.size, 6)}</span>
              <span style="color: var(--text-muted, #8892b0)">@</span>
              <span>$${this._fmt(o.price, 4)}</span>
            </div>
            <button class="btn-cancel" @click=${() => this._doCancelOrder(String(o.oid))}>Cancel</button>
          </div>
        `)}
      </div>
    `;
  }
}
