<script lang="ts">
  import { appState } from '../lib/stores.svelte';
  import { getSnapshot, getCandles, getMarks, postFlashDebug, tradeEnabled, getSystemServices, getJourneys, getCandlesRange, getVolumes, getTunnel } from '../lib/api';
  import { hubWs } from '../lib/ws';
  import { CANDIDATE_FAMILY_ORDER, getModeLabel, LIVE_MODE } from '../lib/mode-labels';

  const INTERVALS = ['1m', '3m', '5m', '15m', '30m', '1h'] as const;
  const BAR_COUNTS = [50, 100, 200] as const;
  const CHART_PREF_INTERVAL_COOKIE = 'aiq_dash_iv';
  const CHART_PREF_BARS_COOKIE = 'aiq_dash_bars';
  const MODE_SERVICE_MAP: Record<string, string> = {
    live: 'openclaw-ai-quant-live-v8',
    paper1: 'openclaw-ai-quant-trader-v8-paper1',
    paper2: 'openclaw-ai-quant-trader-v8-paper2',
    paper3: 'openclaw-ai-quant-trader-v8-paper3',
  };
  const SERVICE_STATUS_REFRESH_MS = 30_000;

  type ModeRuntimeState = 'on' | 'off' | 'error' | 'unknown';

  let snap: any = $state(null);
  let volumes: Record<string, number> = $state({});
  let focusSym = $state('');
  let candles: any[] = $state([]);
  let marks: any = $state(null);
  let selectedInterval = $state('1h');
  let selectedBars: number = $state(200);
  let pollTimer: any = null;
  let error = $state('');
  let mobileTab: 'symbols' | 'detail' | 'feed' = $state('symbols');
  let detailTab: 'detail' | 'trades' | 'oms' | 'audit' = $state('detail');
  let manualTradeEnabled = $state(false);
  let liveEngineActive = $state(false);
  let modeRuntimeState = $state<Record<string, ModeRuntimeState>>({
    live: 'unknown',
    paper1: 'unknown',
    paper2: 'unknown',
    paper3: 'unknown',
  });
  let detailExpanded = $state(false);
  let chartHeight = $state(240);
  let chartDragging = $state(false);
  let chartPrefsLoaded = $state(false);
  const CHART_MIN = 120;
  const CHART_MAX = 600;

  // ── Journey state ──────────────────────────────────────────────────
  let journeys: any[] = $state([]);
  let selectedJourney: any = $state(null);
  let journeyCandles: any[] = $state([]);
  let journeyMarks: any[] = $state([]);
  let journeyOffset = $state(0);
  let journeyLoading = $state(false);
  let journeyInterval = $state('15m');
  let journeyHasMore = $state(true);
  let journeyChartHeight = $state(280);
  let journeyChartDragging = $state(false);
  let journeyFetchSeq = 0;
  let journeyFromTs = 0;
  let journeyToTs = 0;
  let journeyExtending = false;
  let mainExtending = false;
  const JOURNEY_CHART_MIN = 120;
  const JOURNEY_CHART_MAX = 600;

  // ── Tunnel state (exit bounds visualization) ──────────────────────
  let tunnelPoints: any[] = $state([]);
  let journeyTunnelPoints: any[] = $state([]);

  function pickJourneyInterval(durationMs: number): string {
    if (durationMs < 30 * 60_000)       return '1m';
    if (durationMs < 2 * 60 * 60_000)   return '3m';
    if (durationMs < 6 * 60 * 60_000)   return '5m';
    if (durationMs < 24 * 60 * 60_000)  return '15m';
    return '1h';
  }

  function fmtDuration(ms: number): string {
    if (ms < 0) ms = 0;
    const mins = Math.floor(ms / 60_000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    const rm = mins % 60;
    if (hrs < 24) return rm > 0 ? `${hrs}h ${rm}m` : `${hrs}h`;
    const days = Math.floor(hrs / 24);
    const rh = hrs % 24;
    return rh > 0 ? `${days}d ${rh}h` : `${days}d`;
  }

  async function fetchJourneys(reset = false) {
    if (journeyLoading) return;
    journeyLoading = true;
    try {
      const off = reset ? 0 : journeyOffset;
      const res = await getJourneys(appState.mode, 50, off);
      const batch = res.journeys || [];
      if (reset) {
        journeys = batch;
        journeyOffset = batch.length;
      } else {
        journeys = [...journeys, ...batch];
        journeyOffset += batch.length;
      }
      journeyHasMore = batch.length >= 50;
    } catch (e) { console.error('fetchJourneys failed:', e); }
    journeyLoading = false;
  }

  function journeyTimeRange(j: any) {
    const openTs = Date.parse((j.open_ts || '').replace(' ', 'T'));
    const closeTs = j.close_ts ? Date.parse((j.close_ts || '').replace(' ', 'T')) : Date.now();
    if (!isFinite(openTs)) return null;
    const dur = closeTs - openTs;
    const pad = Math.max(dur * 0.1, 60_000);
    return { openTs, closeTs, dur, fromTs: Math.floor(openTs - pad), toTs: Math.ceil(closeTs + pad) };
  }

  async function selectJourney(j: any) {
    selectedJourney = j;
    journeyCandles = [];
    journeyMarks = [];

    const tr = journeyTimeRange(j);
    if (!tr) return;

    const iv = pickJourneyInterval(tr.dur);
    journeyInterval = iv;
    journeyFromTs = tr.fromTs;
    journeyToTs = tr.toTs;

    const seq = ++journeyFetchSeq;
    try {
      const res = await getCandlesRange(j.symbol, iv, tr.fromTs, tr.toTs, 500);
      if (seq !== journeyFetchSeq) return;
      journeyCandles = res.candles || [];
    } catch (e) { console.error('getCandlesRange failed:', e); }

    // Build journey marks from legs
    journeyMarks = (j.legs || []).map((leg: any) => ({
      price: leg.price,
      timestamp: leg.timestamp,
      action: leg.action,
      type: j.type || j.pos_type,
      size: leg.size,
      pnl: leg.pnl,
      reason: leg.reason,
      confidence: leg.confidence,
    }));
    void fetchTunnelForJourney(j, tr.fromTs, tr.toTs);
  }

  // ── Tunnel data fetch (live position) ─────────────────────────────
  async function fetchTunnelForLive() {
    if (!focusSym || !marks?.position) { tunnelPoints = []; return; }
    try {
      const res = await getTunnel(focusSym, appState.mode);
      tunnelPoints = Array.isArray(res?.tunnel) ? res.tunnel : [];
    } catch { tunnelPoints = []; }
  }

  // ── Tunnel data fetch (journey review) ────────────────────────────
  async function fetchTunnelForJourney(j: any, fromTs: number, toTs: number) {
    if (!j) { journeyTunnelPoints = []; return; }
    try {
      const res = await getTunnel(j.symbol, appState.mode, fromTs, toTs);
      journeyTunnelPoints = Array.isArray(res?.tunnel) ? res.tunnel : [];
    } catch { journeyTunnelPoints = []; }
  }

  function onJourneyChartSplitterDown(e: PointerEvent) {
    e.preventDefault();
    journeyChartDragging = true;
    const startY = e.clientY;
    const startH = journeyChartHeight;
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);

    function onMove(ev: PointerEvent) {
      const h = startH + (ev.clientY - startY);
      journeyChartHeight = Math.max(JOURNEY_CHART_MIN, Math.min(JOURNEY_CHART_MAX, h));
    }
    function onUp() {
      journeyChartDragging = false;
      target.removeEventListener('pointermove', onMove);
      target.removeEventListener('pointerup', onUp);
    }
    target.addEventListener('pointermove', onMove);
    target.addEventListener('pointerup', onUp);
  }

  async function changeJourneyInterval(newIv: string) {
    if (!selectedJourney) return;
    journeyInterval = newIv;
    const j = selectedJourney;
    const tr = journeyTimeRange(j);
    if (!tr) return;
    journeyFromTs = tr.fromTs;
    journeyToTs = tr.toTs;
    const seq = ++journeyFetchSeq;
    try {
      const res = await getCandlesRange(j.symbol, newIv, tr.fromTs, tr.toTs, 500);
      if (seq !== journeyFetchSeq) return;
      journeyCandles = res.candles || [];
    } catch (e) { console.error('getCandlesRange failed:', e); }
    void fetchTunnelForJourney(j, tr.fromTs, tr.toTs);
  }

  // ── Dynamic candle loading ──────────────────────────────────────────

  function mergeCandles(existing: any[], incoming: any[]): any[] {
    const map = new Map<number, any>();
    for (const c of existing) map.set(c.t, c);
    for (const c of incoming) if (!map.has(c.t)) map.set(c.t, c);
    return [...map.values()].sort((a, b) => a.t - b.t);
  }

  async function onJourneyNeedCandles(e: CustomEvent) {
    const { before, after } = e.detail || {};
    if (journeyExtending || !selectedJourney) return;
    const j = selectedJourney;
    const tr = journeyTimeRange(j);
    if (!tr) return;
    const extension = Math.max(tr.dur, intervalToMs(journeyInterval) * 100);

    let newFrom = journeyFromTs;
    let newTo = journeyToTs;
    if (before != null) newFrom = journeyFromTs - extension;
    if (after != null) newTo = journeyToTs + extension;
    if (newFrom === journeyFromTs && newTo === journeyToTs) return;

    journeyExtending = true;
    const seq = ++journeyFetchSeq;
    try {
      const res = await getCandlesRange(j.symbol, journeyInterval, newFrom, newTo, 2000);
      if (seq !== journeyFetchSeq) return;
      journeyCandles = mergeCandles(journeyCandles, res.candles || []);
      journeyFromTs = newFrom;
      journeyToTs = newTo;
    } catch (e) { console.error('onJourneyNeedCandles failed:', e); }
    finally { journeyExtending = false; }
  }

  async function onMainNeedCandles(e: CustomEvent) {
    const { before } = e.detail || {};
    if (before == null || mainExtending || !focusSym) return;
    // Capture current context before async — detect stale responses after await
    const sym = focusSym;
    const iv = selectedInterval;
    mainExtending = true;
    try {
      const res = await getCandlesRange(sym, iv, undefined, before, 500);
      if (focusSym !== sym || selectedInterval !== iv) return;
      if (res.candles?.length) {
        candles = mergeCandles(res.candles, candles);
      }
    } catch (e) { console.error('onMainNeedCandles failed:', e); }
    finally { mainExtending = false; }
  }

  function onChartSplitterDown(e: PointerEvent) {
    e.preventDefault();
    chartDragging = true;
    const startY = e.clientY;
    const startH = chartHeight;
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);

    function onMove(ev: PointerEvent) {
      const h = startH + (ev.clientY - startY);
      chartHeight = Math.max(CHART_MIN, Math.min(CHART_MAX, h));
    }
    function onUp() {
      chartDragging = false;
      target.removeEventListener('pointermove', onMove);
      target.removeEventListener('pointerup', onUp);
    }
    target.addEventListener('pointermove', onMove);
    target.addEventListener('pointerup', onUp);
  }

  function readCookie(name: string): string | null {
    if (typeof document === 'undefined') return null;
    const needle = `${encodeURIComponent(name)}=`;
    const parts = String(document.cookie || '').split(';');
    for (const raw of parts) {
      const p = raw.trim();
      if (p.startsWith(needle)) return decodeURIComponent(p.slice(needle.length));
    }
    return null;
  }

  function writeCookie(name: string, value: string, maxAgeS = 31_536_000) {
    if (typeof document === 'undefined') return;
    document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; Max-Age=${maxAgeS}; Path=/; SameSite=Lax`;
  }

  function isValidInterval(iv: string): iv is (typeof INTERVALS)[number] {
    return (INTERVALS as readonly string[]).includes(iv);
  }

  function isValidBars(n: number): n is (typeof BAR_COUNTS)[number] {
    return (BAR_COUNTS as readonly number[]).includes(n);
  }

  function loadChartPrefsFromCookie() {
    const ivRaw = String(readCookie(CHART_PREF_INTERVAL_COOKIE) || '').trim().toLowerCase();
    if (ivRaw && isValidInterval(ivRaw)) selectedInterval = ivRaw;

    const barsRaw = Number(readCookie(CHART_PREF_BARS_COOKIE));
    if (Number.isFinite(barsRaw) && isValidBars(barsRaw)) selectedBars = barsRaw;
  }

  function classifyModeRuntimeState(service: any): ModeRuntimeState {
    const active = String(service?.active || '').toLowerCase();
    const sub = String(service?.sub || '').toLowerCase();
    const load = String(service?.load || '').toLowerCase();
    if (active === 'active') return 'on';
    if (active === 'failed' || sub === 'failed' || sub === 'auto-restart') return 'error';
    if (load === 'not-found' || active === '' || active === 'unknown') return 'unknown';
    return 'off';
  }

  function getModeRuntimeState(mode: string): ModeRuntimeState {
    return modeRuntimeState[mode] ?? 'unknown';
  }

  function getModeRuntimeLabel(mode: string): string {
    const state = getModeRuntimeState(mode);
    if (state === 'on') return 'ON';
    if (state === 'off') return 'OFF';
    if (state === 'error') return 'ERR';
    return 'NA';
  }

  function resolveStrategyMode(rawHealth: any): string {
    const direct = String(rawHealth?.strategy_mode || '').trim().toLowerCase();
    if (direct) return direct;
    const line = String(rawHealth?.line || '');
    const m = line.match(/\bstrategy_mode=([a-z_]+)/i);
    return m?.[1]?.toLowerCase() || '';
  }

  function promotedFamilyLabel(strategyMode: string): string {
    const role = String(strategyMode || '').trim().toLowerCase();
    if (role === 'primary') return 'EFFICIENT';
    if (role === 'fallback') return 'GROWTH';
    if (role === 'conservative') return 'CONSERVATIVE';
    if (role === 'flat') return 'FLAT';
    return 'NA';
  }

  async function refreshModeRuntimeStates() {
    try {
      const svcs = await getSystemServices();
      const byName = new Map((svcs || []).map((s: any) => [String(s?.name || ''), s]));
      modeRuntimeState = {
        live: classifyModeRuntimeState(byName.get(MODE_SERVICE_MAP.live)),
        paper1: classifyModeRuntimeState(byName.get(MODE_SERVICE_MAP.paper1)),
        paper2: classifyModeRuntimeState(byName.get(MODE_SERVICE_MAP.paper2)),
        paper3: classifyModeRuntimeState(byName.get(MODE_SERVICE_MAP.paper3)),
      };
      liveEngineActive = modeRuntimeState.live === 'on';
    } catch {
      modeRuntimeState = {
        live: 'unknown',
        paper1: 'unknown',
        paper2: 'unknown',
        paper3: 'unknown',
      };
      liveEngineActive = false;
    }
  }

  type FlashDebugEvent = {
    symbol: string;
    prev: number;
    mid: number;
    direction: 'up' | 'down';
    phase: 'a' | 'b';
    source: 'table' | 'detail';
    tone: 'table' | 'accent';
    at_ms: number;
  };

  const flashDebugEnabled = resolveFlashDebugEnabled();
  let flashDebugQueue: FlashDebugEvent[] = [];
  let flashDebugTimer: any = null;
  const flashDebugFlushMs = 250;
  const flashDebugBatchMax = 300;

  function resolveFlashDebugEnabled(): boolean {
    if (typeof window === 'undefined') return false;
    try {
      const query = new URLSearchParams(window.location.search).get('flash_debug')?.toLowerCase();
      if (query === '1' || query === 'true') {
        window.localStorage.setItem('aiq_flash_debug', '1');
        return true;
      }
      if (query === '0' || query === 'false') {
        window.localStorage.removeItem('aiq_flash_debug');
        return false;
      }
      return window.localStorage.getItem('aiq_flash_debug') === '1';
    } catch {
      return false;
    }
  }

  function scheduleFlashDebugFlush() {
    if (flashDebugTimer != null) return;
    flashDebugTimer = setTimeout(() => {
      flashDebugTimer = null;
      void flushFlashDebug();
    }, flashDebugFlushMs);
  }

  function onMidFlashTrigger(event: CustomEvent<any>, source: 'table' | 'detail') {
    if (!flashDebugEnabled) return;
    const detail = event?.detail;
    if (!detail || typeof detail.symbol !== 'string' || detail.symbol.length === 0) return;
    if (!Number.isFinite(detail.prev) || !Number.isFinite(detail.mid)) return;
    if (detail.direction !== 'up' && detail.direction !== 'down') return;
    if (detail.phase !== 'a' && detail.phase !== 'b') return;
    if (detail.tone !== 'table' && detail.tone !== 'accent') return;

    flashDebugQueue.push({
      symbol: detail.symbol,
      prev: detail.prev,
      mid: detail.mid,
      direction: detail.direction,
      phase: detail.phase,
      source,
      tone: detail.tone,
      at_ms: Number.isFinite(detail.at_ms) ? detail.at_ms : Date.now(),
    });

    if (flashDebugQueue.length >= flashDebugBatchMax) {
      if (flashDebugTimer != null) {
        clearTimeout(flashDebugTimer);
        flashDebugTimer = null;
      }
      void flushFlashDebug();
      return;
    }
    scheduleFlashDebugFlush();
  }

  async function flushFlashDebug() {
    if (!flashDebugEnabled || flashDebugQueue.length === 0) return;
    const batch = flashDebugQueue.splice(0, flashDebugBatchMax);
    try {
      await postFlashDebug(batch);
    } catch {
      // Keep the debug pipeline best-effort and avoid affecting UI flow.
      flashDebugQueue = batch.concat(flashDebugQueue).slice(0, 2000);
    }
    if (flashDebugQueue.length > 0) {
      scheduleFlashDebugFlush();
    }
  }

  function pnlPct(pos: any): number | null {
    if (!pos || pos.entry_price == null || !pos.size || pos.unreal_pnl_est == null) return null;
    const notional = pos.entry_price * Math.abs(pos.size);
    if (notional === 0) return null;
    return (pos.unreal_pnl_est / notional) * 100;
  }

  function fmtNum(v: number | null | undefined, dp = 2): string {
    if (v === null || v === undefined || !Number.isFinite(v)) return '\u2014';
    return v.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }
  function fmtAge(s: number | null | undefined): string {
    if (s === null || s === undefined) return '\u2014';
    if (s < 60) return `${Math.round(s)}s`;
    if (s < 3600) return `${Math.round(s / 60)}m`;
    return `${(s / 3600).toFixed(1)}h`;
  }
  function sigAge(ts: string | null | undefined): string {
    if (!ts) return '';
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '';
    return fmtAge((Date.now() - d.getTime()) / 1000);
  }
  function isFreshSig(ts: string | null | undefined): boolean {
    if (!ts) return false;
    const d = new Date(ts);
    if (isNaN(d.getTime())) return false;
    return (Date.now() - d.getTime()) < 3_600_000; // 1 hour
  }
  function pnlClass(v: number | null | undefined): string {
    if (v === null || v === undefined) return '';
    return v >= 0 ? 'green' : 'red';
  }

  async function refresh() {
    try {
      appState.loading = true;
      const [data, vol] = await Promise.all([
        getSnapshot(appState.mode),
        getVolumes().catch(() => ({ volumes: {} })),
      ]);
      updateServerClockOffset(data?.now_ts_ms);
      volumes = vol.volumes || {};
      // Preserve live WS mid prices — don't let stale REST prices overwrite them.
      // WS owns price; REST owns everything else (positions, signals, heartbeat, balances).
      if (snap?.symbols && data?.symbols) {
        const liveMids: Record<string, number> = {};
        for (const s of snap.symbols) {
          if (s.mid != null) liveMids[s.symbol] = s.mid;
        }
        for (const s of data.symbols) {
          if (liveMids[s.symbol] !== undefined) s.mid = liveMids[s.symbol];
        }
      }
      snap = data;
      appState.snapshot = data;
      error = '';
    } catch (e: any) {
      error = e.message || 'fetch failed';
    } finally {
      appState.loading = false;
    }
  }

  // Returns candle limit sized to give roughly 1-7 days of data per interval.
  function candleLimit(iv: string): number {
    switch (iv) {
      case '1m':  return 400;   // ~6.7 h
      case '3m':  return 300;   // ~15 h
      case '5m':  return 288;   // ~24 h
      case '15m': return 240;   // ~60 h
      case '30m': return 200;   // ~4 days
      case '1h':  return 168;   // ~7 days
      case '4h':  return 180;   // ~30 days
      case '1d':  return 200;   // ~200 days
      default:    return 200;
    }
  }

  function intervalToMs(iv: string): number {
    const m = /^([0-9]+)([mhd])$/i.exec(String(iv || '').trim());
    if (!m) return 60_000;
    const n = Number(m[1]);
    if (!Number.isFinite(n) || n <= 0) return 60_000;
    const unit = String(m[2] || '').toLowerCase();
    if (unit === 'm') return n * 60_000;
    if (unit === 'h') return n * 60 * 60_000;
    if (unit === 'd') return n * 24 * 60 * 60_000;
    return 60_000;
  }

  function newestCandleIndex(rows: any[]): number {
    let idx = 0;
    for (let i = 1; i < rows.length; i++) {
      if (Number(rows[i]?.t || 0) > Number(rows[idx]?.t || 0)) idx = i;
    }
    return idx;
  }

  function newestCandleAtOrBefore(rows: any[], ts: number): number {
    let idx = -1;
    let bestT = -Infinity;
    for (let i = 0; i < rows.length; i++) {
      const t = Number(rows[i]?.t || 0);
      if (!Number.isFinite(t) || t <= 0) continue;
      if (t <= ts && t > bestT) {
        bestT = t;
        idx = i;
      }
    }
    return idx;
  }

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

  function extractLiveMid(data: any, sym: string): number | null {
    const key = String(sym || '').toUpperCase();
    const fromBbo = quoteMid(data?.bbo?.[key] ?? data?.bbo?.[sym]);
    if (fromBbo != null) return fromBbo;
    return finitePositive(data?.mids?.[key] ?? data?.mids?.[sym]);
  }

  function collectLiveMidMap(data: any): Record<string, number> {
    const out: Record<string, number> = {};
    const midsRaw = data?.mids;
    if (midsRaw && typeof midsRaw === 'object') {
      for (const [sym, raw] of Object.entries(midsRaw)) {
        const px = finitePositive(raw);
        if (px != null) out[String(sym).toUpperCase()] = px;
      }
    }
    const bboRaw = data?.bbo;
    if (bboRaw && typeof bboRaw === 'object') {
      for (const [sym, raw] of Object.entries(bboRaw)) {
        const px = quoteMid(raw);
        if (px != null) out[String(sym).toUpperCase()] = px;
      }
    }
    return out;
  }

  function snapshotDevelopingCandle(rows: any[], iv: string): any | null {
    if (!rows.length) return null;
    const idx = newestCandleIndex(rows);
    const src = rows[idx];
    const t = Number(src?.t || 0);
    if (!Number.isFinite(t) || t <= 0) return null;

    const close = finitePositive(src?.c);
    if (close == null) return null;
    const open = finitePositive(src?.o) ?? close;
    const high = finitePositive(src?.h) ?? Math.max(open, close);
    const low = finitePositive(src?.l) ?? Math.min(open, close);
    const tCloseRaw = Number(src?.t_close);
    const tClose = Number.isFinite(tCloseRaw) && tCloseRaw > 0
      ? tCloseRaw
      : (t + intervalToMs(iv) - 1);
    const volRaw = Number(src?.v);
    const nRaw = Number(src?.n);

    return {
      t,
      t_close: tClose,
      o: open,
      h: Math.max(high, open, close),
      l: Math.min(low, open, close),
      c: close,
      v: Number.isFinite(volRaw) ? volRaw : 0,
      n: Number.isFinite(nRaw) ? nRaw : 0,
    };
  }

  function mergeOfficialCandlesWithDeveloping(officialRows: any[], developing: any | null, maxBars: number): any[] {
    const merged = Array.isArray(officialRows) ? [...officialRows] : [];
    if (developing) {
      const latestTs = merged.length > 0
        ? Number(merged[newestCandleIndex(merged)]?.t || 0)
        : 0;
      if (!Number.isFinite(latestTs) || latestTs < Number(developing.t || 0)) {
        merged.push(developing);
      }
    }
    if (merged.length > maxBars) {
      return merged.slice(merged.length - maxBars);
    }
    return merged;
  }

  // Track previous symbol so we can clear candles on symbol switch
  // (plain let — not reactive, no effect re-run on change)
  let _prevFocusSym = '';
  let _prevSelectedInterval = '';
  let _candlesSeriesSym = '';
  let _candlesSeriesInterval = '';
  // Client/server clock offset for candle-boundary alignment.
  let _serverNowOffsetMs = 0;
  let _lastLiveFrameMs = 0;
  let _lastLiveTickKey = '';
  // Candle reconciliation controls.
  const CANDLE_ROLLOVER_RECONCILE_DELAY_MS = 1600;
  const CANDLE_PERIODIC_RECONCILE_MS = 25_000;
  let _candlesFetchInFlight = false;
  let _candlesFetchQueued = false;
  let _candlesRolloverReconcileTimer: ReturnType<typeof setTimeout> | null = null;

  function setCandlesSeriesContext(sym: string, iv: string) {
    _candlesSeriesSym = sym;
    _candlesSeriesInterval = iv;
    _lastLiveFrameMs = 0;
    _lastLiveTickKey = '';
  }

  function hasCandlesSeriesContext(sym: string, iv: string): boolean {
    return _candlesSeriesSym === sym && _candlesSeriesInterval === iv;
  }

  function activeSeriesInterval(sym: string, requestedIv: string): string {
    // While a new interval is fetching, keep updating the currently rendered series.
    if (_candlesSeriesSym === sym && _candlesSeriesInterval) {
      return _candlesSeriesInterval;
    }
    return requestedIv;
  }

  function publishCandlesMutation() {
    // Lit custom elements trigger `updated()` on reference changes.
    // Live ticks mutate candle objects in-place, so publish a new array reference.
    candles = [...candles];
  }

  function updateServerClockOffset(serverNowMs: unknown) {
    const ts = Number(serverNowMs);
    if (!Number.isFinite(ts) || ts <= 0) return;
    _serverNowOffsetMs = ts - Date.now();
  }

  function serverNowMs(): number {
    return Date.now() + _serverNowOffsetMs;
  }

  function clearRolloverReconcileTimer() {
    if (_candlesRolloverReconcileTimer == null) return;
    clearTimeout(_candlesRolloverReconcileTimer);
    _candlesRolloverReconcileTimer = null;
  }

  async function reconcileCandlesForCurrentView(sym = focusSym, iv = selectedInterval, bars = selectedBars): Promise<void> {
    if (!sym) return;
    const keepDeveloping = hasCandlesSeriesContext(sym, iv);
    const developingBeforeFetch = keepDeveloping ? snapshotDevelopingCandle(candles, iv) : null;

    if (_candlesFetchInFlight) {
      _candlesFetchQueued = true;
      return;
    }
    _candlesFetchInFlight = true;
    try {
      const res = await getCandles(sym, iv, bars);
      // Ignore stale responses if focus context changed mid-flight.
      if (focusSym !== sym || selectedInterval !== iv || selectedBars !== bars) return;
      const officialRows = Array.isArray(res?.candles) ? res.candles : [];
      const developingCurrent = keepDeveloping ? snapshotDevelopingCandle(candles, iv) : null;
      candles = mergeOfficialCandlesWithDeveloping(
        officialRows,
        developingCurrent ?? developingBeforeFetch,
        bars,
      );
      // Advance to the current bar if the newest candle's period has elapsed.
      // Without this, after a reconcile replaces the developing candle with an
      // official completed candle, the chart stalls until the next WS tick.
      const msPerBar = intervalToMs(iv);
      const nowMs = serverNowMs();
      const currentBarStart = Math.floor(nowMs / msPerBar) * msPerBar;
      if (candles.length > 0) {
        const nIdx = newestCandleIndex(candles);
        const nT = Number(candles[nIdx]?.t || 0);
        if (nT > 0 && nT < currentBarStart) {
          const prevClose = Number(candles[nIdx]?.c || 0);
          const symData = snap?.symbols?.find((s: any) => s.symbol === sym);
          const mid = finitePositive(symData?.mid) ?? prevClose;
          const open = prevClose > 0 ? prevClose : mid;
          candles.push({
            t: currentBarStart,
            t_close: currentBarStart + msPerBar - 1,
            o: open,
            h: Math.max(open, mid),
            l: Math.min(open, mid),
            c: mid,
            v: 0, n: 0,
          });
          if (candles.length > bars) candles.splice(0, candles.length - bars);
        }
      }
      // Reset tick dedup so the next WS tick processes even if mid is unchanged.
      _lastLiveTickKey = '';
      setCandlesSeriesContext(sym, iv);
      void fetchTunnelForLive();
    } catch {
      // Keep rendering the current candles on transient API failures.
    } finally {
      _candlesFetchInFlight = false;
      if (_candlesFetchQueued) {
        _candlesFetchQueued = false;
        setTimeout(() => { void reconcileCandlesForCurrentView(); }, 0);
      }
    }
  }

  function scheduleRolloverReconcile() {
    clearRolloverReconcileTimer();
    _candlesRolloverReconcileTimer = setTimeout(() => {
      _candlesRolloverReconcileTimer = null;
      void reconcileCandlesForCurrentView();
    }, CANDLE_ROLLOVER_RECONCILE_DELAY_MS);
  }

  async function setFocus(sym: string) {
    focusSym = sym;
    appState.focus = sym;
    candles = [];
    tunnelPoints = [];
    setCandlesSeriesContext('', '');
    marks = null;
    _candlesFetchQueued = false;
    clearRolloverReconcileTimer();
    if (!sym) return;
    detailTab = 'detail';
    mobileTab = 'detail';
    try {
      marks = await getMarks(sym, appState.mode);
    } catch { /* ignore */ }
  }

  // Re-fetch candles when symbol or interval changes.
  // Only clears the chart when the symbol changes (not on interval switch)
  // so old data stays visible during the brief network round-trip.
  $effect(() => {
    const sym  = focusSym;
    const iv = selectedInterval;
    const bars = selectedBars;
    if (!sym) {
      candles = [];
      _prevFocusSym = '';
      _prevSelectedInterval = '';
      setCandlesSeriesContext('', '');
      return;
    }
    if (sym !== _prevFocusSym) {
      candles = [];
      _prevFocusSym = sym;
      _prevSelectedInterval = iv;
      setCandlesSeriesContext('', '');
    } else if (iv !== _prevSelectedInterval) {
      // Keep the current series context until the new interval candles arrive.
      // This avoids a temporary live-update hang during slow interval fetches.
      _prevSelectedInterval = iv;
    }
    void reconcileCandlesForCurrentView(sym, iv, bars);
  });

  // Low-frequency official-candle reconcile while detail view is open.
  $effect(() => {
    const sym = focusSym;
    const tab = detailTab;
    const iv = selectedInterval;
    const bars = selectedBars;
    if (!sym || tab !== 'detail') return;
    const id = setInterval(() => { void reconcileCandlesForCurrentView(sym, iv, bars); }, CANDLE_PERIODIC_RECONCILE_MS);
    return () => clearInterval(id);
  });

  // Live candle update: mutate current developing candle, and roll over to a
  // new synthetic candle once the exchange interval boundary is crossed.
  $effect(() => {
    const sym = focusSym;
    if (!sym) return;
    const handler = (data: any) => {
      updateServerClockOffset(data?.server_ts_ms);
      const localNow = Date.now();
      // Keep near-per-tick responsiveness while capping pathological redraw rates.
      if (localNow - _lastLiveFrameMs < 16) return;
      const mid = extractLiveMid(data, sym);
      if (mid == null || candles.length === 0) return;

      if (_candlesSeriesSym && _candlesSeriesSym !== sym) return;
      const liveIv = activeSeriesInterval(sym, selectedInterval);
      const wsServerNow = Number(data?.server_ts_ms);
      const now = Number.isFinite(wsServerNow) && wsServerNow > 0 ? wsServerNow : serverNowMs();
      const msPerBar = intervalToMs(liveIv);
      const barStart = Math.floor(now / msPerBar) * msPerBar;
      const barClose = barStart + msPerBar - 1;
      const tickKey = `${liveIv}:${barStart}:${mid}`;
      if (tickKey === _lastLiveTickKey) return;
      _lastLiveTickKey = tickKey;
      let mutated = false;

      let liveIdx = newestCandleIndex(candles);
      let c = candles[liveIdx];
      let candleStart = Number(c?.t || 0);
      if (!Number.isFinite(candleStart) || candleStart <= 0) return;

      // During rapid interval switches, stale future candles can briefly remain.
      // Drop them so live updates resume on the correct active interval series.
      if (candleStart > barStart) {
        for (let i = candles.length - 1; i >= 0; i--) {
          const t = Number(candles[i]?.t || 0);
          if (Number.isFinite(t) && t > barStart) {
            candles.splice(i, 1);
            mutated = true;
          }
        }
        if (candles.length === 0) {
          if (mutated) publishCandlesMutation();
          return;
        }
        liveIdx = newestCandleAtOrBefore(candles, barStart);
        if (liveIdx < 0) {
          if (mutated) publishCandlesMutation();
          return;
        }
        c = candles[liveIdx];
        candleStart = Number(c?.t || 0);
        if (!Number.isFinite(candleStart) || candleStart <= 0) {
          if (mutated) publishCandlesMutation();
          return;
        }
      }

      if (candleStart < barStart) {
        const prevClose = Number.isFinite(Number(c.c)) ? Number(c.c) : mid;
        const o = prevClose;
        candles.push({
          t: barStart,
          t_close: barClose,
          o,
          h: Math.max(o, mid),
          l: Math.min(o, mid),
          c: mid,
          v: 0,
          n: 0,
        });
        mutated = true;
        if (candles.length > selectedBars) {
          candles.splice(0, candles.length - selectedBars);
        }
        // Replace synthetic rollover candle with exchange-written candles shortly after boundary.
        scheduleRolloverReconcile();
        _lastLiveFrameMs = localNow;
        publishCandlesMutation();
        return;
      }

      const closeMs = Number(c.t_close || 0);
      if (!Number.isFinite(closeMs) || closeMs <= 0 || closeMs < barClose) {
        c.t_close = barClose;
        mutated = true;
      }

      const prevClose = Number.isFinite(Number(c.c)) ? Number(c.c) : mid;
      const prevHigh = Number.isFinite(Number(c.h)) ? Number(c.h) : mid;
      const prevLow = Number.isFinite(Number(c.l)) ? Number(c.l) : mid;
      if (prevClose === mid && prevHigh >= mid && prevLow <= mid) {
        if (mutated) publishCandlesMutation();
        return;
      }
      c.c = mid;
      c.h = Math.max(prevHigh, mid);
      c.l = Math.min(prevLow, mid);
      _lastLiveFrameMs = localNow;
      publishCandlesMutation();
    };
    hubWs.subscribe('mids', handler);
    hubWs.subscribe('bbo', handler);
    return () => {
      hubWs.unsubscribe('mids', handler);
      hubWs.unsubscribe('bbo', handler);
    };
  });

  function setMode(m: string) {
    appState.mode = m;
    focusSym = '';
    // Reset journey state for the new mode
    journeys = [];
    selectedJourney = null;
    journeyCandles = [];
    journeyMarks = [];
    journeyOffset = 0;
    journeyHasMore = true;
    refresh();
    if (detailTab === 'trades') {
      void fetchJourneys(true);
    }
  }

  function setFeed(f: 'trades' | 'oms' | 'audit') {
    detailTab = f;
    if (f === 'trades') {
      void fetchJourneys(true);
    }
  }

  // Persist last chart controls for the next visit.
  $effect(() => {
    if (!chartPrefsLoaded) return;
    writeCookie(CHART_PREF_INTERVAL_COOKIE, selectedInterval);
    writeCookie(CHART_PREF_BARS_COOKIE, String(selectedBars));
  });

  $effect(() => {
    loadChartPrefsFromCookie();
    chartPrefsLoaded = true;
    refresh();
    pollTimer = setInterval(refresh, 5000);
    hubWs.connect();
    return () => {
      clearInterval(pollTimer);
      clearRolloverReconcileTimer();
      if (flashDebugTimer != null) {
        clearTimeout(flashDebugTimer);
        flashDebugTimer = null;
      }
      void flushFlashDebug();
    };
  });

  // Subscribe to real-time mid price updates over WebSocket (~100ms).
  // WS owns all price data; REST owns positions/signals/heartbeat/balances.
  $effect(() => {
    const midsHandler = (data: any) => {
      if (!snap?.symbols) return;
      const newMids = collectLiveMidMap(data);
      if (Object.keys(newMids).length === 0) return;

      // Mutate mid prices + recalculate unrealized PnL in-place.
      // Svelte 5 deep proxies track these writes automatically.
      for (const s of snap.symbols) {
        const p = newMids[String(s.symbol).toUpperCase()];
        if (p === undefined) continue;
        s.mid = p;
        if (s.position?.entry_price != null && s.position?.size != null) {
          s.position.unreal_pnl_est =
            s.position.type === 'LONG'
              ? (p - s.position.entry_price) * s.position.size
              : (s.position.entry_price - p) * s.position.size;
        }
      }
    };
    hubWs.subscribe('mids', midsHandler);
    hubWs.subscribe('bbo', midsHandler);
    return () => {
      hubWs.unsubscribe('mids', midsHandler);
      hubWs.unsubscribe('bbo', midsHandler);
    };
  });

  // ── Manual trade feature check ─────────────────────────────────────────────
  $effect(() => {
    tradeEnabled().then(r => { manualTradeEnabled = r?.enabled ?? false; }).catch(() => {});
  });

  // ── Runtime service states for Live + candidate family daemons ────────────
  $effect(() => {
    void refreshModeRuntimeStates();
    const timer = setInterval(() => { void refreshModeRuntimeStates(); }, SERVICE_STATUS_REFRESH_MS);
    return () => clearInterval(timer);
  });

  // ── Resizable columns ──────────────────────────────────────────────────────
  const SYM_MIN = 200;
  let symWidth = $state(455);
  let dragging = $state(false);

  function onSplitterDown(e: PointerEvent) {
    e.preventDefault();
    dragging = true;
    const startX = e.clientX;
    const startW = symWidth;
    const gridEl = (e.currentTarget as HTMLElement).closest('.dashboard-grid') as HTMLElement | null;
    const symMax = Math.max(SYM_MIN + 100, (gridEl ? gridEl.clientWidth : window.innerWidth - 66) - 280);
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);

    function onMove(ev: PointerEvent) {
      const w = startW + (ev.clientX - startX);
      symWidth = Math.max(SYM_MIN, Math.min(symMax, w));
    }
    function onUp() {
      dragging = false;
      target.removeEventListener('pointermove', onMove);
      target.removeEventListener('pointerup', onUp);
    }
    target.addEventListener('pointermove', onMove);
    target.addEventListener('pointerup', onUp);
  }

  let symbols = $derived(snap?.symbols || []);
  function posEquity(s: any): number {
    const p = s.position;
    if (!p || !p.size) return 0;
    return Math.abs(p.size) * (s.mid || 0);
  }
  let filteredSymbols = $derived.by(() => {
    const q = appState.search.trim().toUpperCase();
    let syms = symbols;
    if (q) syms = syms.filter((s: any) => String(s.symbol).includes(q));
    return [...syms].sort((a: any, b: any) => {
      const aPos = a.position ? 1 : 0;
      const bPos = b.position ? 1 : 0;
      if (aPos !== bPos) return bPos - aPos;
      if (aPos && bPos) return posEquity(b) - posEquity(a);
      return (volumes[b.symbol] || 0) - (volumes[a.symbol] || 0);
    });
  });
  let health = $derived(snap?.health || {});
  let balances = $derived(snap?.balances || {});
  let daily = $derived(snap?.daily || {});
  let recent = $derived(snap?.recent || {});
  let openPositions = $derived(snap?.open_positions || []);
  let selectedModeKey = $derived(
    (appState.mode === 'paper' || !appState.mode) ? 'paper1' : appState.mode
  );
  let selectedModeRuntimeState = $derived(getModeRuntimeState(selectedModeKey));
  let selectedModeRuntimeLabel = $derived(getModeRuntimeLabel(selectedModeKey));
  let selectedLiveStrategyMode = $derived(
    selectedModeKey === 'live' ? resolveStrategyMode(health) : ''
  );
  let selectedLivePromotedFamily = $derived(
    promotedFamilyLabel(selectedLiveStrategyMode)
  );

  // ── Range selector for PnL / DD ───────────────────────────────────────
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
</script>

<!-- Mode selector + metrics -->
<div class="topbar">
  <div class="topbar-row">
    <div class="mode-tabs">
      <button
        class="mode-btn mode-btn-live"
        class:active={appState.mode === LIVE_MODE}
        onclick={() => setMode(LIVE_MODE)}
      >{getModeLabel(LIVE_MODE)}</button>

      <span class="mode-divider" aria-hidden="true"></span>

      <div class="family-tabs">
        {#each CANDIDATE_FAMILY_ORDER as m}
          <button
            class="mode-btn"
            class:active={appState.mode === m || (appState.mode === 'paper' && m === 'paper1')}
            onclick={() => setMode(m)}
          >{getModeLabel(m)}</button>
        {/each}
      </div>
    </div>

    <div class="status-chip" class:ok={health.ok} class:bad={!health.ok}>
      <span class="status-dot" class:alive={health.ok}></span>
      {health.ok ? 'ENGINE' : 'NO HB'}
    </div>

    <div
      class="status-chip mode-runtime-chip"
      class:ok={selectedModeRuntimeState === 'on'}
      class:warn={selectedModeRuntimeState === 'off'}
      class:bad={selectedModeRuntimeState === 'error'}
      class:unknown={selectedModeRuntimeState === 'unknown'}
    >
      <span
        class="status-dot"
        class:alive={selectedModeRuntimeState === 'on'}
        class:warn-dot={selectedModeRuntimeState === 'off'}
        class:bad-dot={selectedModeRuntimeState === 'error'}
        class:unknown-dot={selectedModeRuntimeState === 'unknown'}
      ></span>
      {selectedModeRuntimeLabel}
    </div>

    {#if selectedModeKey === 'live'}
      <div class="status-chip live-promoted-chip" class:unknown={selectedLivePromotedFamily === 'NA'}>
        <span
          class="status-dot live-source-dot"
          class:unknown-dot={selectedLivePromotedFamily === 'NA'}
        ></span>
        {selectedLivePromotedFamily}
      </div>
    {/if}
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

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}
</div>

<!-- Mobile tab switcher -->
<div class="mobile-tabs">
  <button class="m-tab" class:active={mobileTab === 'symbols'} onclick={() => mobileTab = 'symbols'}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>
    Symbols
  </button>
  <button class="m-tab" class:active={mobileTab === 'detail'} onclick={() => { mobileTab = 'detail'; detailTab = 'detail'; }}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
    Detail
  </button>
  <button class="m-tab" class:active={mobileTab === 'feed'} onclick={() => { mobileTab = 'feed'; if (detailTab === 'detail') detailTab = 'trades'; }}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
    Feed
  </button>
</div>

<div class="dashboard-grid" class:is-dragging={dragging || chartDragging || journeyChartDragging} class:drag-col={dragging} class:drag-row={chartDragging || journeyChartDragging}>
  <!-- Symbol table -->
  <div class="panel symbols-panel" class:mobile-visible={mobileTab === 'symbols'} class:expanded-hidden={detailExpanded} style="width:{symWidth}px;min-width:{symWidth}px">
    <div class="panel-header">
      <div class="search-wrap">
        <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input
          type="text"
          class="search-input"
          placeholder="Filter..."
          bind:value={appState.search}
        />
      </div>
      <span class="sym-count">{filteredSymbols.length}</span>
    </div>
    <div class="sym-table-wrap">
      <table class="sym-table">
        <thead>
          <tr>
            <th>SYM</th>
            <th class="col-mid">MID</th>
            <th>SIG</th>
            <th>POS</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredSymbols as s (s.symbol)}
            <tr
              class:is-focus={focusSym === s.symbol}
              class:row-long={s.position?.type === 'LONG'}
              class:row-short={s.position?.type === 'SHORT'}
              onclick={() => setFocus(s.symbol)}
            >
              <td class="sym-name">{s.symbol}</td>
              <td class="num col-mid">
                <mid-price
                  symbol={s.symbol}
                  value={s.mid != null ? String(s.mid) : ''}
                  decimals={6}
                  onmid-flash-trigger={(e) => onMidFlashTrigger(e as CustomEvent, 'table')}
                ></mid-price>
              </td>
              <td>
                {#if isFreshSig(s.last_signal?.timestamp)}
                  {#if s.last_signal?.signal === 'BUY'}
                    <span class="sig-badge buy">BUY</span>
                  {:else if s.last_signal?.signal === 'SELL'}
                    <span class="sig-badge sell">SELL</span>
                  {/if}
                  <span class="sig-age">{sigAge(s.last_signal.timestamp)}</span>
                {:else}
                  <span class="sig-badge none">\u2014</span>
                {/if}
              </td>
              <td>
                {#if s.position}
                  <span class="pos-badge" class:long={s.position.type === 'LONG'} class:short={s.position.type === 'SHORT'}>
                    {s.position.type}
                  </span>
                  {#if s.position.unreal_pnl_est != null}
                    {@const pct = pnlPct(s.position)}
                    <span class="pos-pnl {pnlClass(s.position.unreal_pnl_est)}">
                      {s.position.unreal_pnl_est >= 0 ? '+' : ''}{fmtNum(s.position.unreal_pnl_est)}{pct != null ? ` ${pct >= 0 ? '+' : ''}${fmtNum(pct, 1)}%` : ''}
                    </span>
                  {/if}
                  {#if s.position.open_timestamp}
                    <span class="pos-age">{sigAge(s.position.open_timestamp)}</span>
                  {/if}
                {:else}
                  <span class="flat-label">flat</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Drag splitter -->
  <div class="splitter" class:active={dragging} class:expanded-hidden={detailExpanded} role="separator" aria-orientation="vertical" onpointerdown={onSplitterDown}></div>

  <!-- Detail + Feed panel (merged, tabbed) -->
  <div class="panel detail-panel" class:mobile-visible={mobileTab === 'detail' || mobileTab === 'feed'}>
    <div class="panel-header detail-header">
      {#if focusSym}
        <div class="focus-sym">
          <h3>{focusSym}</h3>
          {#each symbols.filter((s: any) => s.symbol === focusSym).slice(0, 1) as sym}
            <mid-price
              symbol={sym.symbol}
              tone="accent"
              value={sym.mid != null ? String(sym.mid) : ''}
              decimals={6}
              onmid-flash-trigger={(e) => onMidFlashTrigger(e as CustomEvent, 'detail')}
            ></mid-price>
          {/each}
        </div>
      {/if}
      <div class="detail-tabs">
        <button class="tab" class:is-on={detailTab === 'detail'} onclick={() => detailTab = 'detail'}>DETAIL</button>
        <button class="tab" class:is-on={detailTab === 'trades'} onclick={() => setFeed('trades')}>TRADES</button>
        <button class="tab" class:is-on={detailTab === 'oms'} onclick={() => setFeed('oms')}>OMS</button>
        <button class="tab" class:is-on={detailTab === 'audit'} onclick={() => setFeed('audit')}>AUDIT</button>
      </div>
      <button class="expand-btn" aria-label={detailExpanded ? 'Collapse' : 'Expand'} onclick={() => detailExpanded = !detailExpanded}>
        {#if detailExpanded}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7"/></svg>
        {:else}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
        {/if}
      </button>
      {#if focusSym}
        <button class="close-focus" aria-label="Close" onclick={() => { focusSym = ''; mobileTab = 'symbols'; }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      {/if}
    </div>

    {#if detailTab === 'detail'}
      {#if focusSym}
        <!-- Interval + bar count selector -->
        <div class="iv-bar">
          {#each INTERVALS as iv}
            <button
              class="iv-tab"
              class:is-on={selectedInterval === iv}
              onclick={() => { selectedInterval = iv; }}
            >{iv.toUpperCase()}</button>
          {/each}
          <span class="iv-sep"></span>
          {#each BAR_COUNTS as bc}
            <button
              class="iv-tab"
              class:is-on={selectedBars === bc}
              onclick={() => { selectedBars = bc; }}
            >{bc}</button>
          {/each}
        </div>
        <div class="chart-wrap" style="height:{chartHeight}px">
          <candle-chart
            candles={candles}
            entries={marks?.entries || []}
            entryPrice={marks?.position?.entry_price ?? 0}
            postype={marks?.position?.type ?? ''}
            symbol={focusSym}
            interval={selectedInterval}
            tunnelpoints={JSON.stringify(tunnelPoints)}
            onneed-candles={onMainNeedCandles}
          ></candle-chart>
        </div>
        <div class="chart-splitter" class:active={chartDragging} role="separator" aria-orientation="horizontal" onpointerdown={onChartSplitterDown}></div>

        {#if marks?.position}
          {@const p = marks.position}
          {@const livePos = snap?.symbols?.find((s: any) => s.symbol === focusSym)?.position}
          <div class="kv-section">
            <h4>Position</h4>
            <div class="kv"><span class="k">Type</span><span class="v">{p.pos_type || p.type}</span></div>
            <div class="kv"><span class="k">Size</span><span class="v mono">{fmtNum(p.size, 6)}</span></div>
            <div class="kv"><span class="k">Entry</span><span class="v mono">{fmtNum(p.entry_price, 6)}</span></div>
            <div class="kv"><span class="k">uPnL</span><span class="v {pnlClass(livePos?.unreal_pnl_est)}">{fmtNum(livePos?.unreal_pnl_est)}</span></div>
            <div class="kv"><span class="k">Leverage</span><span class="v">{fmtNum(p.leverage, 1)}x</span></div>
          </div>
          {#if marks?.entries?.length}
            <div class="kv-section">
              <h4>Entries</h4>
              {#each marks.entries as e}
                <div class="kv">
                  <span class="k">{e.action}</span>
                  <span class="v mono">@ {fmtNum(e.price, 6)} &times; {fmtNum(e.size, 4)}</span>
                </div>
              {/each}
            </div>
          {/if}
        {:else}
          <div class="empty-state">
            <span class="empty-label">Flat</span>
            <span class="empty-sub">No open position</span>
          </div>
        {/if}

        {#if appState.mode === 'live' && manualTradeEnabled}
          <trade-panel
            symbol={focusSym}
            position={JSON.stringify(marks?.position || null)}
            mid={String(symbols.find((s: any) => s.symbol === focusSym)?.mid ?? '')}
            mode={appState.mode}
            engine-running={liveEngineActive ? 'true' : 'false'}
            ontradedone={async () => { await refresh(); try { marks = await getMarks(focusSym, appState.mode); } catch {} }}
          ></trade-panel>
        {/if}
      {:else}
        <div class="empty-focus">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-dim)" stroke-width="1"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
          <p>Select a symbol</p>
        </div>
      {/if}
    {:else}
      <!-- Feed content (trades / oms / audit) -->
      <div class="feed-content">
        {#if detailTab === 'trades'}
          <!-- Journey chart -->
          <div class="journey-chart-area" style="height:{selectedJourney ? journeyChartHeight : 48}px">
            {#if selectedJourney}
              <div class="journey-chart-header">
                <span class="journey-chart-label">
                  {selectedJourney.symbol}
                  <span class="badge" class:badge-long={selectedJourney.type === 'LONG'} class:badge-short={selectedJourney.type !== 'LONG'}>{selectedJourney.type}</span>
                </span>
                <div class="journey-iv-bar">
                  {#each INTERVALS as iv}
                    <button
                      class="jiv-tab"
                      class:is-on={journeyInterval === iv}
                      onclick={() => changeJourneyInterval(iv)}
                    >{iv.toUpperCase()}</button>
                  {/each}
                </div>
                <button class="journey-close-btn" onclick={() => { selectedJourney = null; journeyCandles = []; journeyMarks = []; journeyTunnelPoints = []; }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
              </div>
              <div class="journey-chart-wrap" style="height:{journeyChartHeight - 30}px">
                <candle-chart
                  candles={JSON.stringify(journeyCandles)}
                  entries="[]"
                  entryPrice={0}
                  postype=""
                  symbol={selectedJourney.symbol}
                  interval={journeyInterval}
                  journeymarks={JSON.stringify(journeyMarks)}
                  journeyoverlay={true}
                  tunnelpoints={JSON.stringify(journeyTunnelPoints)}
                  onneed-candles={onJourneyNeedCandles}
                ></candle-chart>
              </div>
            {:else}
              <div class="journey-hint">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--text-dim)" stroke-width="1.5"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 6-10"/></svg>
                <span>Select a journey below to view on chart</span>
              </div>
            {/if}
          </div>
          {#if selectedJourney}
            <div class="journey-chart-splitter" class:active={journeyChartDragging} role="separator" aria-orientation="horizontal" onpointerdown={onJourneyChartSplitterDown}></div>
          {/if}
          <!-- Journey list -->
          <div class="journey-list">
            {#each journeys as j (j.id)}
              {@const openMs = Date.parse((j.open_ts || '').replace(' ', 'T'))}
              {@const closeMs = j.close_ts ? Date.parse(j.close_ts.replace(' ', 'T')) : Date.now()}
              {@const dur = isFinite(openMs) && isFinite(closeMs) ? closeMs - openMs : 0}
              <button
                class="journey-card"
                class:selected={selectedJourney?.id === j.id}
                onclick={() => selectJourney(j)}
              >
                <div class="jc-top">
                  <span class="jc-sym">{j.symbol}</span>
                  <span class="badge" class:badge-long={j.type === 'LONG'} class:badge-short={j.type !== 'LONG'}>{j.type}</span>
                  {#if j.is_open}<span class="jc-open-dot" title="Still open"></span>{/if}
                  <span class="jc-age dim">{sigAge(j.close_ts || j.open_ts)}</span>
                  <span class="jc-dur dim">{fmtDuration(dur)}</span>
                  <span class="jc-pnl mono {j.total_pnl >= 0 ? 'green' : 'red'}">{j.total_pnl >= 0 ? '+' : ''}{fmtNum(j.total_pnl)}</span>
                </div>
                <div class="jc-sub dim">
                  {j.open_ts?.slice(5, 16) || ''}
                  &rarr; {j.close_ts ? j.close_ts.slice(5, 16) : 'now'}
                  <span class="mono">{fmtNum(j.entry_price, 6)}</span>
                  {#if j.exit_price != null}<span class="mono">&rarr; {fmtNum(j.exit_price, 6)}</span>{/if}
                  <span class="dim">({j.legs?.length || 0} legs)</span>
                </div>
              </button>
            {/each}
            {#if journeyLoading}
              <div class="journey-loading">Loading...</div>
            {:else if journeyHasMore && journeys.length > 0}
              <button class="journey-load-more" onclick={() => fetchJourneys()}>Load more</button>
            {:else if journeys.length === 0}
              <div class="journey-empty">No trade journeys found</div>
            {/if}
          </div>
        {:else if detailTab === 'oms'}
          {#each (recent.oms_intents || []).slice(0, 25) as i}
            <div class="feed-item">
              <div class="feed-row">
                <span class="feed-l">
                  <span class="feed-sym">{i.symbol}</span>
                  {i.action} {i.side}
                  <span class:green={i.status === 'FILLED'} class:red={i.status === 'REJECTED'} class:yellow={i.status !== 'FILLED' && i.status !== 'REJECTED'}>{i.status}</span>
                </span>
                <span class="feed-r">{i.created_ts_ms ? new Date(i.created_ts_ms).toISOString().slice(11, 19) : ''}Z</span>
              </div>
              <div class="feed-sub">reason: {i.reason || '\u2014'} conf: {i.confidence || '\u2014'}</div>
            </div>
          {/each}
          {#each (recent.oms_fills || []).slice(0, 15) as f}
            <div class="feed-item">
              <div class="feed-row">
                <span class="feed-l">FILL {f.symbol} {f.side} {fmtNum(f.size, 6)}</span>
                <span class="feed-r">{f.ts_ms ? new Date(f.ts_ms).toISOString().slice(11, 19) : ''}Z</span>
              </div>
              <div class="feed-sub">px {fmtNum(f.price, 6)} pnl <span class="{pnlClass(f.pnl_usd)}">{f.pnl_usd != null ? fmtNum(f.pnl_usd) : '\u2014'}</span></div>
            </div>
          {/each}
        {:else if detailTab === 'audit'}
          {#each (recent.audit_events || []).slice(0, 40) as a}
            <div class="feed-item">
              <div class="feed-row">
                <span class="feed-l">{a.event || '\u2014'} {a.symbol || ''}</span>
                <span class="feed-r">{a.timestamp?.slice(11, 19) || ''}</span>
              </div>
              <div class="feed-sub">{a.level || 'info'}</div>
            </div>
          {/each}
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  /* ─── Topbar ─── */
  .topbar {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 12px;
    animation: slideUp 0.3s ease;
  }
  .topbar-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .mode-tabs {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg);
    border-radius: var(--radius-md);
    padding: 4px;
    border: 1px solid var(--border);
  }
  .family-tabs {
    display: flex;
    gap: 3px;
  }
  .mode-divider {
    width: 1px;
    background: var(--border);
    align-self: stretch;
    opacity: 0.9;
  }
  .mode-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    padding: 5px 14px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    font-family: 'IBM Plex Mono', monospace;
    transition: all var(--t-fast);
    white-space: nowrap;
  }
  .mode-btn:hover {
    color: var(--text);
    background: var(--surface-hover);
  }
  .mode-btn.active {
    background: var(--accent);
    color: var(--bg);
    box-shadow: 0 1px 4px rgba(77,171,247,0.3);
  }
  .mode-btn-live {
    color: rgba(255,107,107,0.95);
    border: 1px solid rgba(255,107,107,0.35);
    flex-shrink: 0;
  }
  .mode-btn-live:hover {
    background: rgba(255,107,107,0.12);
    color: #ffc9c9;
  }
  .mode-btn-live.active {
    background: var(--red);
    box-shadow: 0 1px 4px rgba(255,107,107,0.3);
    color: var(--bg);
    border-color: transparent;
  }

  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.04em;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--border);
    white-space: nowrap;
  }
  .status-chip.ok {
    border-color: rgba(81,207,102,0.3);
    color: var(--green);
  }
  .status-chip.bad {
    border-color: rgba(255,107,107,0.3);
    color: var(--red);
  }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--red);
  }
  .status-dot.alive {
    background: var(--green);
    box-shadow: 0 0 6px var(--green);
    animation: pulse 2s ease-in-out infinite;
  }
  .mode-runtime-chip.warn {
    border-color: rgba(255,212,59,0.35);
    color: var(--yellow);
  }
  .mode-runtime-chip.unknown {
    border-color: rgba(148,163,184,0.35);
    color: var(--text-dim);
  }
  .live-promoted-chip {
    border-color: rgba(77,171,247,0.35);
    color: #a5d8ff;
  }
  .live-promoted-chip.unknown {
    border-color: rgba(148,163,184,0.35);
    color: var(--text-dim);
  }
  .status-dot.live-source-dot {
    background: var(--accent);
    box-shadow: 0 0 6px rgba(77,171,247,0.45);
  }
  .status-dot.warn-dot {
    background: var(--yellow);
  }
  .status-dot.bad-dot {
    background: var(--red);
  }
  .status-dot.unknown-dot {
    background: var(--text-dim);
  }

  .metrics-bar {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
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
  .gt-title {
    font-weight: 600;
    font-size: 11px;
  }
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

  /* ─── Range dropdown ─── */
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

  .error-banner {
    padding: 6px 12px;
    border-radius: var(--radius-md);
    font-size: 12px;
    background: var(--red-bg);
    color: var(--red);
    border: 1px solid rgba(255,107,107,0.2);
  }

  /* ─── Mobile tabs ─── */
  .mobile-tabs {
    display: none;
    gap: 2px;
    margin-bottom: 8px;
    background: var(--bg);
    border-radius: var(--radius-md);
    padding: 3px;
    border: 1px solid var(--border);
  }
  .m-tab {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    padding: 8px 4px;
    border-radius: 5px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
  }
  .m-tab.active {
    background: var(--surface);
    color: var(--text);
  }

  /* ─── Grid layout ─── */
  .dashboard-grid {
    display: flex;
    gap: 0;
    height: calc(100vh - 140px);
    height: calc(100dvh - 140px);
    min-height: 400px;
  }
  .dashboard-grid.is-dragging {
    user-select: none;
  }
  .dashboard-grid.drag-col {
    cursor: col-resize;
  }
  .dashboard-grid.drag-row {
    cursor: row-resize;
  }

  .splitter {
    width: 10px;
    cursor: col-resize;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }
  .splitter::after {
    content: '';
    width: 3px;
    height: 32px;
    border-radius: 2px;
    background: var(--border);
    transition: background var(--t-fast);
  }
  .splitter:hover::after,
  .splitter.active::after {
    background: var(--accent);
  }

  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    gap: 8px;
  }
  .panel-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }

  /* ─── Expanded detail (hide symbol panel + splitter) ─── */
  .expanded-hidden {
    display: none !important;
  }

  /* ─── Symbol table ─── */
  .symbols-panel { flex-shrink: 0; }

  .search-wrap {
    position: relative;
    flex: 1;
  }
  .search-icon {
    position: absolute;
    left: 8px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-dim);
    pointer-events: none;
  }
  .search-input {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 6px 8px 6px 28px;
    border-radius: var(--radius-md);
    font-size: 12px;
    font-family: 'IBM Plex Mono', monospace;
    transition: border-color var(--t-fast);
  }
  .search-input:focus {
    outline: none;
    border-color: var(--accent);
  }
  .sym-count {
    font-size: 11px;
    color: var(--text-dim);
    font-family: 'IBM Plex Mono', monospace;
    flex-shrink: 0;
  }
  .sym-table-wrap {
    overflow-y: auto;
    flex: 1;
  }
  .sym-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  .sym-table th {
    text-align: left;
    padding: 6px 10px;
    color: var(--text-dim);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--surface);
    z-index: 1;
  }
  .sym-table td {
    padding: 6px 10px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .sym-table tr {
    cursor: pointer;
    transition: background var(--t-fast);
  }
  .sym-table tr:hover {
    background: rgba(77,171,247,0.04);
  }
  .sym-table tr.is-focus {
    background: var(--accent-bg);
  }
  .sym-table tr.row-long {
    border-left: 2px solid var(--green);
  }
  .sym-table tr.row-short {
    border-left: 2px solid var(--red);
  }

  /* Price flash animation styles live in Lit web component: wc/mid-price.ts */

  .sym-name {
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.02em;
  }

  .num {
    font-variant-numeric: tabular-nums;
    text-align: right;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--text);
  }

  .sig-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.04em;
  }
  .sig-badge.buy {
    background: var(--green-bg);
    color: var(--green);
  }
  .sig-badge.sell {
    background: var(--red-bg);
    color: var(--red);
  }
  .sig-badge.none {
    color: var(--text-dim);
  }

  .pos-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.04em;
  }
  .pos-badge.long {
    color: var(--green);
    background: var(--green-bg);
  }
  .pos-badge.short {
    color: var(--red);
    background: var(--red-bg);
  }
  .flat-label {
    color: var(--text-dim);
    font-size: 11px;
  }
  .pos-pnl {
    display: inline;
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 500;
    margin-left: 4px;
    letter-spacing: 0.01em;
  }
  .sig-age {
    display: inline;
    font-size: 9px;
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    margin-left: 3px;
  }
  .pos-pnl.green { color: var(--green); }
  .pos-pnl.red   { color: var(--red); }
  .pos-age {
    display: inline;
    font-size: 9px;
    color: var(--text);
    margin-left: 3px;
  }

  /* ─── Detail panel ─── */
  .detail-panel { overflow-y: auto; flex: 1; min-width: 0; }
  .detail-tabs {
    display: flex;
    gap: 2px;
    background: var(--bg);
    border-radius: 5px;
    padding: 2px;
    flex-shrink: 0;
  }

  /* ─── Interval selector ─── */
  .iv-bar {
    display: flex;
    gap: 1px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border-subtle);
    flex-shrink: 0;
    background: var(--surface);
  }
  .iv-tab {
    background: transparent;
    border: none;
    color: var(--text-dim);
    padding: 3px 7px;
    cursor: pointer;
    font-size: 10px;
    font-weight: 600;
    border-radius: 3px;
    letter-spacing: 0.05em;
    font-family: 'IBM Plex Mono', monospace;
    transition: all var(--t-fast);
  }
  .iv-tab:hover { color: var(--text); background: rgba(255,255,255,0.04); }
  .iv-tab.is-on { color: var(--accent); background: var(--accent-bg); }
  .iv-sep {
    width: 1px;
    height: 14px;
    background: var(--border);
    margin: 0 4px;
    align-self: center;
    flex-shrink: 0;
  }

  /* ─── Candle chart container ─── */
  .chart-wrap {
    flex-shrink: 0;
    overflow: hidden;
    touch-action: none;
  }
  .chart-splitter {
    height: 8px;
    cursor: row-resize;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    border-bottom: 1px solid var(--border-subtle);
  }
  .chart-splitter::after {
    content: '';
    width: 32px;
    height: 3px;
    border-radius: 2px;
    background: var(--border);
    transition: background var(--t-fast);
  }
  .chart-splitter:hover::after,
  .chart-splitter.active::after {
    background: var(--accent);
  }
  @media (max-width: 768px) {
    .chart-wrap { height: 200px !important; }
    .chart-splitter { display: none; }
  }
  .detail-header {
    gap: 8px;
  }
  .focus-sym {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex: 1;
  }
  .focus-sym h3 {
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: -0.01em;
  }
  .expand-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
  }
  .expand-btn:hover {
    background: var(--surface-hover);
    color: var(--text);
  }
  .close-focus {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
  }
  .close-focus:hover {
    background: var(--surface-hover);
    color: var(--text);
  }

  .kv-section {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-subtle);
    animation: slideUp 0.2s ease;
  }
  .kv-section h4 {
    margin: 0 0 8px;
    font-size: 10px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
  }
  .kv {
    display: flex;
    justify-content: space-between;
    padding: 3px 0;
    font-size: 12px;
  }
  .kv .k { color: var(--text-muted); }
  .kv .v { font-weight: 500; }

  .empty-focus {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 8px;
    color: var(--text-dim);
  }
  .empty-focus p {
    font-size: 13px;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px;
    gap: 2px;
  }
  .empty-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
  }
  .empty-sub {
    font-size: 11px;
    color: var(--text-dim);
  }

  /* ─── Feed content ─── */
  .feed-tabs {
    display: flex;
    gap: 2px;
    background: var(--bg);
    border-radius: 5px;
    padding: 2px;
  }
  .tab {
    background: transparent;
    border: none;
    color: var(--text-muted);
    padding: 4px 10px;
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
    border-radius: 4px;
    letter-spacing: 0.04em;
    font-family: 'IBM Plex Mono', monospace;
    transition: all var(--t-fast);
  }
  .tab:hover {
    color: var(--text);
  }
  .tab.is-on {
    color: var(--accent);
    background: var(--accent-bg);
  }
  .feed-content {
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .feed-item {
    padding: 8px 14px;
    border-bottom: 1px solid var(--border-subtle);
    font-size: 12px;
    transition: background var(--t-fast);
  }
  .feed-item:hover {
    background: rgba(255,255,255,0.015);
  }
  .feed-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .feed-l { font-weight: 500; display: flex; gap: 6px; align-items: center; }
  .feed-sym {
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    font-size: 11px;
  }
  .feed-action { font-size: 11px; }
  .feed-type { font-size: 11px; color: var(--text-muted); }
  .feed-r {
    color: var(--text-dim);
    font-size: 10px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .feed-sub {
    color: var(--text-muted);
    font-size: 11px;
    margin-top: 3px;
  }
  .green { color: var(--green); }
  .red { color: var(--red); }
  .yellow { color: var(--yellow); }

  /* ─── Journey ─── */
  .journey-chart-area {
    overflow: hidden;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }
  .journey-chart-header {
    display: flex;
    align-items: center;
    padding: 4px 10px;
    font-size: 11px;
    gap: 6px;
  }
  .journey-chart-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    flex-shrink: 0;
  }
  .journey-iv-bar {
    display: flex;
    gap: 2px;
    margin-left: auto;
  }
  .jiv-tab {
    background: none;
    border: 1px solid transparent;
    color: var(--text-dim);
    font-size: 9px;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    cursor: pointer;
    font-family: 'IBM Plex Mono', monospace;
  }
  .jiv-tab:hover { color: var(--text); }
  .jiv-tab.is-on {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--accent-bg);
  }
  .journey-close-btn {
    background: none;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    padding: 2px;
    flex-shrink: 0;
    margin-left: 4px;
  }
  .journey-close-btn:hover { color: var(--text); }
  .journey-chart-wrap {
    flex: 1;
    min-height: 0;
    position: relative;
    touch-action: none;
  }
  .journey-chart-splitter {
    height: 5px;
    cursor: row-resize;
    background: transparent;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
    transition: background 0.15s;
  }
  .journey-chart-splitter:hover,
  .journey-chart-splitter.active {
    background: var(--accent-bg, rgba(59,130,246,0.1));
  }
  .journey-hint {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 100%;
    color: var(--text-dim);
    font-size: 12px;
  }
  .journey-list {
    overflow-y: auto;
    flex: 1;
    min-height: 80px;
  }
  .journey-card {
    display: block;
    width: 100%;
    text-align: left;
    padding: 8px 14px;
    border: none;
    border-bottom: 1px solid var(--border-subtle);
    background: none;
    color: var(--text);
    cursor: pointer;
    font-size: 12px;
    transition: background var(--t-fast);
  }
  .journey-card:hover { background: rgba(255,255,255,0.02); }
  .journey-card.selected {
    background: rgba(59,130,246,0.08);
    border-left: 2px solid var(--accent, #3b82f6);
  }
  .jc-top {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .jc-sym {
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    font-size: 11px;
  }
  .badge {
    font-size: 9px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 3px;
    text-transform: uppercase;
  }
  .badge-long { background: rgba(59,130,246,0.2); color: #93c5fd; }
  .badge-short { background: rgba(245,158,11,0.2); color: #fcd34d; }
  .jc-open-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--green);
    display: inline-block;
  }
  .jc-age { font-size: 10px; }
  .jc-dur { font-size: 10px; opacity: 0.7; }
  .jc-pnl {
    margin-left: auto;
    font-weight: 600;
    font-size: 11px;
  }
  .jc-sub {
    font-size: 10px;
    margin-top: 2px;
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .journey-loading, .journey-empty {
    padding: 16px;
    text-align: center;
    color: var(--text-dim);
    font-size: 12px;
  }
  .journey-load-more {
    display: block;
    width: 100%;
    padding: 10px;
    border: none;
    background: none;
    color: var(--accent, #3b82f6);
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  }
  .journey-load-more:hover { background: rgba(59,130,246,0.06); }

  /* ─── Mobile ─── */
  @media (max-width: 768px) {
    .topbar-row {
      flex-wrap: wrap;
    }
    .mode-tabs {
      width: 100%;
      flex-wrap: nowrap;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      gap: 4px;
      padding: 4px;
    }
    .family-tabs {
      display: flex;
      width: auto;
      gap: 4px;
      flex-shrink: 0;
    }
    .mode-divider {
      display: block;
    }
    .mode-btn-live {
      width: auto;
      text-align: center;
      flex-shrink: 0;
    }
    .family-tabs .mode-btn {
      width: auto;
      min-width: 0;
      text-align: center;
      flex-shrink: 0;
    }
    .metrics-bar {
      gap: 4px;
    }
    .metric-pill {
      font-size: 10px;
      padding: 2px 7px;
    }

    .mobile-tabs {
      display: flex;
    }

    .dashboard-grid {
      flex-direction: column;
      height: calc(100dvh - 240px);
    }

    .splitter { display: none; }
    .expand-btn { display: none; }

    .symbols-panel {
      width: auto !important;
      min-width: 0 !important;
    }

    .panel {
      display: none;
    }
    .panel.mobile-visible {
      display: flex;
    }

    /* Column widths for ~375px: SYM 24 / MID 12 / SIG 22 / POS 42 */
    .sym-table {
      table-layout: fixed;
    }
    .sym-table th:nth-child(1), .sym-table td:nth-child(1) { width: 15%; }
    .sym-table th:nth-child(2), .sym-table td:nth-child(2) { width: 20%; }
    .sym-table th:nth-child(3), .sym-table td:nth-child(3) { width: 25%; }
    .sym-table th:nth-child(4), .sym-table td:nth-child(4) { width: 40%; }

    .col-mid {
      font-size: 10px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .sym-table td {
      padding: 10px 6px;
    }
    .sym-table tr {
      min-height: 44px;
    }
  }

  @media (max-width: 480px) {
    .mode-tabs {
      width: 100%;
      flex-wrap: nowrap;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      gap: 3px;
      padding: 3px;
    }
    .family-tabs {
      display: flex;
      width: auto;
      gap: 3px;
      flex-shrink: 0;
    }
    .mode-divider {
      display: block;
    }
    .mode-btn-live {
      width: auto;
      flex-shrink: 0;
    }
    .family-tabs .mode-btn {
      width: auto;
      flex-shrink: 0;
    }
    .mode-btn {
      padding: 4px 8px;
      font-size: 10px;
    }
    .metric-pill {
      font-size: 9px;
      padding: 2px 5px;
    }
    .metric-label {
      display: none;
    }
  }
</style>
