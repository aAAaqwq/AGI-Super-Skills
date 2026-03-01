<script lang="ts">
  import { getSnapshot, getMids, getTrendCloses, getTrendCandles, getVolumes, type CandleData } from '../lib/api';
  import { hubWs } from '../lib/ws';
  import { CANDIDATE_FAMILY_ORDER, getModeLabel, LIVE_MODE } from '../lib/mode-labels';
  import SymbolDetailModal from '../components/SymbolDetailModal.svelte';

  let mode = $state('_pending_');
  let gridSize = $state(3);
  let snap: any = $state(null);
  let symbols: any[] = $state([]);
  let selectedSymbol = $state('');
  let mids: Record<string, number> = $state({});
  let trendCloses: Record<string, number[]> = $state({});
  let trendCandles: Record<string, CandleData[]> = $state({});
  let volumes: Record<string, number> = $state({});
  let loading = $state(true);
  let filter = $state('');
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let trendTimer: ReturnType<typeof setInterval> | null = null;
  let candleTimer: ReturnType<typeof setInterval> | null = null;
  let midsSeeded = false;

  async function refreshTrend() {
    try {
      const res = await getTrendCloses(trendInterval, trendBars);
      trendCloses = res.closes || {};
    } catch {}
  }

  async function refreshCandles() {
    try {
      const res = await getTrendCandles(candleInterval, candleBars);
      trendCandles = res.candles || {};
    } catch {}
  }

  async function refreshVolumes() {
    try {
      const res = await getVolumes();
      volumes = res.volumes || {};
    } catch {}
  }

  async function refresh() {
    try {
      const rawSnap = await getSnapshot(mode);
      snap = rawSnap;
      symbols = rawSnap.symbols || [];
      if (!midsSeeded) {
        const m = await getMids();
        mids = m.mids || {};
        midsSeeded = true;
      }
      await Promise.all([refreshTrend(), refreshCandles(), refreshVolumes()]);
    } catch {}
    loading = false;
  }

  function liveCandles(symbol: string): CandleData[] {
    const base = trendCandles[symbol];
    if (!base?.length) return [];
    const mid = mids[symbol];
    if (mid == null || !isFinite(mid) || mid <= 0) return base;
    const arr = [...base];
    const last = { ...arr[arr.length - 1] };
    last.c = mid;
    if (mid > last.h) last.h = mid;
    if (mid < last.l) last.l = mid;
    arr[arr.length - 1] = last;
    return arr;
  }

  function posEquity(s: any): number {
    const p = s.position;
    if (!p || !p.size) return 0;
    const mid = mids[s.symbol] ?? s.mid ?? 0;
    return Math.abs(p.size) * mid;
  }

  function livePnlPct(s: any): number {
    const p = s.position;
    if (!p || !p.entry_price || !p.size) return 0;
    const mid = mids[s.symbol] ?? s.mid ?? p.entry_price;
    const cost = p.entry_price * Math.abs(p.size);
    if (cost <= 0) return 0;
    const pnl = p.type === 'LONG'
      ? (mid - p.entry_price) * Math.abs(p.size)
      : (p.entry_price - mid) * Math.abs(p.size);
    return (pnl / cost) * 100;
  }

  function fmtNotional(val: number): string {
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
    return `$${val.toFixed(0)}`;
  }

  function fmtPnl(pct: number): string {
    const sign = pct >= 0 ? '+' : '';
    return `${sign}${pct.toFixed(2)}%`;
  }

  function levColor(lev: number): string {
    if (lev <= 2)  return 'var(--text-muted)';
    if (lev <= 4)  return 'var(--accent)';
    if (lev <= 7)  return 'var(--yellow)';
    return 'var(--red)';
  }

  function fmtNum(v: number | null | undefined, dp = 2): string {
    if (v === null || v === undefined || !Number.isFinite(v)) return '\u2014';
    return v.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }
  function pnlClass(v: number | null | undefined): string {
    if (v === null || v === undefined) return '';
    return v >= 0 ? 'green' : 'red';
  }

  // ── Derived metrics from snapshot ─────────────────────────────────
  let health = $derived(snap?.health || {});
  let balances = $derived(snap?.balances || {});
  let daily = $derived(snap?.daily || {});
  let openPositions = $derived(snap?.open_positions || []);

  // ── Range selector for PnL / DD ───────────────────────────────────
  let metricsRange = $state<'today' | 'since' | 'all'>('today');
  let rangeMenuOpen = $state(false);

  let activePnl = $derived(
    metricsRange === 'today' ? daily.pnl_usd
    : metricsRange === 'since' ? snap?.since_config?.pnl_usd
    : snap?.all_time?.pnl_usd
  );
  let activeDd = $derived(
    metricsRange === 'today' ? daily.drawdown_pct
    : metricsRange === 'since' ? snap?.since_config?.drawdown_pct
    : snap?.all_time?.drawdown_pct
  );
  let pnlLabel = $derived(
    metricsRange === 'today' ? 'PnL'
    : metricsRange === 'since' ? 'PnL\u2219cfg'
    : 'PnL\u2219all'
  );
  let ddLabel = $derived(
    metricsRange === 'today' ? 'DD'
    : metricsRange === 'since' ? 'DD\u2219cfg'
    : 'DD\u2219all'
  );
  let sinceLabel = $derived(snap?.since_config?.label ?? 'Since cfg');

  function selectRange(r: 'today' | 'since' | 'all') {
    metricsRange = r;
    rangeMenuOpen = false;
  }

  function onRangeClickOutside(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.range-dropdown-wrap')) {
      rangeMenuOpen = false;
    }
  }

  $effect(() => {
    if (rangeMenuOpen) {
      document.addEventListener('click', onRangeClickOutside, true);
      return () => document.removeEventListener('click', onRangeClickOutside, true);
    }
  });

  const gateReasonMap: Record<string, { label: string; desc: string }> = {
    disabled:            { label: 'Disabled',        desc: 'Gate feature is off — new entries always allowed.' },
    trend_ok:            { label: 'Trend OK',         desc: 'Market breadth is trending and BTC ADX + ATR% pass thresholds. Gate is open.' },
    breadth_chop:        { label: 'Breadth chop',     desc: 'Market breadth is inside the chop zone. New entries are blocked.' },
    btc_adx_low:         { label: 'BTC ADX weak',     desc: 'BTC ADX is below the minimum threshold (weak trend). New entries are blocked.' },
    btc_atr_low:         { label: 'BTC ATR low',      desc: 'BTC ATR% is below the minimum threshold (low volatility). New entries are blocked.' },
    breadth_missing:     { label: 'No breadth data',  desc: 'Market breadth data is unavailable. Gate state depends on fail-open setting.' },
    btc_metrics_missing: { label: 'No BTC metrics',   desc: 'BTC ADX/ATR could not be computed. Gate state depends on fail-open setting.' },
  };
  let gateInfo = $derived(
    gateReasonMap[(health.regime_reason ?? '').toLowerCase()] ??
    { label: (health.regime_reason ?? '—'), desc: '' }
  );

  let filteredSymbols = $derived.by(() => {
    const q = filter.trim().toUpperCase();
    let syms = symbols;
    if (q) syms = syms.filter((s: any) => String(s.symbol).includes(q));
    return [...syms].sort((a, b) => {
      const aPos = a.position ? 1 : 0;
      const bPos = b.position ? 1 : 0;
      if (aPos !== bPos) return bPos - aPos;
      if (aPos && bPos) return posEquity(b) - posEquity(a);
      return (volumes[b.symbol] || 0) - (volumes[a.symbol] || 0);
    });
  });

  // ── Cookie helpers ───────────────────────────────────────────────
  function getCookie(key: string, fallback: string): string {
    const m = document.cookie.match(new RegExp(`(?:^|; )${key}=([^;]*)`));
    return m ? decodeURIComponent(m[1]) : fallback;
  }
  function setCookie(key: string, val: string) {
    document.cookie = `${key}=${encodeURIComponent(val)};path=/;max-age=31536000;SameSite=Lax`;
  }
  function getNumCookie(key: string, fallback: number): number {
    const v = Number(getCookie(key, String(fallback)));
    return Number.isFinite(v) ? v : fallback;
  }

  // ── Persisted view settings ─────────────────────────────────────
  mode = getCookie('gridMode', 'paper1');
  gridSize = getNumCookie('gridSize', 3);

  // ── Trend controls (persisted via cookies) ─────────────────────
  let showTrendBar     = $state(getCookie('showTrendBar', '1') === '1');
  let trendFullPct     = $state(getNumCookie('trendFullPct', 1.0));
  let trendCurve       = $state(getNumCookie('trendCurve', 1.0));
  let trendWindow      = $state(getNumCookie('trendWindow', 0));
  let trendInterval    = $state(getCookie('trendInterval', '5m'));
  let trendBars        = $state(getNumCookie('trendBars', 60));
  let trendStrengthMul = $state(getNumCookie('trendStrengthMul', 1.0));
  let showOverlay      = $state(getCookie('showOverlay', '0') === '1');
  let candleInterval   = $state(getCookie('candleInterval', '30m'));
  let candleBars       = $state(getNumCookie('candleBars', 30));

  $effect(() => {
    setCookie('showTrendBar', showTrendBar ? '1' : '0');
    setCookie('trendFullPct', String(trendFullPct));
    setCookie('trendCurve', String(trendCurve));
    setCookie('trendWindow', String(trendWindow));
    setCookie('trendInterval', trendInterval);
    setCookie('trendBars', String(trendBars));
    setCookie('trendStrengthMul', String(trendStrengthMul));
    setCookie('showOverlay', showOverlay ? '1' : '0');
    setCookie('candleInterval', candleInterval);
    setCookie('candleBars', String(candleBars));
    setCookie('gridMode', mode);
    setCookie('gridSize', String(gridSize));
  });

  // ── Trend computation (OLS linear regression) ───────────────────
  function linregTrend(pts: number[], win: number): number {
    if (!pts || pts.length < 2) return 0;
    const src = win > 0 && pts.length > win ? pts.slice(-win) : pts;
    const n = src.length;
    if (n < 2) return 0;
    let sx = 0, sy = 0, sxy = 0, sx2 = 0;
    for (let i = 0; i < n; i++) {
      sx += i; sy += src[i]; sxy += i * src[i]; sx2 += i * i;
    }
    const meanY = sy / n;
    if (meanY <= 0) return 0;
    const slope = (n * sxy - sx * sy) / (n * sx2 - sx * sx);
    return (slope * (n - 1)) / meanY;
  }

  function trendStrength(pts: number[]): number {
    const raw = linregTrend(pts, trendWindow);
    const scaled = raw / (trendFullPct / 100);
    const clamped = Math.max(-1, Math.min(1, scaled));
    const abs = Math.abs(clamped);
    const curved = Math.pow(abs, trendCurve);
    return clamped >= 0 ? curved : -curved;
  }

  function trendVars(strength: number): string {
    const abs = Math.abs(strength);
    if (abs < 0.05) return '';
    const mul = trendStrengthMul;
    const h = strength > 0 ? 145 : 25;
    const l  = 13 + abs * 8 * mul;
    const c  = abs * 0.045 * mul;
    const gl = l + 8 * mul;
    const gc = abs * 0.08 * mul;
    const ga = abs * 0.12 * mul;
    const ba = 0.15 + abs * 0.25 * mul;
    return `--trend-bg:oklch(${l.toFixed(1)}% ${c.toFixed(3)} ${h});--trend-glow:oklch(${gl.toFixed(1)}% ${gc.toFixed(3)} ${h} / ${ga.toFixed(2)});--trend-border:oklch(50% ${(abs * 0.06 * mul).toFixed(3)} ${h} / ${ba.toFixed(2)})`;
  }

  function adaptiveDecimals(n: any): number {
    const v = Number(n);
    if (!Number.isFinite(v) || v <= 0) return 6;
    if (v >= 1000) return 2;
    if (v >= 1) return 4;
    return 6;
  }

  $effect(() => {
    refresh();
    pollTimer = setInterval(refresh, 10000);
    trendTimer = setInterval(refreshTrend, 30000);
    candleTimer = setInterval(refreshCandles, 30000);
    hubWs.connect();
    return () => {
      if (pollTimer) clearInterval(pollTimer);
      if (trendTimer) clearInterval(trendTimer);
      if (candleTimer) clearInterval(candleTimer);
    };
  });

  $effect(() => {
    function finitePositive(v: unknown): number | null {
      const n = Number(v);
      return Number.isFinite(n) && n > 0 ? n : null;
    }
    function quoteMid(quote: any): number | null {
      const explicit = finitePositive(quote?.mid);
      if (explicit != null) return explicit;
      const bid = finitePositive(quote?.bid);
      const ask = finitePositive(quote?.ask);
      if (bid == null || ask == null) return null;
      return (bid + ask) / 2;
    }

    const handler = (data: any) => {
      const midsRaw = data?.mids;
      if (midsRaw && typeof midsRaw === 'object') {
        for (const [sym, raw] of Object.entries(midsRaw)) {
          const px = finitePositive(raw);
          if (px != null) mids[String(sym).toUpperCase()] = px;
        }
      }
      const bboRaw = data?.bbo;
      if (bboRaw && typeof bboRaw === 'object') {
        for (const [sym, raw] of Object.entries(bboRaw)) {
          const px = quoteMid(raw);
          if (px != null) mids[String(sym).toUpperCase()] = px;
        }
      }
    };

    hubWs.subscribe('mids', handler);
    hubWs.subscribe('bbo', handler);
    return () => {
      hubWs.unsubscribe('mids', handler);
      hubWs.unsubscribe('bbo', handler);
    };
  });
