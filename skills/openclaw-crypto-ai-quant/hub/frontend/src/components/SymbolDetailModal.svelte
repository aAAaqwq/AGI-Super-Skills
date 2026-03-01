<script lang="ts">
  import { getCandles, getMarks, getCandlesRange, getJourneys, getTunnel, tradeEnabled, getSystemServices } from '../lib/api';
  import { hubWs } from '../lib/ws';

  const INTERVALS = ['1m', '3m', '5m', '15m', '30m', '1h'] as const;
  const BAR_COUNTS = [50, 100, 200] as const;
  const CHART_MIN = 120;
  const CHART_MAX = 600;
  const JOURNEY_CHART_MIN = 120;
  const JOURNEY_CHART_MAX = 600;

  let { symbol, mode, snap, mids, onclose }: {
    symbol: string;
    mode: string;
    snap: any;
    mids: Record<string, number>;
    onclose: () => void;
  } = $props();

  // ── Derived state (from parent props) ───────────────────────────────
  let symbolData = $derived(snap?.symbols?.find((s: any) => s.symbol === symbol));
  let position = $derived(symbolData?.position);
  let liveMid = $derived(mids[symbol] ?? symbolData?.mid ?? 0);
  let recent = $derived(snap?.recent || {});

  // ── Own state ───────────────────────────────────────────────────────
  let detailTab: 'detail' | 'trades' | 'oms' | 'audit' = $state('detail');
  let candles: any[] = $state([]);
  let marks: any = $state(null);
  let selectedInterval = $state('1h');
  let selectedBars: number = $state(200);
  let chartHeight = $state(260);
  let chartDragging = $state(false);

  // Journey state (lazy-loaded on TRADES tab)
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

  // Tunnel state (exit bounds visualization)
  let tunnelPoints: any[] = $state([]);
  let journeyTunnelPoints: any[] = $state([]);

  // Trade panel gating
  let manualTradeEnabled = $state(false);
  let liveEngineActive = $state(false);

  // Mobile swipe-down state
  let sheetTranslateY = $state(0);
  let sheetSwiping = $state(false);

  // ── Live candle pipeline state ──────────────────────────────────────
  let _candlesSeriesSym = '';
  let _candlesSeriesInterval = '';
  let _lastLiveFrameMs = 0;
  let _lastLiveTickKey = '';
  let _serverNowOffsetMs = 0;
  let _candlesFetchInFlight = false;
  let _candlesFetchQueued = false;
  let _candlesRolloverReconcileTimer: ReturnType<typeof setTimeout> | null = null;
  let mainExtending = false;
  const CANDLE_ROLLOVER_RECONCILE_DELAY_MS = 1600;
  const CANDLE_PERIODIC_RECONCILE_MS = 25_000;

  // ── Utility helpers ─────────────────────────────────────────────────
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
  function pnlPct(pos: any): number | null {
    if (!pos || pos.entry_price == null || !pos.size || pos.unreal_pnl_est == null) return null;
    const notional = pos.entry_price * Math.abs(pos.size);
    if (notional === 0) return null;
    return (pos.unreal_pnl_est / notional) * 100;
  }
  function pnlClass(v: number | null | undefined): string {
    if (v === null || v === undefined) return '';
    return v >= 0 ? 'green' : 'red';
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
      if (t <= ts && t > bestT) { bestT = t; idx = i; }
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
  function mergeCandles(existing: any[], incoming: any[]): any[] {
    const map = new Map<number, any>();
    for (const c of existing) map.set(c.t, c);
    for (const c of incoming) if (!map.has(c.t)) map.set(c.t, c);
    return [...map.values()].sort((a, b) => a.t - b.t);
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
  function pickJourneyInterval(durationMs: number): string {
    if (durationMs < 30 * 60_000)       return '1m';
    if (durationMs < 2 * 60 * 60_000)   return '3m';
    if (durationMs < 6 * 60 * 60_000)   return '5m';
    if (durationMs < 24 * 60 * 60_000)  return '15m';
    return '1h';
  }
  function journeyTimeRange(j: any) {
    const openTs = Date.parse((j.open_ts || '').replace(' ', 'T'));
    const closeTs = j.close_ts ? Date.parse((j.close_ts || '').replace(' ', 'T')) : Date.now();
    if (!isFinite(openTs)) return null;
    const dur = closeTs - openTs;
    const pad = Math.max(dur * 0.1, 60_000);
    return { openTs, closeTs, dur, fromTs: Math.floor(openTs - pad), toTs: Math.ceil(closeTs + pad) };
  }

  // ── Candle pipeline helpers ─────────────────────────────────────────
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
    if (_candlesSeriesSym === sym && _candlesSeriesInterval) return _candlesSeriesInterval;
    return requestedIv;
  }

  function publishCandlesMutation() {
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
    const tClose = Number.isFinite(tCloseRaw) && tCloseRaw > 0 ? tCloseRaw : (t + intervalToMs(iv) - 1);
    return { t, t_close: tClose, o: open, h: Math.max(high, open, close), l: Math.min(low, open, close), c: close, v: Number(src?.v) || 0, n: Number(src?.n) || 0 };
  }

  function mergeOfficialCandlesWithDeveloping(officialRows: any[], developing: any | null, maxBars: number): any[] {
    const merged = Array.isArray(officialRows) ? [...officialRows] : [];
    if (developing) {
      const latestTs = merged.length > 0 ? Number(merged[newestCandleIndex(merged)]?.t || 0) : 0;
      if (!Number.isFinite(latestTs) || latestTs < Number(developing.t || 0)) merged.push(developing);
    }
    if (merged.length > maxBars) return merged.slice(merged.length - maxBars);
    return merged;
  }

  async function reconcileCandlesForCurrentView(sym = symbol, iv = selectedInterval, bars = selectedBars): Promise<void> {
    if (!sym) return;
    const keepDeveloping = hasCandlesSeriesContext(sym, iv);
    const developingBeforeFetch = keepDeveloping ? snapshotDevelopingCandle(candles, iv) : null;
    if (_candlesFetchInFlight) { _candlesFetchQueued = true; return; }
    _candlesFetchInFlight = true;
    try {
      const res = await getCandles(sym, iv, bars);
      if (symbol !== sym || selectedInterval !== iv || selectedBars !== bars) return;
      const officialRows = Array.isArray(res?.candles) ? res.candles : [];
      const developingCurrent = keepDeveloping ? snapshotDevelopingCandle(candles, iv) : null;
      candles = mergeOfficialCandlesWithDeveloping(officialRows, developingCurrent ?? developingBeforeFetch, bars);
      // Advance to the current bar if the newest candle's period has elapsed.
      const msPerBar = intervalToMs(iv);
      const nowMs = serverNowMs();
      const currentBarStart = Math.floor(nowMs / msPerBar) * msPerBar;
      if (candles.length > 0) {
        const nIdx = newestCandleIndex(candles);
        const nT = Number(candles[nIdx]?.t || 0);
        if (nT > 0 && nT < currentBarStart) {
          const prevClose = Number(candles[nIdx]?.c || 0);
          const mid = finitePositive(mids[sym]) ?? liveMid ?? prevClose;
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
      _lastLiveTickKey = '';
      setCandlesSeriesContext(sym, iv);
      void fetchTunnelForLive();
    } catch {} finally {
      _candlesFetchInFlight = false;
      if (_candlesFetchQueued) { _candlesFetchQueued = false; setTimeout(() => { void reconcileCandlesForCurrentView(); }, 0); }
    }
  }

  // ── Tunnel data fetch (live position) ─────────────────────────────
  async function fetchTunnelForLive() {
    if (!position || !symbol) { tunnelPoints = []; return; }
    try {
      const res = await getTunnel(symbol, mode);
      tunnelPoints = Array.isArray(res?.tunnel) ? res.tunnel : [];
    } catch { tunnelPoints = []; }
  }

  // ── Tunnel data fetch (journey review) ────────────────────────────
  async function fetchTunnelForJourney(j: any, fromTs: number, toTs: number) {
    if (!j) { journeyTunnelPoints = []; return; }
    try {
      const res = await getTunnel(j.symbol, mode, fromTs, toTs);
      journeyTunnelPoints = Array.isArray(res?.tunnel) ? res.tunnel : [];
    } catch { journeyTunnelPoints = []; }
  }

  function scheduleRolloverReconcile() {
    clearRolloverReconcileTimer();
    _candlesRolloverReconcileTimer = setTimeout(() => { _candlesRolloverReconcileTimer = null; void reconcileCandlesForCurrentView(); }, CANDLE_ROLLOVER_RECONCILE_DELAY_MS);
  }

  // ── Chart splitter drag ─────────────────────────────────────────────
  function onChartSplitterDown(e: PointerEvent) {
    e.preventDefault();
    chartDragging = true;
    const startY = e.clientY;
    const startH = chartHeight;
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);
    function onMove(ev: PointerEvent) { chartHeight = Math.max(CHART_MIN, Math.min(CHART_MAX, startH + (ev.clientY - startY))); }
    function onUp() { chartDragging = false; target.removeEventListener('pointermove', onMove); target.removeEventListener('pointerup', onUp); }
    target.addEventListener('pointermove', onMove);
    target.addEventListener('pointerup', onUp);
  }

  // ── Journey functions ───────────────────────────────────────────────
  async function fetchJourneys(reset = false) {
    if (journeyLoading) return;
    journeyLoading = true;
    try {
      const off = reset ? 0 : journeyOffset;
      const res = await getJourneys(mode, 50, off, symbol);
      const batch = res.journeys || [];
      if (reset) { journeys = batch; journeyOffset = batch.length; }
      else { journeys = [...journeys, ...batch]; journeyOffset += batch.length; }
      journeyHasMore = batch.length >= 50;
    } catch {} finally { journeyLoading = false; }
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
    } catch {}
    journeyMarks = (j.legs || []).map((leg: any) => ({
      price: leg.price, timestamp: leg.timestamp, action: leg.action,
      type: j.type || j.pos_type, size: leg.size, pnl: leg.pnl,
      reason: leg.reason, confidence: leg.confidence,
    }));
    void fetchTunnelForJourney(j, tr.fromTs, tr.toTs);
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
    } catch {}
  }

  function onJourneyChartSplitterDown(e: PointerEvent) {
    e.preventDefault();
    journeyChartDragging = true;
    const startY = e.clientY;
    const startH = journeyChartHeight;
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);
    function onMove(ev: PointerEvent) { journeyChartHeight = Math.max(JOURNEY_CHART_MIN, Math.min(JOURNEY_CHART_MAX, startH + (ev.clientY - startY))); }
    function onUp() { journeyChartDragging = false; target.removeEventListener('pointermove', onMove); target.removeEventListener('pointerup', onUp); }
    target.addEventListener('pointermove', onMove);
    target.addEventListener('pointerup', onUp);
  }

  async function onJourneyNeedCandles(e: CustomEvent) {
    const { before, after } = e.detail || {};
    if (journeyExtending || !selectedJourney) return;
    const j = selectedJourney;
    const tr = journeyTimeRange(j);
    if (!tr) return;
    const extension = Math.max(tr.dur, intervalToMs(journeyInterval) * 100);
    let newFrom = journeyFromTs, newTo = journeyToTs;
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
    } catch {} finally { journeyExtending = false; }
  }

  async function onMainNeedCandles(e: CustomEvent) {
    const { before } = e.detail || {};
    if (before == null || mainExtending || !symbol) return;
    const sym = symbol;
    const iv = selectedInterval;
    mainExtending = true;
    try {
      const res = await getCandlesRange(sym, iv, undefined, before, 500);
      if (symbol !== sym || selectedInterval !== iv) return;
      if (res.candles?.length) candles = mergeCandles(res.candles, candles);
    } catch {} finally { mainExtending = false; }
  }

  function setFeed(f: 'trades' | 'oms' | 'audit') {
    detailTab = f;
    if (f === 'trades') void fetchJourneys(true);
  }

  // ── Mobile swipe-down ───────────────────────────────────────────────
  function onDragHandleDown(e: PointerEvent) {
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);
    sheetSwiping = true;
    const startY = e.clientY;
    function onMove(ev: PointerEvent) {
      const dy = ev.clientY - startY;
      sheetTranslateY = Math.max(0, dy);
    }
    function onUp() {
      sheetSwiping = false;
      target.removeEventListener('pointermove', onMove);
      target.removeEventListener('pointerup', onUp);
      if (sheetTranslateY > 120) { onclose(); }
      sheetTranslateY = 0;
    }
    target.addEventListener('pointermove', onMove);
    target.addEventListener('pointerup', onUp);
  }

  // ── Lifecycle: Escape key ───────────────────────────────────────────
  $effect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onclose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  // ── Lifecycle: Body scroll lock ─────────────────────────────────────
  $effect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  });

  // ── Lifecycle: Fetch marks + candles on symbol change ───────────────
  let _prevSymbol = '';
  let _prevInterval = '';
  $effect(() => {
    const sym = symbol;
    const iv = selectedInterval;
    const bars = selectedBars;
    if (!sym) return;
    if (sym !== _prevSymbol) {
      candles = [];
      marks = null;
      _prevSymbol = sym;
      _prevInterval = iv;
      setCandlesSeriesContext('', '');
      // Reset journey state
      journeys = [];
      selectedJourney = null;
      journeyCandles = [];
      journeyMarks = [];
      journeyOffset = 0;
      journeyHasMore = true;
      detailTab = 'detail';
      // Fetch marks
      getMarks(sym, mode).then(r => { if (symbol === sym) marks = r; }).catch(() => {});
    } else if (iv !== _prevInterval) {
      _prevInterval = iv;
    }
    void reconcileCandlesForCurrentView(sym, iv, bars);
  });

  // ── Lifecycle: Periodic candle reconcile ────────────────────────────
  $effect(() => {
    const sym = symbol;
    const tab = detailTab;
    const iv = selectedInterval;
    const bars = selectedBars;
    if (!sym || tab !== 'detail') return;
    const id = setInterval(() => { void reconcileCandlesForCurrentView(sym, iv, bars); }, CANDLE_PERIODIC_RECONCILE_MS);
    return () => clearInterval(id);
  });

  // ── Lifecycle: Live candle update via WS ────────────────────────────
  $effect(() => {
    const sym = symbol;
    if (!sym) return;
    const handler = (data: any) => {
      updateServerClockOffset(data?.server_ts_ms);
      const localNow = Date.now();
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
      if (candleStart > barStart) {
        for (let i = candles.length - 1; i >= 0; i--) {
          const t = Number(candles[i]?.t || 0);
          if (Number.isFinite(t) && t > barStart) { candles.splice(i, 1); mutated = true; }
        }
        if (candles.length === 0) { if (mutated) publishCandlesMutation(); return; }
        liveIdx = newestCandleAtOrBefore(candles, barStart);
        if (liveIdx < 0) { if (mutated) publishCandlesMutation(); return; }
        c = candles[liveIdx];
        candleStart = Number(c?.t || 0);
        if (!Number.isFinite(candleStart) || candleStart <= 0) { if (mutated) publishCandlesMutation(); return; }
      }
      if (candleStart < barStart) {
        const prevClose = Number.isFinite(Number(c.c)) ? Number(c.c) : mid;
        candles.push({ t: barStart, t_close: barClose, o: prevClose, h: Math.max(prevClose, mid), l: Math.min(prevClose, mid), c: mid, v: 0, n: 0 });
        mutated = true;
        if (candles.length > selectedBars) candles.splice(0, candles.length - selectedBars);
        scheduleRolloverReconcile();
        _lastLiveFrameMs = localNow;
        publishCandlesMutation();
        return;
      }
      const closeMs = Number(c.t_close || 0);
      if (!Number.isFinite(closeMs) || closeMs <= 0 || closeMs < barClose) { c.t_close = barClose; mutated = true; }
      const prevClose = Number.isFinite(Number(c.c)) ? Number(c.c) : mid;
      const prevHigh = Number.isFinite(Number(c.h)) ? Number(c.h) : mid;
      const prevLow = Number.isFinite(Number(c.l)) ? Number(c.l) : mid;
      if (prevClose === mid && prevHigh >= mid && prevLow <= mid) { if (mutated) publishCandlesMutation(); return; }
      c.c = mid;
      c.h = Math.max(prevHigh, mid);
      c.l = Math.min(prevLow, mid);
      _lastLiveFrameMs = localNow;
      publishCandlesMutation();
    };
    hubWs.subscribe('mids', handler);
    hubWs.subscribe('bbo', handler);
    return () => { hubWs.unsubscribe('mids', handler); hubWs.unsubscribe('bbo', handler); };
  });

  // ── Lifecycle: Trade panel check ────────────────────────────────────
  $effect(() => {
    tradeEnabled().then(r => { manualTradeEnabled = r?.enabled ?? false; }).catch(() => {});
    getSystemServices().then(svcs => {
      const svc = (svcs || []).find((s: any) => s.name === 'openclaw-ai-quant-live-v8');
      liveEngineActive = String(svc?.active || '').toLowerCase() === 'active';
    }).catch(() => { liveEngineActive = false; });
  });

  // ── Cleanup rollover timer ──────────────────────────────────────────
  $effect(() => {
    return () => clearRolloverReconcileTimer();
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="modal-backdrop" onclick={onclose}></div>

<div
  class="modal-container"
  class:is-dragging={chartDragging || journeyChartDragging}
  style={sheetTranslateY > 0 ? `transform: translateY(${sheetTranslateY}px)` : ''}
>
  <!-- Mobile drag handle -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="drag-handle" onpointerdown={onDragHandleDown}>
    <div class="drag-pill"></div>
  </div>

  <!-- Header -->
  <div class="modal-header">
    <div class="header-left">
      <h3>{symbol}</h3>
      <mid-price
        symbol={symbol}
        tone="accent"
        value={liveMid ? String(liveMid) : ''}
        decimals={6}
      ></mid-price>
    </div>
    <div class="detail-tabs">
      <button class="tab" class:is-on={detailTab === 'detail'} onclick={() => detailTab = 'detail'}>DETAIL</button>
      <button class="tab" class:is-on={detailTab === 'trades'} onclick={() => setFeed('trades')}>TRADES</button>
      <button class="tab" class:is-on={detailTab === 'oms'} onclick={() => setFeed('oms')}>OMS</button>
      <button class="tab" class:is-on={detailTab === 'audit'} onclick={() => setFeed('audit')}>AUDIT</button>
    </div>
    <button class="close-btn" aria-label="Close" onclick={onclose}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 18L18 6M6 6l12 12"/></svg>
    </button>
  </div>

  <!-- Content -->
  <div class="modal-body">
    {#if detailTab === 'detail'}
      <!-- Interval + bar count selector -->
      <div class="iv-bar">
        {#each INTERVALS as iv}
          <button class="iv-tab" class:is-on={selectedInterval === iv} onclick={() => { selectedInterval = iv; }}>{iv.toUpperCase()}</button>
        {/each}
        <span class="iv-sep"></span>
        {#each BAR_COUNTS as bc}
          <button class="iv-tab" class:is-on={selectedBars === bc} onclick={() => { selectedBars = bc; }}>{bc}</button>
        {/each}
      </div>
      <div class="chart-wrap" style="height:{chartHeight}px">
        <candle-chart
          candles={candles}
          entries={marks?.entries || []}
          entryPrice={marks?.position?.entry_price ?? 0}
          postype={marks?.position?.type ?? ''}
          symbol={symbol}
          interval={selectedInterval}
          tunnelpoints={JSON.stringify(tunnelPoints)}
          onneed-candles={onMainNeedCandles}
        ></candle-chart>
      </div>
      <div class="chart-splitter" class:active={chartDragging} role="separator" aria-orientation="horizontal" onpointerdown={onChartSplitterDown}></div>

      {#if marks?.position}
        {@const p = marks.position}
        {@const livePos = symbolData?.position}
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

      {#if mode === 'live' && manualTradeEnabled}
        <trade-panel
          symbol={symbol}
          position={JSON.stringify(marks?.position || null)}
          mid={String(liveMid || '')}
          mode={mode}
          engine-running={liveEngineActive ? 'true' : 'false'}
          ontradedone={async () => { try { marks = await getMarks(symbol, mode); } catch {} }}
        ></trade-panel>
      {/if}

    {:else}
      <!-- Feed content (trades / oms / audit) -->
      <div class="feed-content">
        {#if detailTab === 'trades'}
          <div class="journey-chart-area" style="height:{selectedJourney ? journeyChartHeight : 48}px">
            {#if selectedJourney}
              <div class="journey-chart-header">
                <span class="journey-chart-label">
                  {selectedJourney.symbol}
                  <span class="badge" class:badge-long={selectedJourney.type === 'LONG'} class:badge-short={selectedJourney.type !== 'LONG'}>{selectedJourney.type}</span>
                </span>
                <div class="journey-iv-bar">
                  {#each INTERVALS as iv}
                    <button class="jiv-tab" class:is-on={journeyInterval === iv} onclick={() => changeJourneyInterval(iv)}>{iv.toUpperCase()}</button>
                  {/each}
                </div>
                <button class="journey-close-btn" aria-label="Close journey" onclick={() => { selectedJourney = null; journeyCandles = []; journeyMarks = []; }}>
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
          <div class="journey-list">
            {#each journeys as j (j.id)}
              {@const openMs = Date.parse((j.open_ts || '').replace(' ', 'T'))}
              {@const closeMs = j.close_ts ? Date.parse(j.close_ts.replace(' ', 'T')) : Date.now()}
              {@const dur = isFinite(openMs) && isFinite(closeMs) ? closeMs - openMs : 0}
              <button class="journey-card" class:selected={selectedJourney?.id === j.id} onclick={() => selectJourney(j)}>
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
  /* ── Backdrop ──────────────────────────────────────────────────────── */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 90;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(4px);
    animation: fadeIn 0.2s ease;
  }

  /* ── Container: Desktop ────────────────────────────────────────────── */
  .modal-container {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 95;
    width: 90vw;
    max-width: 720px;
    max-height: 85vh;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: modalSlideUp 0.25s ease-out;
  }
  .modal-container.is-dragging {
    user-select: none;
    cursor: row-resize;
  }

  /* ── Drag handle (mobile only) ─────────────────────────────────────── */
  .drag-handle {
    display: none;
    justify-content: center;
    padding: 8px 0 4px;
    touch-action: none;
    cursor: grab;
    flex-shrink: 0;
  }
  .drag-pill {
    width: 32px;
    height: 4px;
    border-radius: 2px;
    background: var(--border);
  }

  /* ── Header ────────────────────────────────────────────────────────── */
  .modal-header {
    display: flex;
    align-items: center;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    gap: 8px;
    flex-shrink: 0;
  }
  .header-left {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex: 1;
    min-width: 0;
  }
  .header-left h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: -0.01em;
  }
  .close-btn {
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
  .close-btn:hover {
    background: var(--surface-hover);
    color: var(--text);
  }

  /* ── Tabs ───────────────────────────────────────────────────────────── */
  .detail-tabs {
    display: flex;
    gap: 2px;
    background: var(--bg);
    border-radius: 5px;
    padding: 2px;
    flex-shrink: 0;
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
    transition: all 0.15s;
  }
  .tab:hover { color: var(--text); }
  .tab.is-on { color: var(--accent); background: var(--accent-bg); }

  /* ── Body ───────────────────────────────────────────────────────────── */
  .modal-body {
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  /* ── Interval selector ─────────────────────────────────────────────── */
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
    transition: all 0.15s;
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

  /* ── Chart container ───────────────────────────────────────────────── */
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
    transition: background 0.15s;
  }
  .chart-splitter:hover::after,
  .chart-splitter.active::after {
    background: var(--accent);
  }

  /* ── Position KV ───────────────────────────────────────────────────── */
  .kv-section {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-subtle);
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

  /* ── Empty state ───────────────────────────────────────────────────── */
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

  /* ── Feed content ──────────────────────────────────────────────────── */
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
    transition: background 0.15s;
  }
  .feed-item:hover { background: rgba(255,255,255,0.015); }
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

  /* ── Journey ───────────────────────────────────────────────────────── */
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
  .jiv-tab.is-on { color: var(--accent); border-color: var(--accent); background: var(--accent-bg); }
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
  .journey-chart-splitter.active { background: var(--accent-bg, rgba(59,130,246,0.1)); }
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
    transition: background 0.15s;
  }
  .journey-card:hover { background: rgba(255,255,255,0.02); }
  .journey-card.selected { background: rgba(59,130,246,0.08); border-left: 2px solid var(--accent, #3b82f6); }
  .jc-top { display: flex; align-items: center; gap: 6px; }
  .jc-sym { font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 11px; }
  .badge { font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px; text-transform: uppercase; }
  .badge-long { background: rgba(59,130,246,0.2); color: #93c5fd; }
  .badge-short { background: rgba(245,158,11,0.2); color: #fcd34d; }
  .jc-open-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); display: inline-block; }
  .jc-age { font-size: 10px; }
  .jc-dur { font-size: 10px; opacity: 0.7; }
  .jc-pnl { margin-left: auto; font-weight: 600; font-size: 11px; }
  .jc-sub { font-size: 10px; margin-top: 2px; display: flex; gap: 4px; flex-wrap: wrap; }
  .journey-loading, .journey-empty { padding: 16px; text-align: center; color: var(--text-dim); font-size: 12px; }
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

  /* ── Shared utility classes ────────────────────────────────────────── */
  .green { color: var(--green); }
  .red { color: var(--red); }
  .yellow { color: var(--yellow); }
  .dim { color: var(--text-dim); }
  .mono { font-family: 'IBM Plex Mono', monospace; }

  /* ── Animations ────────────────────────────────────────────────────── */
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes modalSlideUp {
    from { opacity: 0; transform: translate(-50%, -48%); }
    to { opacity: 1; transform: translate(-50%, -50%); }
  }
  @keyframes sheetSlideUp {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
  }

  /* ── Mobile: bottom sheet ──────────────────────────────────────────── */
  @media (max-width: 768px) {
    .modal-container {
      top: auto;
      left: 0;
      right: 0;
      bottom: 0;
      transform: none;
      width: 100%;
      max-width: 100%;
      max-height: 95dvh;
      border-radius: var(--radius-lg) var(--radius-lg) 0 0;
      animation: sheetSlideUp 0.3s ease-out;
    }

    .drag-handle {
      display: flex;
    }

    .chart-wrap { height: 200px !important; }
    .chart-splitter { display: none; }

    .modal-header {
      flex-wrap: wrap;
    }
    .detail-tabs {
      order: 3;
      width: 100%;
    }
  }
</style>