</script>

<div class="page">
  <div class="page-header">
    <h1>Grid View</h1>
    <div class="controls">
      <select bind:value={mode} onchange={refresh}>
        <optgroup label="Live Engine">
          <option value={LIVE_MODE}>{getModeLabel(LIVE_MODE)}</option>
        </optgroup>
        <optgroup label="Candidate Family">
          {#each CANDIDATE_FAMILY_ORDER as m}
            <option value={m}>{getModeLabel(m)}</option>
          {/each}
        </optgroup>
      </select>
      <div class="search-wrap">
        <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input type="text" bind:value={filter} placeholder="Filter..." />
      </div>
      <select bind:value={gridSize}>
        <option value={2}>2x2</option>
        <option value={3}>3x3</option>
        <option value={4}>4x4</option>
        <option value={5}>5x5</option>
      </select>
      <button class="trend-toggle" class:active={showTrendBar} onclick={() => showTrendBar = !showTrendBar} title="Trend settings">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></svg>
      </button>
    </div>
  </div>

  <div class="metrics-bar">
    {#if health.kill_mode && health.kill_mode !== 'off'}
      <span class="metric-pill danger">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        KILL: {health.kill_mode}
      </span>
    {/if}
    {#if health.regime_gate !== undefined && health.regime_gate !== null}
      <span class="metric-pill gate-pill" class:gate-on={health.regime_gate} class:gate-off={!health.regime_gate}>
        GATE {health.regime_gate ? 'ON' : 'OFF'}
        <span class="gate-tooltip">
          <span class="gt-title" class:gt-on={health.regime_gate} class:gt-off={!health.regime_gate}>
            GATE {health.regime_gate ? 'ON' : 'OFF'} — {gateInfo.label}
          </span>
          {#if gateInfo.desc}
            <span class="gt-desc">{gateInfo.desc}</span>
          {/if}
          <span class="gt-note">Gate OFF blocks new entries. Exits always continue.</span>
        </span>
      </span>
    {/if}
    <span class="metric-pill">
      <span class="metric-label">BAL</span>
      <span class="metric-value">${fmtNum(balances.realised_usd)}</span>
    </span>
    <span class="metric-pill">
      <span class="metric-label">EQ</span>
      <span class="metric-value">${fmtNum(balances.equity_est_usd)}</span>
    </span>
    <span class="range-dropdown-wrap">
      <button class="metric-pill range-pill {pnlClass(activePnl)}" onclick={() => rangeMenuOpen = !rangeMenuOpen}>
        <span class="metric-label">{pnlLabel}<svg class="range-caret" class:open={rangeMenuOpen} width="8" height="8" viewBox="0 0 8 8"><path d="M1.5 3L4 5.5L6.5 3" fill="none" stroke="currentColor" stroke-width="1.2"/></svg></span>
        <span class="metric-value">${fmtNum(activePnl)}</span>
      </button>
      {#if rangeMenuOpen}
        <div class="range-menu">
          <button class="range-opt" class:active={metricsRange === 'today'} onclick={() => selectRange('today')}>
            <span class="range-dot"></span>Today
          </button>
          <button class="range-opt" class:active={metricsRange === 'since'} onclick={() => selectRange('since')}>
            <span class="range-dot"></span>{sinceLabel}
          </button>
          <button class="range-opt" class:active={metricsRange === 'all'} onclick={() => selectRange('all')}>
            <span class="range-dot"></span>All-time
          </button>
        </div>
      {/if}
    </span>
    <span class="metric-pill">
      <span class="metric-label">{ddLabel}</span>
      <span class="metric-value">{fmtNum(activeDd, 1)}%</span>
    </span>
    <span class="metric-pill">
      <span class="metric-label">POS</span>
      <span class="metric-value">{openPositions.length}</span>
    </span>
  </div>

  {#if showTrendBar}
  <div class="trend-bar">
    <span class="trend-bar-title">TREND</span>
    <div class="tb-divider"></div>
    <label>
      <span class="tb-label" title="Candle interval for trend calculation">Interval</span>
      <select title="Candle interval for trend calculation" bind:value={trendInterval} onchange={refreshTrend}>
        <option value="1m">1m</option>
        <option value="3m">3m</option>
        <option value="5m">5m</option>
        <option value="15m">15m</option>
        <option value="30m">30m</option>
        <option value="1h">1h</option>
      </select>
    </label>
    <label>
      <span class="tb-label" title="Number of candle bars for regression. More = longer lookback period">Lookback</span>
      <input title="Number of candle bars for regression. More = longer lookback period" type="range" min="10" max="200" step="10" bind:value={trendBars} onchange={refreshTrend} />
      <span class="tb-val">{trendBars}</span>
    </label>
    <div class="tb-divider"></div>
    <label>
      <span class="tb-label" title="Price change (%) that maps to full color intensity. Lower = more sensitive to small moves">Sensitivity</span>
      <input title="Price change (%) that maps to full color intensity. Lower = more sensitive to small moves" type="range" min="0.1" max="5" step="0.1" bind:value={trendFullPct} />
      <span class="tb-val">{trendFullPct.toFixed(1)}</span>
    </label>
    <label>
      <span class="tb-label" title="Response exponent. Below 1 compresses differences, above 1 amplifies strong trends">Curve</span>
      <input title="Response exponent. Below 1 compresses differences, above 1 amplifies strong trends" type="range" min="0.2" max="3" step="0.1" bind:value={trendCurve} />
      <span class="tb-val">{trendCurve.toFixed(1)}</span>
    </label>
    <label>
      <span class="tb-label" title="Use only the last N bars for regression. All = use entire lookback range">Window</span>
      <select title="Use only the last N bars for regression. All = use entire lookback range" bind:value={trendWindow}>
        <option value={0}>All</option>
        <option value={10}>10</option>
        <option value={20}>20</option>
        <option value={50}>50</option>
        <option value={100}>100</option>
      </select>
    </label>
    <div class="tb-divider"></div>
    <label>
      <span class="tb-label" title="OKLCH color intensity multiplier. Higher = more vivid trend background">Intensity</span>
      <input title="OKLCH color intensity multiplier. Higher = more vivid trend background" type="range" min="0.5" max="5" step="0.1" bind:value={trendStrengthMul} />
      <span class="tb-val">{trendStrengthMul.toFixed(1)}x</span>
    </label>
    <label class="tb-toggle">
      <input title="Show per-card trend overlay text (regression data, strength value)" type="checkbox" bind:checked={showOverlay} />
      <span class="tb-label" title="Show per-card trend overlay text (regression data, strength value)">Overlay</span>
    </label>
    <div class="tb-divider"></div>
    <span class="trend-bar-title">CANDLES</span>
    <label>
      <span class="tb-label" title="Candle interval for mini charts">Interval</span>
      <select title="Candle interval for mini charts" bind:value={candleInterval} onchange={refreshCandles}>
        <option value="1m">1m</option>
        <option value="3m">3m</option>
        <option value="5m">5m</option>
        <option value="15m">15m</option>
        <option value="30m">30m</option>
        <option value="1h">1h</option>
      </select>
    </label>
    <label>
      <span class="tb-label" title="Number of candle bars to display">Bars</span>
      <select title="Number of candle bars to display" bind:value={candleBars} onchange={refreshCandles}>
        <option value={30}>30</option>
        <option value={50}>50</option>
        <option value={80}>80</option>
      </select>
    </label>
  </div>
  {/if}

  {#if loading}
    <div class="empty-state">Loading...</div>
  {:else}
    <div class="symbol-grid" style="grid-template-columns: repeat({gridSize}, 1fr);">
      {#each filteredSymbols as s (s.symbol)}
        {@const hist = trendCloses[s.symbol] || []}
        {@const trend = trendStrength(hist)}
        <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
        <div class="grid-cell" class:has-trend={Math.abs(trend) >= 0.05} class:has-position={!!s.position} class:pos-long={s.position?.type === 'LONG'} class:pos-short={s.position?.type === 'SHORT'} style={trendVars(trend)} onclick={() => selectedSymbol = s.symbol} onkeydown={(e) => { if (e.key === 'Enter') selectedSymbol = s.symbol; }} role="button" tabindex="0">
          {#if showOverlay}
            <span class="trend-overlay">{hist.length}pt {(linregTrend(hist, trendWindow) * 100).toFixed(3)}% &rarr; {trend.toFixed(2)}</span>
          {/if}
          <div class="cell-header">
            <span class="cell-symbol">{s.symbol}</span>
            {#if s.position}
              <span class="header-right">
                <span class="meta-notional">{fmtNotional(posEquity(s))}</span>
                <span class="lev-box" style="background:{levColor(s.position.leverage ?? 1)}">{Math.round(s.position.leverage ?? 1)}&times;</span>
              </span>
            {/if}
          </div>
          <div class="cell-price-row">
            <span class="cell-price">
              <mid-price
                symbol={s.symbol}
                value={(mids[s.symbol] ?? s.mid) != null ? String(mids[s.symbol] ?? s.mid) : ''}
                decimals={adaptiveDecimals(mids[s.symbol] ?? s.mid)}
                tone="grid"
              ></mid-price>
            </span>
            {#if s.position}
              {@const pnl = livePnlPct(s)}
              <span class="entry-at">@{s.position.entry_price.toFixed(adaptiveDecimals(s.position.entry_price))}</span>
              <span class="pnl-badge" class:up={pnl >= 0} class:down={pnl < 0}>{fmtPnl(pnl)}</span>
            {/if}
          </div>
          {#if s.signal}
            <div class="cell-signal">
              <span class="signal-badge">{s.signal}</span>
            </div>
          {/if}
          <div class="cell-candles">
            <mini-candles
              candles={JSON.stringify(liveCandles(s.symbol))}
              width={200}
              height={56}
              live
            ></mini-candles>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if selectedSymbol}
  <SymbolDetailModal
    symbol={selectedSymbol}
    {mode}
    {snap}
    {mids}
    onclose={() => selectedSymbol = ''}
  />
{/if}

<style>
  .page { max-width: 1600px; animation: slideUp 0.3s ease; }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--sp-md);
    gap: var(--sp-md);
  }
  .page-header h1 {
    font-size: 20px; font-weight: 700; margin: 0; letter-spacing: -0.02em;
  }

  /* ── Metrics pills ─────────────────────────────────────────────── */
  .metrics-bar {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: var(--sp-sm);
  }
  .metric-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
    font-family: 'IBM Plex Mono', monospace;
  }
  .metric-pill.danger {
    border-color: rgba(255,107,107,0.3);
    color: var(--red);
    background: var(--red-bg);
  }
  .metric-pill.gate-on {
    border-color: rgba(81,207,102,0.3);
    color: var(--green);
  }
  .metric-pill.gate-off {
    border-color: rgba(255,107,107,0.3);
    color: var(--red);
  }
  .gate-pill {
    position: relative;
    cursor: help;
  }
  .gate-tooltip {
    display: none;
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    width: 250px;
    background: #111118;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 8px 10px;
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
    z-index: 200;
    flex-direction: column;
    gap: 4px;
    white-space: normal;
    pointer-events: none;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  }
  .gate-pill:hover .gate-tooltip {
    display: flex;
  }
  .gt-title { font-weight: 600; font-size: 11px; }
  .gt-title.gt-on  { color: var(--green); }
  .gt-title.gt-off { color: var(--red); }
  .gt-desc {
    color: var(--text);
    font-size: 10px;
    margin-top: 2px;
    line-height: 1.4;
  }
  .gt-note {
    color: var(--text-muted);
    font-size: 10px;
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px solid var(--border);
    line-height: 1.4;
  }
  .metric-label {
    color: var(--text-muted);
    font-size: 10px;
    font-weight: 400;
  }
  .metric-value {
    font-weight: 600;
  }
  .metric-pill.green .metric-value { color: var(--green); }
  .metric-pill.red .metric-value { color: var(--red); }

  .range-dropdown-wrap {
    position: relative;
    display: inline-flex;
  }
  .range-pill {
    cursor: pointer;
    user-select: none;
  }
  .range-caret {
    display: inline-block;
    margin-left: 2px;
    vertical-align: middle;
    transition: transform var(--t-fast);
  }
  .range-caret.open {
    transform: rotate(180deg);
  }
  .range-menu {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    min-width: 130px;
    background: #111118;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 4px 0;
    z-index: 200;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .range-opt {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 5px 10px;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 11px;
    font-family: inherit;
    text-align: left;
    transition: background var(--t-fast), color var(--t-fast);
  }
  .range-opt:hover {
    background: rgba(255,255,255,0.04);
    color: var(--text);
  }
  .range-opt.active {
    color: var(--accent);
  }
  .range-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    border: 1px solid var(--border);
    flex-shrink: 0;
  }
  .range-opt.active .range-dot {
    background: var(--accent);
    border-color: var(--accent);
  }

  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .controls select {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 12px;
    border-radius: var(--radius-md);
    font-size: 13px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .search-wrap {
    position: relative;
  }
  .search-icon {
    position: absolute;
    left: 8px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-dim);
    pointer-events: none;
  }
  .controls input {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 12px 8px 28px;
    border-radius: var(--radius-md);
    font-size: 13px;
    width: 140px;
  }
  .controls input:focus {
    outline: none;
    border-color: var(--accent);
  }

  .trend-toggle {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-dim);
    padding: 6px 8px;
    border-radius: var(--radius-md);
    cursor: pointer;
    line-height: 0;
  }
  .trend-toggle.active {
    border-color: var(--accent);
    color: var(--accent);
  }

  /* ── Trend settings strip ───────────────────────────────────────── */
  .trend-bar {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 6px 14px;
    margin-bottom: var(--sp-sm);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
    color: var(--text-dim);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .trend-bar::-webkit-scrollbar { display: none; }

  .trend-bar-title {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: var(--accent);
    opacity: 0.7;
    flex-shrink: 0;
  }

  .tb-divider {
    width: 1px;
    height: 18px;
    background: var(--border);
    flex-shrink: 0;
  }

  .trend-bar label {
    display: flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
    cursor: default;
  }
  .tb-label {
    color: var(--text-dim);
  }
  .tb-val {
    color: var(--accent);
    min-width: 24px;
    text-align: right;
  }
  .tb-toggle input[type="checkbox"] {
    accent-color: var(--accent);
    margin: 0;
    cursor: pointer;
  }
  .trend-bar input[type="range"] {
    width: 80px;
    accent-color: var(--accent);
    height: 4px;
    cursor: pointer;
  }
  .trend-bar select {
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-family: inherit;
    cursor: pointer;
  }

  /* ── Grid ────────────────────────────────────────────────────────── */
  .symbol-grid {
    display: grid;
    gap: 10px;
  }

  .grid-cell {
    position: relative;
    background-color: var(--trend-bg, var(--surface));
    border: 1px solid var(--trend-border, var(--border));
    border-radius: var(--radius-lg);
    padding: 14px;
    min-height: 100px;
    transition: background-color 1.5s ease, border-color 1.5s ease;
    cursor: pointer;
  }
  .grid-cell:hover {
    border-color: var(--text-dim);
    transition: border-color 0.15s ease;
  }
  .grid-cell.has-trend {
    animation: trendBreath 4s ease-in-out infinite;
  }
  @keyframes trendBreath {
    0%, 100% { box-shadow: inset 0 0 20px var(--trend-glow, transparent); }
    50%      { box-shadow: inset 0 0 40px var(--trend-glow, transparent); }
  }

  .cell-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }
  .cell-symbol {
    font-weight: 700;
    font-size: 12px;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.02em;
  }

  .cell-price-row {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-bottom: 4px;
  }
  .cell-price {
    font-size: 18px;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: -0.01em;
  }

  /* ── Header right (notional + leverage) ────────────── */
  .header-right {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .lev-box {
    font-size: 10px;
    font-weight: 700;
    padding: 0 4px;
    line-height: 1.4;
    background: var(--text-muted);
    border-radius: var(--radius-sm);
    color: var(--bg);
    letter-spacing: 0.03em;
    font-family: 'IBM Plex Mono', monospace;
  }
  .meta-notional {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    font-family: 'IBM Plex Mono', monospace;
  }

  .signal-badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    background: var(--yellow-bg);
    color: var(--yellow);
    font-weight: 600;
  }

  .cell-candles { margin-top: 6px; }
  .entry-at {
    font-size: 12px;
    font-weight: 500;
    letter-spacing: -0.01em;
    color: var(--text-muted);
  }
  .pnl-badge {
    font-size: 10px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: var(--radius-sm);
    letter-spacing: 0.02em;
  }
  .pnl-badge.up {
    background: var(--green-bg);
    color: var(--green);
  }
  .pnl-badge.down {
    background: var(--red-bg);
    color: var(--red);
  }

  .trend-overlay {
    position: absolute;
    top: 3px;
    right: 5px;
    font-size: 8px;
    font-family: 'IBM Plex Mono', monospace;
    color: #fff;
    opacity: 0.8;
    pointer-events: none;
  }

  .empty-state {
    color: var(--text-dim);
    padding: 40px 0;
    text-align: center;
    font-size: 13px;
  }

  /* ── Position accent bar (pseudo-element, no box-model impact) ── */
  .grid-cell.has-position::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: var(--radius-lg) 0 0 var(--radius-lg);
  }
  .grid-cell.pos-long::before {
    background: var(--green);
  }
  .grid-cell.pos-short::before {
    background: var(--red);
  }

  @media (max-width: 768px) {
    .page-header {
      flex-direction: column;
      align-items: stretch;
    }
    .controls {
      flex-wrap: wrap;
    }
    .metrics-bar {
      gap: 4px;
    }
    .metric-pill {
      font-size: 10px;
      padding: 2px 7px;
    }
    .symbol-grid {
      grid-template-columns: repeat(2, 1fr) !important;
      gap: 0;
      margin-left: calc(-1 * var(--sp-md));
      margin-right: calc(-1 * var(--sp-md));
    }
    .grid-cell {
      padding: 10px;
      border-radius: 0;
      border: none;
    }
    .grid-cell.has-position::before {
      border-radius: 0;
    }
    .cell-price { font-size: 15px; }
  }

  @media (max-width: 480px) {
    .metric-pill {
      font-size: 9px;
      padding: 2px 5px;
    }
    .metric-label {
      display: none;
    }
  }

  @media (orientation: landscape) and (max-height: 500px) {
    .symbol-grid {
      grid-template-columns: repeat(3, 1fr) !important;
      gap: 0;
    }
    .grid-cell { padding: 8px; border: none; }
    .cell-price { font-size: 13px; }
  }
</style>
