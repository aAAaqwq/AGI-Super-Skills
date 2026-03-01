(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  /* ── Shared chart color palette (matches CSS vars) ── */
  const C = {
    accent: "#3affe7",
    accent2: "#ff4d6d",
    ok: "#4ade80",
    warn: "#ffb703",
    gridLine: "rgba(255,255,255,0.06)",
    gridLabel: "rgba(255,255,255,0.35)",
    crosshair: "rgba(255,255,255,0.18)",
    tooltipBg: "rgba(8,10,18,0.88)",
    tooltipBorder: "rgba(255,255,255,0.12)",
    tooltipText: "rgba(255,255,255,0.90)",
    tooltipMuted: "rgba(255,255,255,0.55)",
    candleUpBody: "rgba(74,222,128,0.30)",
    candleUpEdge: "rgba(74,222,128,0.70)",
    candleUpWick: "rgba(74,222,128,0.40)",
    candleDnBody: "rgba(255,77,109,0.30)",
    candleDnEdge: "rgba(255,77,109,0.70)",
    candleDnWick: "rgba(255,77,109,0.40)",
    volUp: "rgba(74,222,128,0.12)",
    volUpTop: "rgba(74,222,128,0.28)",
    volDn: "rgba(255,77,109,0.12)",
    volDnTop: "rgba(255,77,109,0.28)",
    areaFill: "rgba(58,255,231,0.06)",
    lineGlow: "rgba(58,255,231,0.30)",
    entryLong: "rgba(74,222,128,0.65)",
    entryShort: "rgba(255,77,109,0.65)",
    entryNeutral: "rgba(58,255,231,0.55)",
    avgLong: "rgba(74,222,128,0.85)",
    avgShort: "rgba(255,77,109,0.85)",
    avgNeutral: "rgba(255,255,255,0.55)",
    bgGradTop: "rgba(14,18,30,0.60)",
    bgGradBot: "rgba(10,14,24,0.40)",
  };
  const FONT = "ui-monospace, SFMono-Regular, 'SF Mono', 'Cascadia Code', Menlo, Monaco, monospace";

  const state = {
    mode: "live",
    mobileView: "list",
    paused: false,
    lastSnapshot: null,
    mids: { ok: false, updated_ts_ms: null, mids: {} },
    focus: null,
    focusHist: [],
    focusLastMid: null,
    focusLastTickTs: 0,
    sparkMarks: null,
    sparkHover: null,
    candleHover: null,
    pointer: null,
    marksLastFetchTs: 0,
    marksFor: null,
    chartMode: "ticks",
    tickWindowS: 900,
    candleBars: 72,
    candleInterval: "1h",
    candleIntervals: null,
    candleInd: "rsi",
    candles: [],
    candlesLastFetchTs: 0,
    candlesFor: null,
    candleLiveLastMid: null,
    candleLiveLastUpdateTs: 0,
    midDecsBySym: {},
    lastMidBySym: {},
    midFlashTimers: {},
    search: "",
    feed: "trades",
    auditEvents: [],
    modalOpen: false,
    lastConnOk: null,
    lastConnAt: 0,
    midsStream: null,
    midsStreamConnected: false,
    midsStreamBackoffMs: 1000,
    midsStreamRetryTimer: null,
  };

  /* ── Utilities ── */

  function esc(x) {
    return String(x ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  const fmt = {
    num(n, d = 2) {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "\u2014";
      const x = Number(n);
      return x.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
    },
    int(n) {
      if (n === null || n === undefined || Number.isNaN(Number(n))) return "\u2014";
      return Math.trunc(Number(n)).toLocaleString();
    },
    age(s) {
      if (s === null || s === undefined || Number.isNaN(Number(s))) return "\u2014";
      const x = Number(s);
      if (x < 1) return `${Math.round(x * 1000)}ms`;
      if (x < 60) return `${x.toFixed(1)}s`;
      const m = Math.floor(x / 60);
      const r = Math.floor(x % 60);
      return `${m}m${r}s`;
    },
    ago(s) {
      if (s === null || s === undefined || Number.isNaN(Number(s))) return "\u2014";
      const x = Math.max(0, Math.floor(Number(s)));
      if (x < 45) return "just now";
      if (x < 90) return "1 minute ago";
      const m = Math.floor(x / 60);
      if (m < 60) return `${m} minute${m === 1 ? "" : "s"} ago`;
      const h = Math.floor(m / 60);
      if (h < 24) return `${h} hour${h === 1 ? "" : "s"} ago`;
      const d = Math.floor(h / 24);
      return d <= 1 ? "1 day ago" : `${d} days ago`;
    },
    iso(ts) {
      if (!ts) return "\u2014";
      try { const d = new Date(ts); return d.toISOString().replace("T", " ").slice(0, 19) + "Z"; }
      catch { return String(ts); }
    },
    hmsFromMs(ms) {
      if (!ms) return "\u2014";
      try { return new Date(ms).toISOString().slice(11, 19) + "Z"; } catch { return "\u2014"; }
    },
    hmFromMs(ms) {
      if (!ms) return "\u2014";
      try { return new Date(ms).toISOString().slice(11, 16) + "Z"; } catch { return "\u2014"; }
    },
  };

  function parseTsMs(ts) {
    if (!ts) return null;
    const raw = String(ts).trim();
    if (!raw) return null;
    const norm = (() => {
      let t = raw;
      if (t.includes(" ") && !t.includes("T")) t = t.replace(" ", "T");
      t = t.replace(/\.(\d{3})\d+(?=(Z|[+-]\d{2}:?\d{2})$)/, ".$1");
      if (!/(Z|[+-]\d{2}:?\d{2})$/i.test(t)) t += "Z";
      return t;
    })();
    const ms = Date.parse(norm);
    return Number.isFinite(ms) ? ms : null;
  }

  function whenFromMs(ms) {
    const n = Number(ms);
    if (!Number.isFinite(n)) return null;
    const ageS = Math.max(0, (Date.now() - n) / 1000);
    const iso = new Date(n).toISOString();
    const at = iso.slice(0, 19).replace("T", " ") + "Z";
    return { ts_ms: n, age_s: ageS, at, ago: fmt.ago(ageS) };
  }

  function whenFromIso(ts) {
    const ms = parseTsMs(ts);
    if (!ms) return null;
    return whenFromMs(ms);
  }

  function signalMeta(s) {
    const ts = s?.last_signal?.timestamp;
    const ms = parseTsMs(ts);
    if (!ms) return null;
    const ageS = Math.max(0, (Date.now() - ms) / 1000);
    if (ageS > 24 * 60 * 60) return null;
    const iso = new Date(ms).toISOString();
    const at = iso.slice(0, 19).replace("T", " ") + "Z";
    const isoShort = iso.slice(5, 16).replace("T", " ") + "Z";
    return { ts_ms: ms, age_s: ageS, iso, at, isoShort, hm: fmt.hmFromMs(ms), hms: fmt.hmsFromMs(ms) };
  }

  /* ── Mode / prefs ── */

  const MODE_BUTTONS = [
    { id: "modeLive", mode: "live" },
    { id: "modePaper1", mode: "paper1" },
    { id: "modePaper2", mode: "paper2" },
    { id: "modePaper3", mode: "paper3" },
  ];

  function setSeg(mode) {
    state.mode = mode;
    state.midDecsBySym = {};
    state.lastMidBySym = {};
    state.midFlashTimers = {};
    for (const mb of MODE_BUTTONS) {
      const el = $("#" + mb.id);
      if (!el) continue;
      el.classList.toggle("is-on", mode === mb.mode);
      el.setAttribute("aria-selected", mode === mb.mode ? "true" : "false");
    }
    if (isMobile()) {
      const mv = storageGet(prefKey("mobileView"));
      setMobileView(mv || "list", { persist: false });
    }
    const savedIv = storageGet(prefKey("candleInterval"));
    if (savedIv) setCandleInterval(savedIv, { persist: false });
    else { renderCandleIntervalButtons(state.candleIntervals); renderCandleRangeButtons(); }
    const savedInd = storageGet(prefKey("candleInd"));
    if (savedInd) setCandleInd(savedInd, { persist: false, redraw: false });
    else renderCandleIndButtons();
    updateSparkMeta();
  }

  function setChartMode(mode) {
    const m = (mode || "ticks").toLowerCase();
    const isCandles = m === "candles";
    state.chartMode = isCandles ? "candles" : "ticks";
    state.sparkHover = null;
    state.candleHover = null;
    const bt = $("#chartModeTicks");
    const bc = $("#chartModeCandles");
    if (bt && bc) {
      bt.classList.toggle("is-on", !isCandles);
      bc.classList.toggle("is-on", isCandles);
      bt.setAttribute("aria-selected", !isCandles ? "true" : "false");
      bc.setAttribute("aria-selected", isCandles ? "true" : "false");
    }
    const tr = $("#tickRanges");
    const cr = $("#candleRanges");
    const ci = $("#candleIntervals");
    const cd = $("#candleInd");
    if (tr) tr.classList.toggle("is-hidden", isCandles);
    if (cr) cr.classList.toggle("is-hidden", !isCandles);
    if (ci) ci.classList.toggle("is-hidden", !isCandles);
    if (cd) cd.classList.toggle("is-hidden", !isCandles);
    if (isCandles) { renderCandleIntervalButtons(state.candleIntervals); renderCandleRangeButtons(); renderCandleIndButtons(); }
    $("#sparkSub").textContent = isCandles ? "loading candles\u2026" : "loading ticks\u2026";
    updateSparkMeta();
    if (state.focus) { if (isCandles) fetchCandles(state.focus); else seedSparkline(state.focus); }
    else redraw();
  }

  function setTickWindowS(winS) {
    const w = Number(winS);
    if (!Number.isFinite(w) || w <= 0) return;
    state.tickWindowS = w;
    $$("#tickRanges .segbtn").forEach((b) => b.classList.toggle("is-on", Number(b.dataset.window) === w));
    if (state.chartMode === "ticks" && state.focus) seedSparkline(state.focus);
    updateSparkMeta();
  }

  function setCandleBars(bars) {
    const n = Number(bars);
    if (!Number.isFinite(n) || n < 2) return;
    state.candleBars = Math.max(2, Math.min(2000, Math.trunc(n)));
    $$("#candleRanges .segbtn").forEach((b) => b.classList.toggle("is-on", Number(b.dataset.bars) === state.candleBars));
    if (state.chartMode === "candles" && state.focus) fetchCandles(state.focus);
    updateSparkMeta();
  }

  function storageGet(key) { try { return localStorage.getItem(key); } catch { return null; } }
  function storageSet(key, value) { try { localStorage.setItem(key, value); } catch { /* ignore */ } }
  function prefKey(name) { return `aiq.${name}.${state.mode}`; }

  function isMobile() {
    try { return !!window.matchMedia && window.matchMedia("(max-width: 720px)").matches; }
    catch { return (window.innerWidth || 0) <= 720; }
  }

  function setMobileView(view, { persist = true, focusSearch = false } = {}) {
    const v = String(view || "").trim().toLowerCase() === "focus" ? "focus" : "list";
    state.mobileView = v;
    document.body.dataset.mobileView = v;
    const bl = $("#mnavList");
    const bf = $("#mnavFocus");
    if (bl && bf) {
      bl.classList.toggle("is-on", v === "list");
      bf.classList.toggle("is-on", v === "focus");
      bl.setAttribute("aria-selected", v === "list" ? "true" : "false");
      bf.setAttribute("aria-selected", v === "focus" ? "true" : "false");
    }
    if (persist) storageSet(prefKey("mobileView"), v);
    if (v === "focus") {
      if (!state.focus && state.lastSnapshot && (state.lastSnapshot.symbols || []).length) {
        setFocus(state.lastSnapshot.symbols[0].symbol, { user: false });
      }
      return;
    }
    if (focusSearch) { const se = $("#search"); if (se) se.focus(); }
  }

  /* ── Interval helpers ── */

  function normInterval(iv) { return String(iv || "").trim().toLowerCase(); }

  function normCandleInd(ind) {
    const s = String(ind || "").trim().toLowerCase();
    if (s === "rsi" || s === "macd" || s === "adx" || s === "off") return s;
    return "rsi";
  }

  function renderCandleIntervalButtons(intervals) {
    const el = $("#candleIntervals");
    if (!el) return;
    const list = (intervals || []).map((x) => normInterval(x)).filter((x) => x);
    const uniq = Array.from(new Set(list));
    const base = uniq.length ? uniq : ["1m", "1h"];
    const cur = normInterval(state.candleInterval);
    const out = (cur && !base.includes(cur)) ? [cur, ...base] : base;
    const sig = out.join(",");
    if (el.dataset.sig === sig) {
      $$("#candleIntervals .segbtn").forEach((b) => b.classList.toggle("is-on", b.dataset.interval === state.candleInterval));
      return;
    }
    el.dataset.sig = sig;
    el.innerHTML = "";
    for (const iv of out) {
      const b = document.createElement("button");
      b.className = "segbtn mini";
      b.dataset.interval = iv;
      b.type = "button";
      b.textContent = iv;
      if (iv === state.candleInterval) b.classList.add("is-on");
      el.appendChild(b);
    }
  }

  function parseIntervalToMinutes(iv) {
    const s = normInterval(iv);
    const m = /^([0-9]+)([mhd])$/i.exec(s);
    if (!m) return null;
    const n = Number(m[1]);
    if (!Number.isFinite(n) || n <= 0) return null;
    const unit = String(m[2] || "").toLowerCase();
    if (unit === "m") return n;
    if (unit === "h") return n * 60;
    if (unit === "d") return n * 24 * 60;
    return null;
  }

  function intervalMs(iv) {
    const mins = parseIntervalToMinutes(iv);
    if (!mins) return null;
    return mins * 60_000;
  }

  function syncLiveCandleFromMid(sym, midPx) {
    if (state.chartMode !== "candles") return false;
    if (!state.focus || sym !== state.focus) return false;
    const px = Number(midPx);
    if (!Number.isFinite(px) || px <= 0) return false;
    const msPer = intervalMs(state.candleInterval);
    if (!msPer) return false;
    const nowMs = Date.now();
    const t0 = Math.floor(nowMs / msPer) * msPer;
    const t1 = t0 + msPer;
    const candles = Array.isArray(state.candles) ? state.candles : [];
    const last = candles.length ? candles[candles.length - 1] : null;
    const lastT = last ? Number(last.t || 0) : 0;
    const lastPx = state.candleLiveLastMid;
    if (lastPx !== null && Number(lastPx) === px && lastT === t0 && (nowMs - state.candleLiveLastUpdateTs) < 1200) return false;
    const wantBars = Math.max(2, Math.min(2000, Number(state.candleBars) || 72));
    if (!last || lastT !== t0) {
      const prevClose = last && Number.isFinite(Number(last.c)) ? Number(last.c) : px;
      const o = prevClose;
      const c = px;
      const h = Math.max(o, c);
      const l = Math.min(o, c);
      const live = { t: t0, t_close: t1, o, h, l, c, v: 0, n: 0, updated_at: "live" };
      candles.push(live);
      while (candles.length > wantBars) candles.shift();
      state.candles = candles;
    } else {
      const o = Number.isFinite(Number(last.o)) ? Number(last.o) : px;
      const h0 = Number.isFinite(Number(last.h)) ? Number(last.h) : px;
      const l0 = Number.isFinite(Number(last.l)) ? Number(last.l) : px;
      last.o = o;
      last.c = px;
      last.h = Math.max(h0, px);
      last.l = Math.min(l0, px);
      if (!last.t_close || Number(last.t_close) <= 0) last.t_close = t1;
      last.updated_at = "live";
    }
    state.candleLiveLastMid = px;
    state.candleLiveLastUpdateTs = nowMs;
    return true;
  }

  function candleRangePresetsForInterval(iv) {
    const minsPerBar = parseIntervalToMinutes(iv);
    // Per-interval time-aligned presets: clean labels, bars in [30..240]
    const _m = (label, mins) => ({ label, minutes: mins });
    const presetMap = {
      1:    [_m("30m", 30),    _m("1h", 60),    _m("2h", 120),  _m("3h", 180)],     // 30/60/120/180b
      3:    [_m("2h", 120),    _m("4h", 240),   _m("8h", 480),  _m("12h", 720)],    // 40/80/160/240b
      5:    [_m("4h", 240),    _m("8h", 480),   _m("12h", 720), _m("16h", 960)],    // 48/96/144/192b
      15:   [_m("8h", 480),    _m("12h", 720),  _m("1d", 1440), _m("2d", 2880)],    // 32/48/96/192b
      30:   [_m("1d", 1440),   _m("2d", 2880),  _m("3d", 4320), _m("5d", 7200)],    // 48/96/144/240b
      60:   [_m("2d", 2880),   _m("3d", 4320),  _m("5d", 7200), _m("7d", 10080)],   // 48/72/120/168b
      1440: [_m("30d", 43200), _m("60d", 86400),_m("90d",129600),_m("120d",172800)],
    };
    const presets = minsPerBar ? presetMap[minsPerBar] : null;
    if (presets) {
      return presets.map((t) => ({ ...t, bars: Math.max(2, Math.round(t.minutes / minsPerBar)) }));
    }
    // Fallback: pick 4 clean time labels that yield bars in [30..240]
    if (!minsPerBar) {
      return [
        { label: "2d", minutes: 2880, bars: 48 },
        { label: "3d", minutes: 4320, bars: 72 },
        { label: "5d", minutes: 7200, bars: 120 },
        { label: "7d", minutes: 10080, bars: 168 },
      ];
    }
    const candidates = [_m("30m",30),_m("1h",60),_m("2h",120),_m("4h",240),_m("8h",480),_m("12h",720),_m("1d",1440),_m("2d",2880),_m("3d",4320),_m("5d",7200),_m("7d",10080),_m("14d",20160)];
    const picked = candidates.filter((t) => { const b = Math.round(t.minutes / minsPerBar); return b >= 30 && b <= 240; }).slice(0, 4);
    return picked.length >= 2 ? picked.map((t) => ({ ...t, bars: Math.max(2, Math.round(t.minutes / minsPerBar)) })) : [
      { label: "30b", minutes: 30 * minsPerBar, bars: 30 },
      { label: "60b", minutes: 60 * minsPerBar, bars: 60 },
      { label: "120b", minutes: 120 * minsPerBar, bars: 120 },
      { label: "180b", minutes: 180 * minsPerBar, bars: 180 },
    ];
  }

  /* ── Price formatting ── */

  function pxDecimals(v) {
    const x = Math.abs(Number(v));
    if (!Number.isFinite(x) || x <= 0) return 6;
    if (x >= 1000) return 2;
    if (x >= 100) return 3;
    if (x >= 1) return 4;
    if (x >= 0.01) return 6;
    return 8;
  }

  function fmtPx(v) { return fmt.num(v, pxDecimals(v)); }

  function midDecimalsSticky(sym, mid) {
    const k = String(sym || "").trim().toUpperCase();
    const prev = k ? state.midDecsBySym?.[k] : undefined;
    const n = Number(mid);
    if (!Number.isFinite(n)) return Number.isFinite(prev) ? prev : 6;
    const want = pxDecimals(n);
    const out = Number.isFinite(prev) ? Math.max(prev, want) : want;
    if (k) state.midDecsBySym[k] = Math.max(2, Math.min(10, out));
    return Math.max(2, Math.min(10, out));
  }

  function fmtMidStable(sym, mid) { const d = midDecimalsSticky(sym, mid); return fmt.num(mid, d); }

  function flashMidCell(sym, el, dir) {
    if (!el) return;
    const key = String(sym || "").trim().toUpperCase();
    const timers = state.midFlashTimers || {};
    const prevT = timers[key];
    if (prevT) { clearTimeout(prevT); timers[key] = null; }
    el.classList.remove("flash-up", "flash-down");
    void el.offsetWidth;
    if (dir === "up") el.classList.add("flash-up");
    else if (dir === "down") el.classList.add("flash-down");
    timers[key] = setTimeout(() => { try { el.classList.remove("flash-up", "flash-down"); } catch { /* ignore */ } }, 520);
    state.midFlashTimers = timers;
  }

  function fmtVol(v) {
    const x0 = Number(v);
    if (!Number.isFinite(x0)) return "\u2014";
    const sign = x0 < 0 ? "-" : "";
    const x = Math.abs(x0);
    if (x >= 1e12) return sign + (x / 1e12).toFixed(2) + "t";
    if (x >= 1e9) return sign + (x / 1e9).toFixed(2) + "b";
    if (x >= 1e6) return sign + (x / 1e6).toFixed(2) + "m";
    if (x >= 1e3) return sign + (x / 1e3).toFixed(1) + "k";
    if (x >= 1) return sign + x.toFixed(0);
    if (x >= 0.01) return sign + x.toFixed(2);
    if (x === 0) return "0";
    return sign + x.toExponential(2);
  }

  /* ── Client-side indicators ── */

  function calcEMA(values, period) {
    const n = Array.isArray(values) ? values.length : 0;
    const p = Math.max(1, Math.trunc(Number(period) || 1));
    const out = new Array(n).fill(null);
    if (n <= 0) return out;
    const k = 2 / (p + 1);
    let ema = Number(values[0]);
    if (!Number.isFinite(ema)) return out;
    out[0] = ema;
    for (let i = 1; i < n; i++) {
      const v = Number(values[i]);
      if (!Number.isFinite(v)) { out[i] = null; continue; }
      ema = ema + k * (v - ema);
      out[i] = ema;
    }
    return out;
  }

  function calcRSI(closes, period = 14) {
    const n = Array.isArray(closes) ? closes.length : 0;
    const p = Math.max(2, Math.trunc(Number(period) || 14));
    const out = new Array(n).fill(null);
    if (n < p + 1) return out;
    let gain = 0, loss = 0;
    for (let i = 1; i <= p; i++) {
      const d = Number(closes[i]) - Number(closes[i - 1]);
      if (!Number.isFinite(d)) continue;
      if (d >= 0) gain += d; else loss -= d;
    }
    let avgGain = gain / p;
    let avgLoss = loss / p;
    out[p] = avgLoss === 0 ? 100 : (100 - (100 / (1 + (avgGain / avgLoss))));
    for (let i = p + 1; i < n; i++) {
      const d = Number(closes[i]) - Number(closes[i - 1]);
      if (!Number.isFinite(d)) { out[i] = null; continue; }
      const g = d > 0 ? d : 0;
      const l = d < 0 ? -d : 0;
      avgGain = ((avgGain * (p - 1)) + g) / p;
      avgLoss = ((avgLoss * (p - 1)) + l) / p;
      out[i] = avgLoss === 0 ? 100 : (100 - (100 / (1 + (avgGain / avgLoss))));
    }
    return out;
  }

  function calcMACD(closes, fast = 12, slow = 26, signal = 9) {
    const n = Array.isArray(closes) ? closes.length : 0;
    const f = Math.max(2, Math.trunc(Number(fast) || 12));
    const s = Math.max(f + 1, Math.trunc(Number(slow) || 26));
    const g = Math.max(2, Math.trunc(Number(signal) || 9));
    const emaFast = calcEMA(closes, f);
    const emaSlow = calcEMA(closes, s);
    const macd = new Array(n).fill(null);
    for (let i = 0; i < n; i++) {
      const a = emaFast[i]; const b = emaSlow[i];
      macd[i] = (a === null || b === null) ? null : (Number(a) - Number(b));
    }
    const sig = calcEMA(macd.map((v) => (v === null ? 0 : v)), g);
    const hist = new Array(n).fill(null);
    for (let i = 0; i < n; i++) {
      const m = macd[i]; const si = sig[i];
      hist[i] = (m === null || si === null) ? null : (Number(m) - Number(si));
    }
    return { macd, signal: sig, hist, params: { fast: f, slow: s, signal: g } };
  }

  function calcADX(candles, period = 14) {
    const n = Array.isArray(candles) ? candles.length : 0;
    const p = Math.max(2, Math.trunc(Number(period) || 14));
    const out = new Array(n).fill(null);
    if (n < (2 * p)) return out;
    const tr = new Array(n).fill(0);
    const pdm = new Array(n).fill(0);
    const ndm = new Array(n).fill(0);
    for (let i = 1; i < n; i++) {
      const cur = candles[i]; const prev = candles[i - 1];
      const h = Number(cur?.h); const l = Number(cur?.l);
      const ph = Number(prev?.h); const pl = Number(prev?.l); const pc = Number(prev?.c);
      if (![h, l, ph, pl, pc].every((x) => Number.isFinite(x))) continue;
      const up = h - ph; const dn = pl - l;
      pdm[i] = (up > dn && up > 0) ? up : 0;
      ndm[i] = (dn > up && dn > 0) ? dn : 0;
      const r1 = h - l; const r2 = Math.abs(h - pc); const r3 = Math.abs(l - pc);
      tr[i] = Math.max(r1, r2, r3);
    }
    let trS = 0, pS = 0, nS = 0;
    for (let i = 1; i <= p; i++) { trS += tr[i] || 0; pS += pdm[i] || 0; nS += ndm[i] || 0; }
    const dx = new Array(n).fill(null);
    for (let i = p; i < n; i++) {
      if (i > p) { trS = trS - (trS / p) + (tr[i] || 0); pS = pS - (pS / p) + (pdm[i] || 0); nS = nS - (nS / p) + (ndm[i] || 0); }
      if (!Number.isFinite(trS) || trS <= 0) { dx[i] = 0; continue; }
      const pdi = 100 * (pS / trS); const ndi = 100 * (nS / trS);
      const den = pdi + ndi;
      dx[i] = den <= 0 ? 0 : (100 * (Math.abs(pdi - ndi) / den));
    }
    let sumDx = 0;
    for (let i = p; i <= (2 * p - 1); i++) sumDx += Number(dx[i] || 0);
    let adx = sumDx / p;
    out[2 * p - 1] = adx;
    for (let i = 2 * p; i < n; i++) { const d = Number(dx[i] || 0); adx = ((adx * (p - 1)) + d) / p; out[i] = adx; }
    return out;
  }

  function hmLabelFromMs(ms) {
    try { return new Date(Number(ms)).toISOString().slice(11, 16); } catch { return "\u2014"; }
  }

  /* ── Candle UI buttons ── */

  function renderCandleRangeButtons() {
    const el = $("#candleRanges");
    if (!el) return;
    const presets = candleRangePresetsForInterval(state.candleInterval);
    const sig = `${normInterval(state.candleInterval)}:${presets.map((p) => `${p.label}:${p.bars}`).join(",")}`;
    if (el.dataset.sig === sig) {
      $$("#candleRanges .segbtn").forEach((b) => b.classList.toggle("is-on", Number(b.dataset.bars) === state.candleBars));
      return;
    }
    el.dataset.sig = sig;
    el.innerHTML = "";
    for (const p of presets) {
      const b = document.createElement("button");
      b.className = "segbtn mini";
      b.dataset.bars = String(p.bars);
      b.type = "button";
      b.textContent = p.label;
      b.title = `${p.label} (${p.bars} bars @ ${state.candleInterval})`;
      if (p.bars === state.candleBars) b.classList.add("is-on");
      el.appendChild(b);
    }
  }

  function renderCandleIndButtons() {
    const el = $("#candleInd");
    if (!el) return;
    const items = [
      { ind: "rsi", label: "RSI", title: "RSI (14)" },
      { ind: "macd", label: "MACD", title: "MACD (12/26/9)" },
      { ind: "adx", label: "ADX", title: "ADX (14)" },
      { ind: "off", label: "OFF", title: "Hide indicators" },
    ];
    const sig = items.map((i) => i.ind).join(",");
    if (el.dataset.sig === sig) {
      $$("#candleInd .segbtn").forEach((b) => b.classList.toggle("is-on", b.dataset.ind === state.candleInd));
      return;
    }
    el.dataset.sig = sig;
    el.innerHTML = "";
    for (const it of items) {
      const b = document.createElement("button");
      b.className = "segbtn mini";
      b.dataset.ind = it.ind;
      b.type = "button";
      b.textContent = it.label;
      if (it.title) b.title = it.title;
      if (it.ind === state.candleInd) b.classList.add("is-on");
      el.appendChild(b);
    }
  }

  function setCandleInd(ind, { persist = true, redraw: doRedraw = true } = {}) {
    const v = normCandleInd(ind);
    state.candleInd = v;
    if (persist) storageSet(prefKey("candleInd"), v);
    renderCandleIndButtons();
    updateSparkMeta();
    if (doRedraw) redraw();
  }

  function setCandleInterval(interval, { persist = true } = {}) {
    const iv = normInterval(interval);
    if (!iv) return;
    const prev = state.candleInterval;
    state.candleInterval = iv;
    state.candleHover = null;
    if (persist) storageSet(prefKey("candleInterval"), iv);
    renderCandleIntervalButtons(state.candleIntervals);
    renderCandleRangeButtons();
    const presets = candleRangePresetsForInterval(iv);
    const validBars = new Set(presets.map((p) => Number(p.bars)));
    const wantDefaultBars = presets[2]?.bars ?? presets[0]?.bars ?? state.candleBars;
    const desiredBars = validBars.has(Number(state.candleBars)) ? state.candleBars : wantDefaultBars;
    if (Number(desiredBars) !== Number(state.candleBars)) { setCandleBars(desiredBars); return; }
    updateSparkMeta();
    if (prev !== iv && state.chartMode === "candles" && state.focus) fetchCandles(state.focus);
  }

  /* ── Network ── */

  async function fetchJson(url, timeoutMs = 2500) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const r = await fetch(url, { signal: ctrl.signal, cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } finally { clearTimeout(t); }
  }

  function updateConn(ok, label) {
    const dot = $("#connDot");
    const txt = $("#connTxt");
    dot.classList.toggle("ok", !!ok);
    dot.classList.toggle("bad", ok === false);
    txt.textContent = label;
  }

  /* ── Badge helpers ── */

  function badgeDecision(s) {
    const sm = signalMeta(s);
    if (!sm) return { cls: "sig-neutral", txt: "\u2014" };
    const sig = s?.last_signal?.signal;
    const conf = s?.last_signal?.confidence;
    if (!sig) return { cls: "sig-neutral", txt: "\u2014" };
    const up = String(sig).toUpperCase();
    if (up === "BUY") return { cls: "sig-buy", txt: conf ? `BUY \u00b7 ${conf}` : "BUY" };
    if (up === "SELL") return { cls: "sig-sell", txt: conf ? `SELL \u00b7 ${conf}` : "SELL" };
    return { cls: "sig-neutral", txt: conf ? `${up} \u00b7 ${conf}` : up };
  }

  function badgePos(s) {
    const p = s?.position;
    if (!p) return { txt: "flat", cls: "pos-flat" };
    const t = p.type || "\u2014";
    const sz = p.size;
    const upnl = p.unreal_pnl_est;
    const tag = upnl === null || upnl === undefined ? "" : (upnl >= 0 ? ` +${fmt.num(upnl, 2)}` : ` ${fmt.num(upnl, 2)}`);
    return { txt: `${t} ${fmt.num(sz, 4)}${tag}`, cls: upnl >= 0 ? "sig-buy" : "sig-sell" };
  }

  /* ── Universe table ── */

  function renderTable(symbols) {
    const body = $("#symBody");
    body.innerHTML = "";
    const q = state.search.trim().toUpperCase();
    const list = (symbols || []).filter((s) => { if (!q) return true; return String(s.symbol).includes(q); });
    for (const s of list) {
      const tr = document.createElement("tr");
      tr.dataset.sym = s.symbol;
      tr.tabIndex = 0;
      tr.setAttribute("role", "button");
      tr.setAttribute("aria-label", `Focus ${s.symbol}`);
      if (state.focus === s.symbol) tr.classList.add("is-focus");
      const dec = badgeDecision(s);
      const pos = badgePos(s);
      const sm = signalMeta(s);
      const sigWhen = sm ? `${fmt.ago(sm.age_s)}` : "\u2014";
      const sigWhenTitle = sm ? `${sm.at}` : "";
      const age = s.mid_age_s;
      const stale = typeof age === "number" && age > 15;
      if (stale) tr.classList.add("row-stale");
      if (dec.cls === "sig-buy") tr.classList.add("row-sig-buy");
      if (dec.cls === "sig-sell") tr.classList.add("row-sig-sell");
      const pt = String(s?.position?.type || "").toUpperCase();
      if (pt === "LONG") tr.classList.add("row-long");
      if (pt === "SHORT") tr.classList.add("row-short");
      const ageTitle = typeof age === "number" ? `Age: ${fmt.age(age)}` : "";
      tr.innerHTML = `
        <td data-label="SYM">
          <span class="badge ${stale ? "stale" : ""}" title="${esc(ageTitle)}">${esc(s.symbol)}</span>
        </td>
        <td data-label="MID" class="num" title="${esc(ageTitle)}">${s.mid !== null && s.mid !== undefined ? (isMobile() ? fmtMidStable(s.symbol, s.mid) : fmt.num(s.mid, 6)) : "\u2014"}</td>
        <td data-label="SIGNAL">
          <div class="cellcol">
            <span class="badge ${dec.cls}">${esc(dec.txt)}</span>
            <span class="tiny" title="${esc(sigWhenTitle)}">${esc(sigWhen)}</span>
          </div>
        </td>
        <td data-label="POS"><span class="badge ${pos.cls}">${esc(pos.txt)}</span></td>
      `;
      tr.addEventListener("click", () => setFocus(s.symbol, { user: true }));
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFocus(s.symbol, { user: true }); } });
      body.appendChild(tr);
      const px = Number(s.mid);
      if (Number.isFinite(px)) state.lastMidBySym[String(s.symbol || "").trim().toUpperCase()] = px;
    }
    $("#symCount").textContent = `${fmt.int(list.length)} symbols`;
  }

  /* ── Modal ── */

  function pretty(obj) {
    if (!obj) return "\u2014";
    try { return JSON.stringify(obj, null, 2); } catch { return String(obj); }
  }

  function openModal({ title = "\u2014", meta = "", body = "\u2014" } = {}) {
    const root = $("#modal");
    if (!root) return;
    $("#modalTitle").textContent = String(title || "\u2014");
    $("#modalMeta").textContent = String(meta || "");
    $("#modalBody").textContent = String(body || "\u2014");
    root.classList.remove("is-hidden");
    root.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    state.modalOpen = true;
    const c = $("#modalClose");
    if (c) c.focus();
  }

  function closeModal() {
    const root = $("#modal");
    if (!root) return false;
    if (root.classList.contains("is-hidden")) return false;
    root.classList.add("is-hidden");
    root.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    state.modalOpen = false;
    return true;
  }

  function auditBodyText(a) {
    if (!a) return "\u2014";
    const raw = a.data_json ?? a.data ?? null;
    if (raw === null || raw === undefined || raw === "") return pretty(a);
    if (typeof raw !== "string") return pretty(raw);
    const s = String(raw);
    const t = s.trim();
    if (t.startsWith("{") || t.startsWith("[")) {
      try { return JSON.stringify(JSON.parse(t), null, 2); } catch { /* ignore */ }
    }
    return s;
  }

  function openAuditModal(a) {
    if (!a) return;
    const title = `${a.event || "\u2014"} \u00b7 ${a.symbol || "\u2014"}`;
    const ts = a.timestamp ? fmt.iso(a.timestamp) : "\u2014";
    const lvl = a.level || "info";
    openModal({ title, meta: `${ts} \u00b7 ${lvl}`, body: auditBodyText(a) });
  }

  /* ── Focus detail ── */

  function setFocus(sym, { user = false } = {}) {
    state.focus = sym;
    state.focusHist = [];
    state.focusLastMid = null;
    state.focusLastTickTs = 0;
    state.sparkMarks = null;
    state.sparkHover = null;
    state.candleHover = null;
    state.marksLastFetchTs = 0;
    state.marksFor = null;
    state.candles = [];
    state.candlesLastFetchTs = 0;
    state.candlesFor = null;
    state.candleLiveLastMid = null;
    state.candleLiveLastUpdateTs = 0;
    $("#detailTitle").textContent = `Focus \u00b7 ${sym}`;
    $("#sparkTag").textContent = sym;
    $("#sparkSub").textContent = state.chartMode === "candles" ? "loading candles\u2026" : "loading ticks\u2026";
    $("#sparkMeta").textContent = state.chartMode === "candles" ? `candles \u00b7 ${state.candleInterval} \u00b7 ${state.candleBars} bars` : `ticks \u00b7 ${Math.round(state.tickWindowS / 60)}m`;
    $$("#symBody tr").forEach((tr) => tr.classList.toggle("is-focus", tr.dataset.sym === sym));
    if (user && isMobile()) { const se = $("#search"); if (se) se.blur(); setMobileView("focus"); }
    if (!state.paused) hydrateFocusFromSnapshot();
    if (state.chartMode === "candles") fetchCandles(sym); else seedSparkline(sym);
    fetchMarks(sym);
  }

  function kvRow(k, v, cls = "", title = "") {
    const titleAttr = title ? ` title="${esc(title)}"` : "";
    return `<div class="kvrow"><div class="k">${esc(k)}</div><div class="v ${cls}"${titleAttr}>${esc(v)}</div></div>`;
  }

  function kvSec(title) { return `<div class="sec">${esc(title)}</div>`; }
  function toNum(x) { if (x === null || x === undefined) return null; const n = Number(x); return Number.isFinite(n) ? n : null; }

  function currentPosAndEntries() {
    const mk = state.sparkMarks || null;
    const entries = (mk && Array.isArray(mk.entries)) ? mk.entries : [];
    let pos = mk && mk.position ? mk.position : null;
    if (!pos && state.lastSnapshot && state.focus) {
      const s = (state.lastSnapshot.symbols || []).find((x) => x.symbol === state.focus) || null;
      pos = s?.position || null;
    }
    return { pos, entries };
  }

  function buildEntryLines(pos, entries) {
    const lines = [];
    const avgPx = pos?.entry_price !== null && pos?.entry_price !== undefined ? Number(pos.entry_price) : null;
    if (avgPx !== null && Number.isFinite(avgPx)) {
      lines.push({ action: "AVG", price: avgPx, timestamp: pos?.open_timestamp || null, size: pos?.size ?? null, trade_id: pos?.open_trade_id ?? null, is_avg: true });
    }
    for (const e of (entries || [])) {
      const px = e?.price !== null && e?.price !== undefined ? Number(e.price) : null;
      if (px === null || !Number.isFinite(px)) continue;
      lines.push({ action: String(e.action || "ENTRY").toUpperCase(), price: px, timestamp: e.timestamp || null, size: e.size ?? null, trade_id: e.id ?? null, is_avg: false });
    }
    return lines;
  }

  function entryLineText(line) {
    if (!line) return null;
    const px = fmt.num(line.price, 6);
    const sz = toNum(line.size);
    const szTxt = sz === null ? "" : ` ${fmt.num(sz, 4)}`;
    const base = line.action === "AVG" ? `AVG${szTxt} ${px}` : `${line.action}${szTxt} @ ${px}`;
    const w = line.timestamp ? whenFromIso(line.timestamp) : null;
    return w ? `${base} \u00b7 ${w.ago}` : base;
  }

  function renderPosKv(p) {
    if (!p) return "\u2014";
    const upnl = toNum(p.unreal_pnl_est);
    const upnlCls = upnl === null ? "" : (upnl >= 0 ? "hi" : "bad");
    const rows = [];
    rows.push(kvRow("type", p.type || "\u2014"));
    rows.push(kvRow("size", fmt.num(p.size, 6)));
    rows.push(kvRow("entry", fmt.num(p.entry_price, 6)));
    rows.push(kvRow("uPnL", upnl === null ? "\u2014" : fmt.num(upnl, 2), upnlCls));
    rows.push(kvRow("lev", p.leverage === null || p.leverage === undefined ? "\u2014" : `${fmt.num(p.leverage, 1)}x`));
    rows.push(kvRow("margin", p.margin_used === null || p.margin_used === undefined ? "\u2014" : fmt.num(p.margin_used, 2)));
    if (p.confidence) rows.push(kvRow("confidence", p.confidence));
    if (p.open_timestamp) { const w = whenFromIso(p.open_timestamp); rows.push(kvRow("opened", w ? w.ago : p.open_timestamp, "", w ? w.at : "")); }
    if (p.open_trade_id !== null && p.open_trade_id !== undefined) rows.push(kvRow("trade_id", String(p.open_trade_id)));
    if (p.entry_atr !== null && p.entry_atr !== undefined) rows.push(kvRow("ATR", fmt.num(p.entry_atr, 6)));
    return rows.join("");
  }

  function renderDecKv(s) {
    if (!s) return "\u2014";
    const parts = [];
    const sig = s.last_signal || null;
    const intent = s.last_intent || null;
    const tr = s.last_trade || null;
    if (sig) {
      parts.push(kvSec("Signal"));
      parts.push(kvRow("signal", sig.signal || "\u2014"));
      if (sig.confidence) parts.push(kvRow("confidence", sig.confidence));
      if (sig.price !== null && sig.price !== undefined) parts.push(kvRow("price", fmt.num(sig.price, 6)));
      if (sig.timestamp) { const w = whenFromIso(sig.timestamp); parts.push(kvRow("time", w ? w.ago : sig.timestamp, "", w ? w.at : "")); }
    }
    if (intent) {
      parts.push(kvSec("OMS intent"));
      if (intent.status) parts.push(kvRow("status", intent.status));
      if (intent.action) parts.push(kvRow("action", intent.action));
      if (intent.side) parts.push(kvRow("side", intent.side));
      if (intent.reason) parts.push(kvRow("reason", intent.reason, "wrap"));
      if (intent.dedupe_key) parts.push(kvRow("dedupe", intent.dedupe_key, "wrap"));
      if (intent.created_ts_ms) { const w = whenFromMs(intent.created_ts_ms); parts.push(kvRow("time", w ? w.ago : new Date(intent.created_ts_ms).toISOString(), "", w ? w.at : "")); }
    }
    if (tr) {
      parts.push(kvSec("Last trade"));
      if (tr.action) parts.push(kvRow("action", tr.action));
      if (tr.type) parts.push(kvRow("type", tr.type));
      if (tr.price !== null && tr.price !== undefined) parts.push(kvRow("price", fmt.num(tr.price, 6)));
      if (tr.size !== null && tr.size !== undefined) parts.push(kvRow("size", fmt.num(tr.size, 6)));
      const pnl = toNum(tr.pnl);
      const pnlCls = pnl === null ? "" : (pnl >= 0 ? "hi" : "bad");
      if (tr.pnl !== null && tr.pnl !== undefined) parts.push(kvRow("PnL", fmt.num(tr.pnl, 2), pnlCls));
      if (tr.reason) parts.push(kvRow("reason", tr.reason, "wrap"));
      if (tr.timestamp) { const w = whenFromIso(tr.timestamp); parts.push(kvRow("time", w ? w.ago : tr.timestamp, "", w ? w.at : "")); }
    }
    return parts.length ? parts.join("") : "\u2014";
  }

  function hydrateFocusFromSnapshot() {
    const snap = state.lastSnapshot;
    if (!snap) return;
    const s = (snap.symbols || []).find((x) => x.symbol === state.focus) || null;
    if (!s) {
      $("#detailMid").textContent = "\u2014";
      $("#detailSig").textContent = "\u2014";
      $("#posSummary").textContent = "\u2014";
      $("#posKv").textContent = "\u2014";
      $("#posJson").textContent = "\u2014";
      $("#decSummary").textContent = "\u2014";
      $("#decKv").textContent = "\u2014";
      $("#decJson").textContent = "\u2014";
      return;
    }
    $("#detailMid").textContent = s.mid !== null && s.mid !== undefined ? `MID ${fmt.num(s.mid, 6)} (${fmt.age(s.mid_age_s)})` : "MID \u2014";
    const dec = badgeDecision(s);
    const sm = signalMeta(s);
    const sigSuffix = sm ? ` \u00b7 ${fmt.ago(sm.age_s)}` : "";
    $("#detailSig").textContent = `Signal ${dec.txt}${sigSuffix}`;
    $("#detailSig").title = sm ? `${sm.at}\nSaved strategy signal (not an order)` : "Saved strategy signal (not an order)";
    const opened = s.position?.open_timestamp ? whenFromIso(s.position.open_timestamp) : null;
    const openedSuffix = opened ? ` \u00b7 opened ${opened.ago}` : "";
    $("#posSummary").textContent = s.position ? `${s.position.type} \u00b7 size ${fmt.num(s.position.size, 4)} \u00b7 entry ${fmt.num(s.position.entry_price, 6)}${openedSuffix}` : "flat";
    $("#posSummary").title = opened ? opened.at : "";
    $("#posKv").innerHTML = renderPosKv(s.position);
    $("#posJson").textContent = pretty(s.position);
    const intent = s.last_intent;
    const lastTrade = s.last_trade;
    const decObj = { last_signal: sm ? s.last_signal : null, last_intent: intent, last_trade: lastTrade };
    const bits = [];
    if (intent?.status) bits.push(`OMS ${intent.status}`);
    if (lastTrade?.action) bits.push(`trade ${lastTrade.action}`);
    $("#decSummary").textContent = bits.length ? bits.join(" \u00b7 ") : "\u2014";
    $("#decKv").innerHTML = renderDecKv(decObj);
    $("#decJson").textContent = pretty(decObj);
  }

  /* ── Activity feed ── */

  function setFeed(name) {
    state.feed = name;
    $$(".tab").forEach((b) => b.classList.toggle("is-on", b.dataset.feed === name));
    $("#feedTrades").classList.toggle("is-hidden", name !== "trades");
    $("#feedOms").classList.toggle("is-hidden", name !== "oms");
    $("#feedAudit").classList.toggle("is-hidden", name !== "audit");
  }

  function renderFeeds(snap) {
    const rec = snap?.recent || {};
    const trades = rec.trades || [];
    $("#feedTrades").innerHTML = trades.slice(0, 40).map((t) => {
      const pnl = t.pnl;
      const pnlCls = pnl === null || pnl === undefined ? "" : (pnl >= 0 ? "hi" : "bad");
      return `<div class="item"><div class="row"><div class="l">${t.symbol} \u00b7 ${t.action} ${t.type}</div><div class="r">${fmt.iso(t.timestamp)}</div></div><div class="sub">px <span class="hi">${fmt.num(t.price, 6)}</span> \u00b7 size ${fmt.num(t.size, 6)} \u00b7 notional ${fmt.num(t.notional, 2)} \u00b7 pnl <span class="${pnlCls}">${pnl === null || pnl === undefined ? "\u2014" : fmt.num(pnl, 2)}</span></div><div class="sub">${t.reason ? `reason: ${t.reason}` : ""}</div></div>`;
    }).join("");
    const intents = rec.oms_intents || [];
    const fills = rec.oms_fills || [];
    const recos = rec.oms_reconcile_events || [];
    const htmlOms = [];
    for (const i of intents.slice(0, 25)) {
      htmlOms.push(`<div class="item"><div class="row"><div class="l">${i.symbol} \u00b7 ${i.action} ${i.side} \u00b7 <span class="${i.status === "FILLED" ? "hi" : (i.status === "REJECTED" ? "bad" : "warn")}">${i.status}</span></div><div class="r">${new Date(i.created_ts_ms).toISOString().slice(11,19)}Z</div></div><div class="sub">reason: ${i.reason || "\u2014"} \u00b7 conf: ${i.confidence || "\u2014"}</div><div class="sub">dedupe: ${i.dedupe_key || "\u2014"}</div></div>`);
    }
    for (const f of fills.slice(0, 15)) {
      const pnl = f.pnl_usd;
      const pnlCls = pnl === null || pnl === undefined ? "" : (pnl >= 0 ? "hi" : "bad");
      htmlOms.push(`<div class="item"><div class="row"><div class="l">FILL \u00b7 ${f.symbol} \u00b7 ${f.side} ${fmt.num(f.size, 6)}</div><div class="r">${new Date(f.ts_ms).toISOString().slice(11,19)}Z</div></div><div class="sub">px <span class="hi">${fmt.num(f.price, 6)}</span> \u00b7 notional ${fmt.num(f.notional, 2)} \u00b7 pnl <span class="${pnlCls}">${pnl === null || pnl === undefined ? "\u2014" : fmt.num(pnl, 2)}</span></div><div class="sub">matched: ${f.matched_via || "\u2014"} \u00b7 intent: ${f.intent_id || "\u2014"}</div></div>`);
    }
    for (const e of recos.slice(0, 10)) {
      htmlOms.push(`<div class="item"><div class="row"><div class="l">RECON \u00b7 ${e.kind || "\u2014"} \u00b7 ${e.symbol || "\u2014"}</div><div class="r">${new Date(e.ts_ms).toISOString().slice(11,19)}Z</div></div><div class="sub">${e.result || "\u2014"}</div></div>`);
    }
    $("#feedOms").innerHTML = htmlOms.length ? htmlOms.join("") : `<div class="item"><div class="sub">No OMS activity.</div></div>`;
    const audits = rec.audit_events || [];
    const showAudits = audits.slice(0, 40);
    state.auditEvents = showAudits;
    $("#feedAudit").innerHTML = showAudits.map((a, idx) => `<button type="button" class="itembtn auditbtn" data-audit-idx="${idx}" aria-label="Open audit detail"><div class="row"><div class="l">${esc(`${a.event || "\u2014"} \u00b7 ${a.symbol || "\u2014"}`)}</div><div class="r">${esc(fmt.iso(a.timestamp))}</div></div><div class="sub">${esc(a.level || "info")}</div></button>`).join("");
  }

  function renderHealth(snap) {
    const h = snap?.health || {};
    $("#openCount").textContent = `open ${fmt.int(h.open_pos ?? snap?.open_positions?.length ?? 0)}`;
    const hbAgeS = (h && h.ts_ms && snap?.now_ts_ms) ? Math.max(0, (Number(snap.now_ts_ms) - Number(h.ts_ms)) / 1000) : null;
    const ws = snap?.ws || {};
    const wsAgeS = (ws && ws.updated_ts_ms && snap?.now_ts_ms) ? Math.max(0, (Number(snap.now_ts_ms) - Number(ws.updated_ts_ms)) / 1000) : null;
    const hbTxt = h.ok ? (hbAgeS === null ? "hb ok" : `hb ${fmt.age(hbAgeS)}`) : "hb missing";
    const wsTxt = wsAgeS === null ? "data \u2014" : `data ${fmt.age(wsAgeS)}`;
    $("#hbAge").textContent = `${hbTxt} \u00b7 ${wsTxt}`;
    const loopS = h.loop_s ?? h.wall_s;
    $("#loopWall").textContent = h.ok ? `loop ${fmt.num(loopS, 2)}s` : "loop \u2014";
    $("#wsRestarts").textContent = h.ok ? `wsR ${fmt.int(h.ws_restarts)}` : "wsR \u2014";
    $("#errs").textContent = h.ok ? `err ${fmt.int(h.errors)}` : "err \u2014";

    // Risk state (PAUSED when kill_mode is active).
    const km = String(h.kill_mode || "off").toLowerCase();
    const kr = String(h.kill_reason || "").trim();
    const statePill = $("#statePill");
    const stateDot = $("#stateDot");
    const stateTxt = $("#stateTxt");
    if (statePill && stateDot && stateTxt) {
      stateDot.classList.remove("ok", "bad", "warn");
      statePill.classList.remove("paused", "running");
      if (!h.ok) {
        stateDot.classList.add("warn");
        stateTxt.textContent = "no hb";
        statePill.title = "Heartbeat missing; state unknown";
      } else {
        const paused = (km === "close_only" || km === "halt_all");
        statePill.classList.toggle("paused", paused);
        statePill.classList.toggle("running", !paused);
        stateDot.classList.toggle("bad", paused);
        stateDot.classList.toggle("ok", !paused);
        const label = paused ? (km === "halt_all" ? "HALT" : "PAUSED") : "RUNNING";
        stateTxt.textContent = label.toLowerCase();
        statePill.title = paused ? `PAUSED: ${km}${kr ? ` (${kr})` : ""}` : "Running";
      }
    }

    // Regime gate (trend OK vs chop).
    const rgOn = (typeof h.regime_gate === "boolean") ? h.regime_gate : null;
    const rgReason = String(h.regime_reason || "").trim();
    const rgPill = $("#regimePill");
    const rgDot = $("#regimeDot");
    const rgTxt = $("#regimeTxt");
    if (rgPill && rgDot && rgTxt) {
      rgDot.classList.remove("ok", "bad", "warn");
      rgPill.classList.remove("paused", "running");
      if (!h.ok) {
        rgDot.classList.add("warn");
        rgTxt.textContent = "gate";
        rgPill.title = "Heartbeat missing; regime gate unknown";
      } else if (rgOn === null) {
        rgDot.classList.add("warn");
        rgTxt.textContent = "gate —";
        rgPill.title = "Regime gate not reported by engine";
      } else {
        rgPill.classList.toggle("running", rgOn);
        rgPill.classList.toggle("paused", !rgOn);
        rgDot.classList.toggle("ok", rgOn);
        rgDot.classList.toggle("bad", !rgOn);
        rgTxt.textContent = rgOn ? "gate on" : "gate off";
        rgPill.title = rgOn ? `Regime gate ON (${rgReason || "trend_ok"})` : `Regime gate OFF (${rgReason || "n/a"})`;
      }
    }

    // Config ID (from engine heartbeat).
    const cfg = String(h.config_id || "").trim();
    const cfgShort = cfg ? cfg.slice(0, 12) : "\u2014";
    const cfgEl = $("#cfgId");
    const cfgPill = $("#cfgPill");
    if (cfgEl) cfgEl.textContent = cfgShort;
    if (cfgPill) cfgPill.title = cfg ? `config_id: ${cfg}` : "config_id unavailable";

    // Today's PnL + drawdown (UTC day).
    const d = snap?.daily || {};
    const pnl = d.pnl_usd;
    const dd = d.drawdown_pct;
    const pnlEl = $("#pnlToday");
    const ddEl = $("#ddNow");
    if (pnlEl) pnlEl.textContent = (pnl === null || pnl === undefined || Number.isNaN(Number(pnl))) ? "\u2014" : `$${fmt.num(pnl, 2)}`;
    if (ddEl) ddEl.textContent = (dd === null || dd === undefined || Number.isNaN(Number(dd))) ? "\u2014" : `${fmt.num(dd, 1)}%`;

    // Last data timestamp (WS mids).
    const dataTs = ws?.updated_ts_ms ? Number(ws.updated_ts_ms) : null;
    const dataEl = $("#dataTs");
    const dataPill = $("#dataPill");
    if (dataEl) dataEl.textContent = dataTs ? fmt.hmsFromMs(dataTs) : "\u2014";
    if (dataPill) dataPill.title = dataTs ? `Last WS mids update: ${fmt.iso(dataTs)} (${fmt.ago(wsAgeS)})` : "WS mids timestamp unavailable";

    const mode = snap?.mode || state.mode;
    const b = snap?.balances || {};
    const src = b.balance_source || (mode === "live" ? "unknown" : "paper");
    const realised = b.realised_usd;
    const equity = b.equity_est_usd;
    const unreal = b.unreal_pnl_est_usd;
    const fees = b.est_close_fees_usd;
    const marginUsedEst = b.margin_used_est_usd;
    const marginUsedHl = b.total_margin_used_usd;
    const fr = b.fee_rate;
    const acct = b.account_value_usd;
    const realEl = $("#balReal");
    const eqEl = $("#balEq");
    if (realEl) realEl.textContent = realised === null || realised === undefined ? "\u2014" : `$${fmt.num(realised, 2)}`;
    if (eqEl) eqEl.textContent = equity === null || equity === undefined ? "\u2014" : `$${fmt.num(equity, 2)}`;
    const realPill = $("#balRealPill");
    const eqPill = $("#balEqPill");
    const realK = $("#balRealPill .pillk");
    const eqK = $("#balEqPill .pillk");
    if (realK) realK.textContent = mode === "live" ? "withdrawable" : "realised";
    if (eqK) eqK.textContent = mode === "live" ? "accountValue" : "equity";
    if (realPill) {
      if (mode === "live") {
        if (realised === null || realised === undefined) realPill.title = "Withdrawable unavailable";
        else {
          const asof = b.realised_asof || "\u2014";
          const av = (typeof acct === "number" && Number.isFinite(acct)) ? `$${fmt.num(acct, 2)}` : "\u2014";
          const mu = (typeof marginUsedHl === "number" && Number.isFinite(marginUsedHl))
            ? `$${fmt.num(marginUsedHl, 2)}`
            : ((typeof marginUsedEst === "number" && Number.isFinite(marginUsedEst)) ? `$${fmt.num(marginUsedEst, 2)}` : "\u2014");
          if (src === "hyperliquid") {
            realPill.title = `Withdrawable (Hyperliquid) as of ${asof}\n$${fmt.num(realised, 2)}\nAccountValue: ${av}\nMargin used: ${mu}`;
          } else {
            realPill.title = `Withdrawable (estimate) as of ${asof}\n$${fmt.num(realised, 2)}\nAccountValue snapshot: ${av}\nMargin used est: ${mu}\nwithdrawable \u2248 accountValue \u2212 marginUsed`;
          }
        }
      } else {
        realPill.title = realised === null || realised === undefined ? "Realised cash unavailable" : `Realised cash as of ${b.realised_asof || "\u2014"}`;
      }
    }
    if (eqPill) {
      if (equity === null || equity === undefined) { eqPill.title = mode === "live" ? "AccountValue unavailable" : "Equity estimate unavailable"; }
      else if (mode === "live") {
        const asof = b.realised_asof || "\u2014";
        const pct = (typeof fr === "number" && Number.isFinite(fr)) ? `${(fr * 100).toFixed(3)}%` : "\u2014";
        const u = (typeof unreal === "number" && Number.isFinite(unreal)) ? fmt.num(unreal, 2) : "\u2014";
        const f2 = (typeof fees === "number" && Number.isFinite(fees)) ? fmt.num(fees, 2) : "\u2014";
        if (src === "hyperliquid") {
          eqPill.title = `AccountValue (Hyperliquid) as of ${asof}\n$${fmt.num(equity, 2)}\nuPnL est (local mids): $${u}\nEst close fees: $${f2} (fee ${pct})`;
        } else {
          eqPill.title = `AccountValue (DB snapshot) as of ${asof}\n$${fmt.num(equity, 2)}\nuPnL est (local mids): $${u}\nEst close fees: $${f2} (fee ${pct})`;
        }
      } else {
        if (realised === null || realised === undefined) { eqPill.title = "Equity estimate unavailable"; }
        else {
          const pct = (typeof fr === "number" && Number.isFinite(fr)) ? `${(fr * 100).toFixed(3)}%` : "\u2014";
          const u = (typeof unreal === "number" && Number.isFinite(unreal)) ? fmt.num(unreal, 2) : "\u2014";
          const f2 = (typeof fees === "number" && Number.isFinite(fees)) ? fmt.num(fees, 2) : "\u2014";
          eqPill.title = `Equity est. now = realised + uPnL \u2212 close fees\n$${fmt.num(realised, 2)} + $${u} \u2212 $${f2} (fee ${pct})`;
        }
      }
    }
  }

  function applyCandleConfigFromSnapshot(snap) {
    const cfg = snap?.config;
    if (!cfg) return;
    const intervals = Array.isArray(cfg.candle_intervals) ? cfg.candle_intervals : null;
    if (intervals && intervals.length) state.candleIntervals = intervals.map((x) => normInterval(x)).filter((x) => x);
    const savedIv = storageGet(prefKey("candleInterval"));
    const desired = savedIv ? normInterval(savedIv) : normInterval(cfg.candle_interval_default || cfg.trader_interval);
    if (desired && desired !== state.candleInterval) setCandleInterval(desired, { persist: false });
    renderCandleIntervalButtons(state.candleIntervals);
    renderCandleRangeButtons();
    renderCandleIndButtons();
  }

  function labelTickWindow(s) {
    const n = Number(s || 0);
    if (n === 300) return "5m";
    if (n === 900) return "15m";
    if (n === 3600) return "1h";
    if (n > 0 && n < 3600) return `${Math.round(n / 60)}m`;
    if (n >= 3600) return `${Math.round(n / 3600)}h`;
    return "\u2014";
  }

  function updateSparkMeta() {
    const el = $("#sparkMeta");
    if (!el) return;
    if (state.chartMode === "candles") {
      const n = (state.candles || []).length;
      const ind = normCandleInd(state.candleInd);
      const indTxt = ind === "rsi" ? " \u00b7 RSI14" : (ind === "macd" ? " \u00b7 MACD12/26/9" : (ind === "adx" ? " \u00b7 ADX14" : ""));
      el.textContent = `candles \u00b7 ${state.candleInterval} \u00b7 ${n}/${state.candleBars} bars${indTxt}`;
      return;
    }
    const w = labelTickWindow(state.tickWindowS);
    const n = (state.focusHist || []).length;
    el.textContent = `ticks \u00b7 ${w} \u00b7 ${n} pts`;
  }

  function redraw() {
    updateSparkMeta();
    if (state.chartMode === "candles") drawCandles(state.candles || []);
    else drawSpark(state.focusHist || []);
  }

  /* ── Chart: shared tooltip helper ── */

  function drawTooltip(ctx, dpr, lines, hx, hy, x0, x1, y0) {
    ctx.save();
    ctx.font = `${11 * dpr}px ${FONT}`;
    const wMax = Math.max(...lines.map((l) => ctx.measureText(l.text).width));
    const bw = wMax + 16 * dpr;
    const bh = (lines.length * 15 + 10) * dpr;
    let bx = hx + 10 * dpr;
    let by = hy - bh - 10 * dpr;
    if (bx + bw > x1) bx = hx - bw - 10 * dpr;
    if (by < y0) by = hy + 10 * dpr;
    ctx.fillStyle = C.tooltipBg;
    ctx.strokeStyle = C.tooltipBorder;
    ctx.lineWidth = 1;
    const r = 6 * dpr;
    ctx.beginPath();
    ctx.moveTo(bx + r, by);
    ctx.arcTo(bx + bw, by, bx + bw, by + bh, r);
    ctx.arcTo(bx + bw, by + bh, bx, by + bh, r);
    ctx.arcTo(bx, by + bh, bx, by, r);
    ctx.arcTo(bx, by, bx + bw, by, r);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    for (let i = 0; i < lines.length; i++) {
      ctx.fillStyle = lines[i].color || C.tooltipText;
      ctx.fillText(lines[i].text, bx + 8 * dpr, by + (16 + i * 15) * dpr);
    }
    ctx.restore();
  }

  /* ── Chart: Ticks sparkline ── */

  function drawSpark(points) {
    const canvas = $("#spark");
    const ctx = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const wantW = Math.max(1, Math.floor(rect.width * dpr));
    const wantH = Math.max(1, Math.floor(rect.height * dpr));
    if (canvas.width !== wantW || canvas.height !== wantH) { canvas.width = wantW; canvas.height = wantH; }
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // subtle gradient background
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, C.bgGradTop);
    g.addColorStop(1, C.bgGradBot);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);

    if (!points || points.length < 2) {
      ctx.fillStyle = C.gridLabel;
      ctx.font = `${11 * dpr}px ${FONT}`;
      ctx.fillText("no ticks yet", 14 * dpr, 24 * dpr);
      return;
    }

    const { pos, entries } = currentPosAndEntries();
    const entryLines = buildEntryLines(pos, entries);
    const entryPrices = entryLines.map((l) => l.price).filter((v) => Number.isFinite(v));
    const ys = points.map((p) => p.mid).concat(entryPrices);
    const min = Math.min(...ys);
    const max = Math.max(...ys);
    const pad = (max - min) * 0.12 || 1e-9;
    const lo = min - pad;
    const hi = max + pad;
    const x0 = 10 * dpr, x1 = w - 10 * dpr;
    const y0 = 14 * dpr, y1 = h - 18 * dpr;

    // grid lines
    ctx.strokeStyle = C.gridLine;
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i++) { const yy = y0 + (i * (y1 - y0)) / 4; ctx.beginPath(); ctx.moveTo(x0, yy); ctx.lineTo(x1, yy); ctx.stroke(); }

    const tss = points.map((p) => p.ts_ms || 0);
    const tMin = Math.min(...tss);
    const tMax = Math.max(...tss);
    const tDen = tMax - tMin || 1;
    const toX = (p) => x0 + ((Number(p.ts_ms || tMin) - tMin) * (x1 - x0)) / tDen;
    const toY = (v) => y1 - ((v - lo) * (y1 - y0)) / (hi - lo);

    // y-axis labels
    ctx.save();
    ctx.font = `${10 * dpr}px ${FONT}`;
    ctx.fillStyle = C.gridLabel;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (let i = 1; i <= 3; i++) { const yy = y0 + (i * (y1 - y0)) / 4; const v = lo + ((y1 - yy) * (hi - lo)) / (y1 - y0); ctx.fillText(fmtPx(v), x0 + 2 * dpr, yy); }
    // x-axis labels
    const xt = [{ x: x0, ts: tMin, align: "left" }, { x: (x0 + x1) / 2, ts: tMin + tDen / 2, align: "center" }, { x: x1, ts: tMax, align: "right" }];
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    ctx.textBaseline = "top";
    for (const tk of xt) { ctx.beginPath(); ctx.moveTo(tk.x, y1); ctx.lineTo(tk.x, y1 + 4 * dpr); ctx.stroke(); ctx.textAlign = tk.align; ctx.fillText(hmLabelFromMs(tk.ts), tk.x, y1 + 4.5 * dpr); }
    ctx.restore();

    // Entry/avg lines
    let hoverLine = null;
    if (state.pointer && entryLines.length) {
      let best = null; let bestDy = Infinity;
      for (const ln of entryLines) { const dy = Math.abs(state.pointer.y - toY(ln.price)); if (dy < bestDy) { bestDy = dy; best = ln; } }
      if (best && bestDy <= 7 * dpr) hoverLine = best;
    }
    if (entryPrices.length) {
      const posType = (pos?.type || "").toUpperCase();
      const avg = entryLines.find((l) => l.is_avg) || null;
      const avgPx = avg ? Number(avg.price) : null;
      const avgOk = avgPx !== null && Number.isFinite(avgPx);
      ctx.save();
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.95;
      ctx.strokeStyle = posType === "LONG" ? C.entryLong : (posType === "SHORT" ? C.entryShort : C.entryNeutral);
      const nonAvg = entryLines.filter((l) => !l.is_avg);
      for (const ln of nonAvg) {
        const y = toY(ln.price);
        ctx.setLineDash(ln.action === "ADD" ? [2, 6] : [7, 6]);
        ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y);
        if (hoverLine && hoverLine === ln) ctx.lineWidth = 2;
        ctx.stroke(); ctx.lineWidth = 1;
      }
      ctx.setLineDash([]);
      if (avgOk) {
        ctx.strokeStyle = posType === "LONG" ? C.avgLong : (posType === "SHORT" ? C.avgShort : C.avgNeutral);
        ctx.lineWidth = 2;
        const y = toY(avgPx);
        ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y);
        if (hoverLine && hoverLine.is_avg) ctx.lineWidth = 3;
        ctx.stroke();
        ctx.fillStyle = C.tooltipText;
        ctx.font = `${11 * dpr}px ${FONT}`;
        const label = `avg ${fmt.num(avgPx, 6)}`;
        const tw = ctx.measureText(label).width;
        ctx.fillText(label, Math.max(x0 + 6 * dpr, x1 - tw - 6 * dpr), Math.max(y0 + 14 * dpr, Math.min(y1 - 6 * dpr, y - 6 * dpr)));
      }
      ctx.restore();
    }

    // area fill
    ctx.beginPath();
    ctx.moveTo(toX(points[0]), toY(points[0].mid));
    for (let i = 1; i < points.length; i++) ctx.lineTo(toX(points[i]), toY(points[i].mid));
    ctx.lineTo(toX(points[points.length - 1]), y1);
    ctx.lineTo(toX(points[0]), y1);
    ctx.closePath();
    ctx.fillStyle = C.areaFill;
    ctx.fill();

    // line
    ctx.beginPath();
    ctx.moveTo(toX(points[0]), toY(points[0].mid));
    for (let i = 1; i < points.length; i++) ctx.lineTo(toX(points[i]), toY(points[i].mid));
    ctx.strokeStyle = C.accent;
    ctx.lineWidth = 1.5;
    ctx.shadowColor = C.lineGlow;
    ctx.shadowBlur = 8;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // last point dot
    const lx = toX(points[points.length - 1]);
    const ly = toY(points[points.length - 1].mid);
    ctx.fillStyle = "rgba(255,255,255,0.90)";
    ctx.beginPath();
    ctx.arc(lx, ly, 2.5, 0, Math.PI * 2);
    ctx.fill();

    // Hover crosshair + tooltip
    if (state.sparkHover && state.sparkHover.ts_ms && state.sparkHover.mid !== null && state.sparkHover.mid !== undefined) {
      const hp = state.sparkHover;
      const hx = toX(hp);
      const hy = toY(hp.mid);
      ctx.save();
      ctx.strokeStyle = C.crosshair;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(hx, y0); ctx.lineTo(hx, y1); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x0, hy); ctx.lineTo(x1, hy); ctx.stroke();
      ctx.fillStyle = "rgba(255,255,255,0.92)";
      ctx.beginPath(); ctx.arc(hx, hy, 3, 0, Math.PI * 2); ctx.fill();
      const t = fmt.hmsFromMs(hp.ts_ms);
      const ptxt = `MID ${fmt.num(hp.mid, 6)}`;
      const ltxt = hoverLine ? entryLineText(hoverLine) : null;
      const lines = [];
      lines.push({ text: ptxt, color: C.tooltipText });
      if (ltxt) lines.push({ text: ltxt, color: C.accent });
      lines.push({ text: t, color: C.tooltipMuted });
      drawTooltip(ctx, dpr, lines, hx, hy, x0, x1, y0);
      ctx.restore();
    }
  }

  /* ── Chart: Candles ── */

  function drawCandles(candles) {
    const canvas = $("#spark");
    const ctx = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const wantW = Math.max(1, Math.floor(rect.width * dpr));
    const wantH = Math.max(1, Math.floor(rect.height * dpr));
    if (canvas.width !== wantW || canvas.height !== wantH) { canvas.width = wantW; canvas.height = wantH; }
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, C.bgGradTop);
    bg.addColorStop(1, C.bgGradBot);
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    if (!candles || candles.length < 2) {
      ctx.fillStyle = C.gridLabel;
      ctx.font = `${11 * dpr}px ${FONT}`;
      ctx.fillText("no candles yet", 14 * dpr, 24 * dpr);
      return;
    }

    const { pos, entries } = currentPosAndEntries();
    const entryLines = buildEntryLines(pos, entries);
    const entryPrices = entryLines.map((l) => l.price).filter((v) => Number.isFinite(v));
    const lows = candles.map((c) => Number(c.l)).concat(entryPrices);
    const highs = candles.map((c) => Number(c.h)).concat(entryPrices);
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const padV = (max - min) * 0.10 || 1e-9;
    const lo = min - padV;
    const hi = max + padV;
    const x0 = 10 * dpr, x1 = w - 10 * dpr;
    const y0 = 14 * dpr, y1 = h - 18 * dpr;

    const ind = normCandleInd(state.candleInd);
    const indOn = ind !== "off";
    const fullH = y1 - y0;
    const gap = Math.round(Math.max(6 * dpr, Math.min(12 * dpr, fullH * 0.05)));
    const gaps = gap * (indOn ? 2 : 1);
    let volH = Math.round(Math.max(22 * dpr, Math.min(66 * dpr, fullH * (indOn ? 0.16 : 0.20))));
    let indH = indOn ? Math.round(Math.max(26 * dpr, Math.min(72 * dpr, fullH * 0.18))) : 0;
    const minPriceH = 90 * dpr;
    if ((fullH - volH - indH - gaps) < minPriceH) {
      const avail = Math.max(18 * dpr, fullH - minPriceH - gaps);
      if (indOn) { volH = Math.max(18 * dpr, Math.round(avail * 0.44)); indH = Math.max(18 * dpr, Math.round(avail - volH)); }
      else { volH = Math.max(18 * dpr, Math.round(avail)); }
    }
    const yVol1 = y1;
    const yVol0 = yVol1 - volH;
    const yInd1 = indOn ? (yVol0 - gap) : yVol0;
    const yInd0 = indOn ? (yInd1 - indH) : yInd1;
    const yP0 = y0;
    const yP1 = Math.max(yP0 + 10 * dpr, (indOn ? (yInd0 - gap) : (yVol0 - gap)));
    const toY = (v) => yP1 - ((v - lo) * (yP1 - yP0)) / (hi - lo);
    const n = candles.length;
    const step = (x1 - x0) / (n - 1);
    const bodyW = Math.max(2 * dpr, Math.min(10 * dpr, step * 0.62));
    const volW = Math.max(1 * dpr, Math.min(14 * dpr, step * 0.86));
    let rsi = null, adx = null, macd = null;

    // Panel backdrops
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,0.08)";
    ctx.fillRect(x0, yVol0, x1 - x0, yVol1 - yVol0);
    if (indOn && (yInd1 - yInd0) > 4 * dpr) { ctx.fillStyle = "rgba(0,0,0,0.10)"; ctx.fillRect(x0, yInd0, x1 - x0, yInd1 - yInd0); }
    ctx.restore();
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    if (indOn) { ctx.beginPath(); ctx.moveTo(x0, yInd0 - gap / 2); ctx.lineTo(x1, yInd0 - gap / 2); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(x0, yVol0 - gap / 2); ctx.lineTo(x1, yVol0 - gap / 2); ctx.stroke();

    // Volume bars
    const vols = candles.map((c) => Math.max(0, Number(c.v) || 0));
    const volSorted = vols.filter((v) => v > 0).slice().sort((a, b) => a - b);
    const volMax = volSorted.length ? volSorted[volSorted.length - 1] : 0;
    let volCap = volMax || 1;
    if (volSorted.length >= 10) { const p97 = volSorted[Math.floor((volSorted.length - 1) * 0.97)]; if (p97 > 0 && volMax > p97 * 3) volCap = p97 * 3; }
    const volPanelH = Math.max(1, yVol1 - yVol0);
    for (let i = 0; i < n; i++) {
      const c = candles[i];
      const v = Math.max(0, Number(c.v) || 0);
      const ratio = Math.max(0, Math.min(1, v / volCap));
      const vh = Math.max(0, ratio * volPanelH);
      if (vh <= 0) continue;
      const o = Number(c.o); const cl = Number(c.c); const up = cl >= o;
      const x = x0 + i * step; const y = yVol1 - vh;
      ctx.fillStyle = up ? C.volUp : C.volDn;
      ctx.fillRect(x - volW / 2, y, volW, vh);
      ctx.fillStyle = up ? C.volUpTop : C.volDnTop;
      ctx.fillRect(x - volW / 2, y, volW, Math.max(1, Math.floor(1 * dpr)));
    }

    // Volume label
    ctx.save();
    ctx.font = `${9 * dpr}px ${FONT}`;
    ctx.fillStyle = C.gridLabel;
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    const clipped = volCap < volMax;
    const vtxt = volMax > 0 ? `vol ${fmtVol(volCap)}${clipped ? "+" : ""}` : "vol";
    ctx.fillText(vtxt, x0 + 2 * dpr, yVol0 + 2 * dpr);
    ctx.restore();

    // Indicator panel
    if (indOn && (yInd1 - yInd0) > 10 * dpr) {
      const closes = candles.map((c) => Number(c.c));
      const iTop = yInd0;
      const iBot = yInd1;
      const iH = Math.max(1, iBot - iTop);
      const lastFinite = (arr) => { for (let i = n - 1; i >= 0; i--) { const v = arr?.[i]; if (v !== null && v !== undefined && Number.isFinite(Number(v))) return Number(v); } return null; };
      const drawLine = (arr, toYf, color, widthPx) => {
        ctx.strokeStyle = color; ctx.lineWidth = widthPx; ctx.beginPath(); let started = false;
        for (let i = 0; i < n; i++) { const v = arr?.[i]; if (v === null || v === undefined || !Number.isFinite(Number(v))) { started = false; continue; } const x = x0 + i * step; const y = toYf(Number(v)); if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y); }
        if (started) ctx.stroke();
      };
      ctx.save();
      ctx.font = `${9 * dpr}px ${FONT}`;
      ctx.textBaseline = "top";
      ctx.textAlign = "left";

      if (ind === "rsi") {
        rsi = calcRSI(closes, 14);
        const toYr = (v) => iBot - (Math.max(0, Math.min(100, v)) / 100) * iH;
        const y70 = toYr(70); const y30 = toYr(30);
        ctx.fillStyle = "rgba(255,255,255,0.02)";
        ctx.fillRect(x0, y70, x1 - x0, Math.max(0, y30 - y70));
        ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.lineWidth = 1; ctx.setLineDash([3 * dpr, 4 * dpr]);
        for (const lv of [30, 70]) { const yy = toYr(lv); ctx.beginPath(); ctx.moveTo(x0, yy); ctx.lineTo(x1, yy); ctx.stroke(); }
        ctx.setLineDash([]);
        drawLine(rsi, toYr, "rgba(58,255,231,0.75)", Math.max(1, 1.5 * dpr));
        const last = lastFinite(rsi);
        ctx.fillStyle = C.gridLabel;
        ctx.fillText(last === null ? "RSI14" : `RSI14 ${fmt.num(last, 1)}`, x0 + 2 * dpr, iTop + 2 * dpr);
      } else if (ind === "adx") {
        adx = calcADX(candles, 14);
        const toYa = (v) => iBot - (Math.max(0, Math.min(100, v)) / 100) * iH;
        ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 1; ctx.setLineDash([3 * dpr, 4 * dpr]);
        for (const lv of [20, 40]) { const yy = toYa(lv); ctx.beginPath(); ctx.moveTo(x0, yy); ctx.lineTo(x1, yy); ctx.stroke(); }
        ctx.setLineDash([]);
        drawLine(adx, toYa, "rgba(255,183,3,0.75)", Math.max(1, 1.5 * dpr));
        const last = lastFinite(adx);
        ctx.fillStyle = C.gridLabel;
        ctx.fillText(last === null ? "ADX14" : `ADX14 ${fmt.num(last, 1)}`, x0 + 2 * dpr, iTop + 2 * dpr);
      } else if (ind === "macd") {
        macd = calcMACD(closes, 12, 26, 9);
        const m = macd.macd; const s = macd.signal; const hst = macd.hist;
        let maxAbs = 0;
        for (let i = 0; i < n; i++) { for (const v of [m?.[i], s?.[i], hst?.[i]]) { if (v === null || v === undefined || !Number.isFinite(Number(v))) continue; maxAbs = Math.max(maxAbs, Math.abs(Number(v))); } }
        if (!(maxAbs > 0)) maxAbs = 1e-9;
        const hiM = maxAbs * 1.15; const loM = -hiM;
        const toYm = (v) => iBot - ((v - loM) * iH) / (hiM - loM);
        const yZ = toYm(0);
        ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.lineWidth = 1; ctx.setLineDash([3 * dpr, 4 * dpr]);
        ctx.beginPath(); ctx.moveTo(x0, yZ); ctx.lineTo(x1, yZ); ctx.stroke(); ctx.setLineDash([]);
        const barW = Math.max(1 * dpr, Math.min(12 * dpr, step * 0.72));
        for (let i = 0; i < n; i++) {
          const v = hst?.[i]; if (v === null || v === undefined || !Number.isFinite(Number(v))) continue;
          const val = Number(v); const x = x0 + i * step; const y = toYm(val);
          const top = Math.min(yZ, y); const hh = Math.abs(y - yZ); if (hh < 1 * dpr) continue;
          ctx.fillStyle = val >= 0 ? "rgba(74,222,128,0.16)" : "rgba(255,77,109,0.16)";
          ctx.fillRect(x - barW / 2, top, barW, hh);
        }
        drawLine(s, toYm, "rgba(255,255,255,0.40)", Math.max(1, 1.0 * dpr));
        drawLine(m, toYm, "rgba(58,255,231,0.80)", Math.max(1, 1.5 * dpr));
        const lastM = lastFinite(m);
        ctx.fillStyle = C.gridLabel;
        ctx.fillText(lastM === null ? "MACD12/26/9" : `MACD ${fmtPx(lastM)}`, x0 + 2 * dpr, iTop + 2 * dpr);
      }
      ctx.restore();
    }

    // Price grid lines
    ctx.strokeStyle = C.gridLine;
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i++) { const yy = yP0 + (i * (yP1 - yP0)) / 4; ctx.beginPath(); ctx.moveTo(x0, yy); ctx.lineTo(x1, yy); ctx.stroke(); }

    // Axis labels
    ctx.save();
    ctx.font = `${10 * dpr}px ${FONT}`;
    ctx.fillStyle = C.gridLabel;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (let i = 1; i <= 3; i++) { const yy = yP0 + (i * (yP1 - yP0)) / 4; const v = lo + ((yP1 - yy) * (hi - lo)) / (yP1 - yP0); ctx.fillText(fmtPx(v), x0 + 2 * dpr, yy); }
    const idxs = Array.from(new Set([0, Math.round((n - 1) / 3), Math.round((2 * (n - 1)) / 3), n - 1])).filter((i) => i >= 0 && i < n).sort((a, b) => a - b);
    ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 1; ctx.textBaseline = "top";
    for (const idx of idxs) { const c = candles[idx]; const x = x0 + idx * step; const ts = Number(c?.t_close || c?.t); ctx.beginPath(); ctx.moveTo(x, y1); ctx.lineTo(x, y1 + 4 * dpr); ctx.stroke(); ctx.textAlign = idx === 0 ? "left" : (idx === (n - 1) ? "right" : "center"); ctx.fillText(hmLabelFromMs(ts), x, y1 + 4.5 * dpr); }
    ctx.restore();

    // Entry/avg lines (candle chart)
    let hoverLine = null;
    if (state.pointer && entryLines.length) {
      let best = null; let bestDy = Infinity;
      for (const ln of entryLines) { const dy = Math.abs(state.pointer.y - toY(ln.price)); if (dy < bestDy) { bestDy = dy; best = ln; } }
      if (best && bestDy <= 7 * dpr) hoverLine = best;
    }
    if (entryPrices.length) {
      const posType = (pos?.type || "").toUpperCase();
      const avg = entryLines.find((l) => l.is_avg) || null;
      const avgPx = avg ? Number(avg.price) : null;
      const avgOk = avgPx !== null && Number.isFinite(avgPx);
      ctx.save();
      ctx.lineWidth = 1; ctx.globalAlpha = 0.95;
      ctx.strokeStyle = posType === "LONG" ? C.entryLong : (posType === "SHORT" ? C.entryShort : C.entryNeutral);
      const nonAvg = entryLines.filter((l) => !l.is_avg);
      for (const ln of nonAvg) {
        const y = toY(ln.price);
        ctx.setLineDash(ln.action === "ADD" ? [2, 6] : [7, 6]);
        ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y);
        if (hoverLine && hoverLine === ln) ctx.lineWidth = 2;
        ctx.stroke(); ctx.lineWidth = 1;
      }
      ctx.setLineDash([]);
      if (avgOk) {
        ctx.strokeStyle = posType === "LONG" ? C.avgLong : (posType === "SHORT" ? C.avgShort : C.avgNeutral);
        ctx.lineWidth = 2;
        const y = toY(avgPx);
        ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y);
        if (hoverLine && hoverLine.is_avg) ctx.lineWidth = 3;
        ctx.stroke();
        ctx.fillStyle = C.tooltipText;
        ctx.font = `${11 * dpr}px ${FONT}`;
        const label = `avg ${fmt.num(avgPx, 6)}`;
        const tw = ctx.measureText(label).width;
        ctx.fillText(label, Math.max(x0 + 6 * dpr, x1 - tw - 6 * dpr), Math.max(y0 + 14 * dpr, Math.min(y1 - 6 * dpr, y - 6 * dpr)));
      }
      ctx.restore();
    }

    // Draw candle bodies
    for (let i = 0; i < n; i++) {
      const c = candles[i];
      const o = Number(c.o); const hiV = Number(c.h); const loV = Number(c.l); const cl = Number(c.c);
      const up = cl >= o;
      const x = x0 + i * step;
      const yH = toY(hiV); const yL = toY(loV); const yO = toY(o); const yC = toY(cl);
      ctx.strokeStyle = up ? C.candleUpWick : C.candleDnWick;
      ctx.lineWidth = Math.max(1, Math.floor(1 * dpr));
      ctx.beginPath(); ctx.moveTo(x, yH); ctx.lineTo(x, yL); ctx.stroke();
      const top = Math.min(yO, yC); const bot = Math.max(yO, yC);
      const hh = Math.max(2 * dpr, bot - top);
      ctx.fillStyle = up ? C.candleUpBody : C.candleDnBody;
      ctx.strokeStyle = up ? C.candleUpEdge : C.candleDnEdge;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.rect(x - bodyW / 2, top, bodyW, hh); ctx.fill(); ctx.stroke();
    }

    // Hover tooltip for candles
    if (state.candleHover && state.candleHover.t) {
      const c = state.candleHover;
      let idx = 0;
      for (let i = 0; i < n; i++) { if ((candles[i].t || 0) === c.t) { idx = i; break; } }
      const x = x0 + idx * step;
      const y = toY(Number(c.c));
      ctx.save();
      ctx.strokeStyle = C.crosshair; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y1); ctx.stroke();
      const at = new Date(Number(c.t_close || c.t)).toISOString().slice(0, 19).replace("T", " ") + "Z";
      const lines = [];
      lines.push({ text: `C ${fmt.num(c.c, 6)}`, color: C.tooltipText });
      if (hoverLine) lines.push({ text: entryLineText(hoverLine), color: C.accent });
      lines.push({ text: `O ${fmt.num(c.o, 6)}`, color: C.tooltipMuted });
      lines.push({ text: `H ${fmt.num(c.h, 6)}`, color: C.tooltipMuted });
      lines.push({ text: `L ${fmt.num(c.l, 6)}`, color: C.tooltipMuted });
      if (c.v !== undefined && c.v !== null) lines.push({ text: `V ${fmtVol(c.v)}`, color: C.tooltipMuted });
      if (ind === "rsi" && Array.isArray(rsi)) { const rv = rsi[idx]; if (rv !== null && rv !== undefined && Number.isFinite(Number(rv))) lines.push({ text: `RSI ${fmt.num(rv, 1)}`, color: C.tooltipMuted }); }
      else if (ind === "adx" && Array.isArray(adx)) { const av = adx[idx]; if (av !== null && av !== undefined && Number.isFinite(Number(av))) lines.push({ text: `ADX ${fmt.num(av, 1)}`, color: C.tooltipMuted }); }
      else if (ind === "macd" && macd && Array.isArray(macd.macd)) {
        const mv = macd.macd[idx]; const sv = macd.signal[idx]; const hv = macd.hist[idx];
        if (mv !== null && mv !== undefined && Number.isFinite(Number(mv))) lines.push({ text: `MACD ${fmtPx(mv)}`, color: C.tooltipMuted });
        if (sv !== null && sv !== undefined && Number.isFinite(Number(sv))) { const hTxt = hv !== null && hv !== undefined && Number.isFinite(Number(hv)) ? ` \u00b7 H ${fmtPx(hv)}` : ""; lines.push({ text: `SIG ${fmtPx(sv)}${hTxt}`, color: C.tooltipMuted }); }
      }
      lines.push({ text: at, color: C.tooltipMuted });
      drawTooltip(ctx, dpr, lines, x, y0 + 10 * dpr, x0, x1, y0);
      ctx.restore();
    }
  }

  /* ── Data fetching ── */

  async function seedSparkline(sym) {
    try {
      const win = Math.max(60, Math.min(24 * 60 * 60, Number(state.tickWindowS) || 900));
      const data = await fetchJson(`/api/sparkline?symbol=${encodeURIComponent(sym)}&window_s=${encodeURIComponent(win)}`, 3000);
      state.focusHist = (data.points || []).map((p) => ({ ts_ms: p.ts_ms, mid: p.mid })).filter((p) => p.ts_ms && p.mid !== null && p.mid !== undefined).sort((a, b) => a.ts_ms - b.ts_ms);
      $("#sparkSub").textContent = `${state.focusHist.length} pts`;
      redraw();
    } catch { $("#sparkSub").textContent = "sparkline unavailable"; }
  }

  async function fetchCandles(sym) {
    try {
      const bars = Math.max(2, Math.min(2000, Number(state.candleBars) || 72));
      state.candlesFor = sym;
      state.candlesLastFetchTs = Date.now();
      const data = await fetchJson(`/api/candles?mode=${encodeURIComponent(state.mode)}&symbol=${encodeURIComponent(sym)}&interval=${encodeURIComponent(state.candleInterval)}&limit=${encodeURIComponent(bars)}`, 3500);
      if (state.focus !== sym || state.chartMode !== "candles") return;
      state.candles = (data.candles || []).filter((c) => c && c.t && c.o !== undefined && c.h !== undefined && c.l !== undefined && c.c !== undefined).sort((a, b) => (a.t || 0) - (b.t || 0));
      $("#sparkSub").textContent = `${state.candles.length} bars`;
      const livePx = state.mids?.mids?.[sym];
      syncLiveCandleFromMid(sym, livePx);
      redraw();
    } catch { $("#sparkSub").textContent = "candles unavailable"; state.candles = []; redraw(); }
  }

  async function fetchMarks(sym) {
    try {
      state.marksFor = sym;
      state.marksLastFetchTs = Date.now();
      const mk = await fetchJson(`/api/marks?mode=${encodeURIComponent(state.mode)}&symbol=${encodeURIComponent(sym)}`, 2500);
      if (state.focus !== sym) return;
      state.sparkMarks = mk;
      redraw();
    } catch { /* ignore; overlay is optional */ }
  }

  function pushTick(sym, mid) {
    if (!sym || sym !== state.focus) return;
    const ts = Date.now();
    const minDt = 900;
    if (state.focusLastTickTs && ts - state.focusLastTickTs < minDt && mid === state.focusLastMid) return;
    state.focusLastTickTs = ts;
    state.focusLastMid = mid;
    state.focusHist.push({ ts_ms: ts, mid });
    const winMs = Math.max(60_000, Math.min(24 * 60 * 60 * 1000, (Number(state.tickWindowS) || 900) * 1000));
    const cutoff = ts - winMs;
    while (state.focusHist.length && state.focusHist[0].ts_ms < cutoff) state.focusHist.shift();
    $("#sparkSub").textContent = `${state.focusHist.length} pts`;
    redraw();
  }

  /* ── Polling ── */

  async function pollSnapshot() {
    if (state.paused) return;
    try {
      const snap = await fetchJson(`/api/snapshot?mode=${encodeURIComponent(state.mode)}`, 3500);
      state.lastSnapshot = snap;
      applyCandleConfigFromSnapshot(snap);
      updateConn(true, "server ok");
      state.lastConnOk = true;
      state.lastConnAt = Date.now();
      renderHealth(snap);
      renderTable(snap.symbols || []);
      renderFeeds(snap);
      $("#ts").textContent = `snapshot ${new Date(snap.now_ts_ms).toISOString().slice(11,19)}Z`;
      if (!state.focus && (snap.symbols || []).length) setFocus(snap.symbols[0].symbol);
      hydrateFocusFromSnapshot();
      if (state.focus) {
        const now = Date.now();
        const due = !state.marksLastFetchTs || (now - state.marksLastFetchTs) > 6000;
        if (due) fetchMarks(state.focus);
      }
      if (state.focus && state.chartMode === "candles") {
        const now = Date.now();
        const due = !state.candlesLastFetchTs || (now - state.candlesLastFetchTs) > 20000;
        if (due) fetchCandles(state.focus);
      }
    } catch (e) { updateConn(false, "server offline"); state.lastConnOk = false; state.lastConnAt = Date.now(); }
  }

  async function pollMids() {
    if (state.paused) return;
    try {
      const ws = await fetchJson(`/api/mids`, 2000);
      applyMidsSnapshot(ws);
    } catch { /* ignore; snapshot will show WS health */ }
  }

  function applyMidsSnapshot(ws) {
    if (state.paused) return;
    if (!ws || !ws.mids) return;
    state.mids = ws;
    const mids = ws.mids;
    const focusSym = state.focus;
    const focusPx = focusSym ? mids[focusSym] : undefined;
    if (focusSym && focusPx !== undefined) {
      const ageS = ws.updated_ts_ms ? (Date.now() - ws.updated_ts_ms) / 1000 : null;
      $("#detailMid").textContent = ageS === null ? `MID ${fmt.num(focusPx, 6)}` : `MID ${fmt.num(focusPx, 6)} (${fmt.age(ageS)})`;
      if (state.chartMode === "ticks") pushTick(focusSym, focusPx);
      else if (state.chartMode === "candles") { if (syncLiveCandleFromMid(focusSym, focusPx)) redraw(); }
    }
    const rows = $$("#symBody tr");
    for (const tr of rows) {
      const sym = tr.dataset.sym;
      const px = mids[sym];
      if (px === undefined) continue;
      const midCell = tr.children[1];
      const pxN = Number(px);
      if (!Number.isFinite(pxN)) continue;
      const nextText = isMobile() ? fmtMidStable(sym, pxN) : fmt.num(pxN, 6);
      if (nextText === midCell.textContent) continue;
      const key = String(sym || "").trim().toUpperCase();
      const prevPx = state.lastMidBySym?.[key];
      midCell.textContent = nextText;
      if (Number.isFinite(prevPx) && pxN !== prevPx) flashMidCell(key, midCell, pxN > prevPx ? "up" : "down");
      state.lastMidBySym[key] = pxN;
    }
  }

  function stopMidsStream() {
    const es = state.midsStream;
    state.midsStream = null;
    state.midsStreamConnected = false;
    if (state.midsStreamRetryTimer) {
      clearTimeout(state.midsStreamRetryTimer);
      state.midsStreamRetryTimer = null;
    }
    if (es) {
      try { es.close(); } catch { /* ignore */ }
    }
  }

  function scheduleMidsStreamReconnect() {
    if (state.midsStreamRetryTimer) return;
    const delayMs = Math.max(500, Math.min(15000, Number(state.midsStreamBackoffMs) || 1000));
    state.midsStreamRetryTimer = setTimeout(() => {
      state.midsStreamRetryTimer = null;
      startMidsStream();
    }, delayMs);
    state.midsStreamBackoffMs = Math.min(15000, Math.round(delayMs * 1.6));
  }

  function startMidsStream() {
    if (state.midsStream) return;
    if (typeof EventSource === "undefined") return;
    let es;
    try {
      es = new EventSource("/api/mids/stream");
    } catch {
      scheduleMidsStreamReconnect();
      return;
    }

    state.midsStream = es;
    es.onopen = () => {
      state.midsStreamConnected = true;
      state.midsStreamBackoffMs = 1000;
    };
    es.addEventListener("mids", (ev) => {
      if (!ev || !ev.data) return;
      try { applyMidsSnapshot(JSON.parse(ev.data)); } catch { /* ignore malformed payload */ }
    });
    es.onmessage = (ev) => {
      if (!ev || !ev.data) return;
      try { applyMidsSnapshot(JSON.parse(ev.data)); } catch { /* ignore malformed payload */ }
    };
    es.onerror = () => {
      state.midsStreamConnected = false;
      stopMidsStream();
      scheduleMidsStreamReconnect();
    };
  }

  /* ── UI bindings ── */

  function bindUi() {
    for (const mb of MODE_BUTTONS) {
      const el = $("#" + mb.id);
      if (el) el.addEventListener("click", () => { state.focus = null; setSeg(mb.mode); pollSnapshot(); });
    }
    const ml = $("#mnavList");
    const mf = $("#mnavFocus");
    if (ml) ml.addEventListener("click", () => setMobileView("list", { focusSearch: true }));
    if (mf) mf.addEventListener("click", () => setMobileView("focus"));
    $("#chartModeTicks").addEventListener("click", () => setChartMode("ticks"));
    $("#chartModeCandles").addEventListener("click", () => setChartMode("candles"));
    $$("#tickRanges .segbtn").forEach((b) => b.addEventListener("click", () => setTickWindowS(b.dataset.window)));
    const cr = $("#candleRanges");
    if (cr) cr.addEventListener("click", (e) => { const b = e.target.closest("button[data-bars]"); if (!b) return; setCandleBars(b.dataset.bars); });
    const ci = $("#candleIntervals");
    if (ci) ci.addEventListener("click", (e) => { const b = e.target.closest("button[data-interval]"); if (!b) return; setCandleInterval(b.dataset.interval); });
    const cd = $("#candleInd");
    if (cd) cd.addEventListener("click", (e) => { const b = e.target.closest("button[data-ind]"); if (!b) return; setCandleInd(b.dataset.ind); });
    $("#search").addEventListener("input", (e) => { state.search = e.target.value || ""; if (state.lastSnapshot) renderTable(state.lastSnapshot.symbols || []); });
    $("#pauseBtn").addEventListener("click", () => {
      state.paused = !state.paused;
      $("#pauseTxt").textContent = state.paused ? "RESUME" : "PAUSE";
      if (!state.paused) {
        pollSnapshot();
        pollMids();
      }
    });
    $$(".tab").forEach((b) => b.addEventListener("click", () => setFeed(b.dataset.feed)));
    const feedAudit = $("#feedAudit");
    if (feedAudit) feedAudit.addEventListener("click", (e) => { const b = e.target.closest("button[data-audit-idx]"); if (!b) return; const idx = Number(b.dataset.auditIdx); const a = (Number.isFinite(idx) && idx >= 0) ? (state.auditEvents || [])[idx] : null; openAuditModal(a); });
    const modal = $("#modal");
    const modalClose = $("#modalClose");
    if (modal) modal.addEventListener("click", (e) => { if (e.target && e.target.closest("[data-modal-close]")) closeModal(); });
    if (modalClose) modalClose.addEventListener("click", () => closeModal());
    document.addEventListener("keydown", (e) => {
      if (e.key === "/") { e.preventDefault(); $("#search").focus(); }
      if (e.key === "Escape") { if (typeof decCloseModal === "function" && decCloseModal()) return; if (closeModal()) return; $("#search").blur(); }
    });
    const canvas = $("#spark");
    const onMove = (clientX, clientY) => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.max(1, window.devicePixelRatio || 1);
      const x = (clientX - rect.left) * dpr;
      const y = (clientY - rect.top) * dpr;
      if (x < 0 || y < 0 || x > canvas.width || y > canvas.height) return;
      state.pointer = { x, y };
      const x0 = 10 * dpr, x1 = canvas.width - 10 * dpr;
      const target = Math.max(0, Math.min(1, (x - x0) / (x1 - x0)));
      if (state.chartMode === "candles") {
        const bars = state.candles || [];
        if (bars.length < 2) return;
        const idx = Math.max(0, Math.min(bars.length - 1, Math.round(target * (bars.length - 1))));
        state.candleHover = bars[idx];
        state.sparkHover = null;
        redraw();
        return;
      }
      const pts = state.focusHist || [];
      if (pts.length < 2) return;
      const tss = pts.map((p) => p.ts_ms || 0);
      const tMin = Math.min(...tss);
      const tMax = Math.max(...tss);
      const tDen = tMax - tMin || 1;
      const tGuess = tMin + target * tDen;
      let best = pts[0]; let bestD = Math.abs((pts[0].ts_ms || 0) - tGuess);
      for (let i = 1; i < pts.length; i++) { const d = Math.abs((pts[i].ts_ms || 0) - tGuess); if (d < bestD) { bestD = d; best = pts[i]; } }
      state.sparkHover = best;
      state.candleHover = null;
      redraw();
    };
    canvas.addEventListener("mousemove", (e) => onMove(e.clientX, e.clientY));
    canvas.addEventListener("mouseleave", () => { state.sparkHover = null; state.candleHover = null; state.pointer = null; redraw(); });
    canvas.addEventListener("pointermove", (e) => onMove(e.clientX, e.clientY));
    canvas.addEventListener("pointerdown", (e) => onMove(e.clientX, e.clientY));
    canvas.addEventListener("pointerleave", () => { state.sparkHover = null; state.candleHover = null; state.pointer = null; redraw(); });
    window.addEventListener("resize", () => { redraw(); });
  }

  function tick() {
    pollSnapshot();
    pollMids();
    startMidsStream();
    setInterval(pollSnapshot, 1200);
    setInterval(() => { if (!state.midsStreamConnected) pollMids(); }, 1200);
  }

  /* ── Panel resizer (drag to resize left/right) ── */

  function initResizer() {
    const resizer = $("#panelResizer");
    if (!resizer) return;
    const layout = $("#main");
    const STORAGE_KEY = "aiq.leftPanelWidth";
    const MIN_W = 180;
    const MAX_PCT = 0.50;
    let dragging = false;
    let startX = 0;
    let startW = 0;

    const saved = storageGet(STORAGE_KEY);
    if (saved) {
      const w = Number(saved);
      if (Number.isFinite(w) && w >= MIN_W) {
        layout.style.gridTemplateColumns = `${w}px 0px 1fr`;
      }
    }

    function onDown(e) {
      e.preventDefault();
      dragging = true;
      startX = e.clientX ?? e.touches?.[0]?.clientX ?? 0;
      const leftPanel = layout.querySelector(".panel.left");
      startW = leftPanel ? leftPanel.getBoundingClientRect().width : 260;
      resizer.classList.add("is-dragging");
      document.body.classList.add("is-resizing");
    }

    function onMove(e) {
      if (!dragging) return;
      const cx = e.clientX ?? e.touches?.[0]?.clientX ?? 0;
      const delta = cx - startX;
      const maxW = layout.getBoundingClientRect().width * MAX_PCT;
      const w = Math.max(MIN_W, Math.min(maxW, startW + delta));
      layout.style.gridTemplateColumns = `${Math.round(w)}px 0px 1fr`;
    }

    function onUp() {
      if (!dragging) return;
      dragging = false;
      resizer.classList.remove("is-dragging");
      document.body.classList.remove("is-resizing");
      const leftPanel = layout.querySelector(".panel.left");
      if (leftPanel) storageSet(STORAGE_KEY, String(Math.round(leftPanel.getBoundingClientRect().width)));
      redraw();
    }

    resizer.addEventListener("mousedown", onDown);
    resizer.addEventListener("touchstart", onDown, { passive: false });
    document.addEventListener("mousemove", onMove);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("mouseup", onUp);
    document.addEventListener("touchend", onUp);
  }

  /* ============================================================
     DECISIONS DASHBOARD (AQC-824)
     ============================================================ */

  const decState = {
    decisions: [],
    offset: 0,
    limit: 50,
    hasMore: false,
    loading: false,
    currentDecisionId: null,
    lastFilters: {},
  };

  /* ── View tab switching ── */

  function setViewTab(tab) {
    const dash = tab === "dashboard";
    const bDash = $("#viewDash");
    const bDec = $("#viewDecisions");
    if (bDash) { bDash.classList.toggle("is-on", dash); bDash.setAttribute("aria-selected", dash ? "true" : "false"); }
    if (bDec) { bDec.classList.toggle("is-on", !dash); bDec.setAttribute("aria-selected", !dash ? "true" : "false"); }
    const main = $("#main");
    const decView = $("#decisionsView");
    if (main) main.classList.toggle("is-hidden", !dash);
    if (decView) decView.classList.toggle("is-hidden", dash);
    // On first switch to decisions, populate symbol dropdown
    if (!dash) decPopulateSymbols();
  }

  /* ── Symbol dropdown population ── */

  function decPopulateSymbols() {
    const sel = $("#decFilterSymbol");
    if (!sel) return;
    const snap = state.lastSnapshot;
    const symbols = (snap?.symbols || []).map((s) => s.symbol).sort();
    const current = sel.value;
    const existing = new Set(Array.from(sel.options).map((o) => o.value));
    for (const sym of symbols) {
      if (!existing.has(sym)) {
        const opt = document.createElement("option");
        opt.value = sym;
        opt.textContent = sym;
        sel.appendChild(opt);
      }
    }
    if (current) sel.value = current;
  }

  /* ── Build query params ── */

  function decBuildParams() {
    const p = new URLSearchParams();
    p.set("mode", state.mode);
    const sym = ($("#decFilterSymbol") || {}).value;
    const evt = ($("#decFilterEvent") || {}).value;
    const status = ($("#decFilterStatus") || {}).value;
    const start = ($("#decFilterStart") || {}).value;
    const end = ($("#decFilterEnd") || {}).value;
    if (sym) p.set("symbol", sym);
    if (evt) p.set("event_type", evt);
    if (status) p.set("status", status);
    if (start) {
      const ms = new Date(start).getTime();
      if (Number.isFinite(ms)) p.set("start", String(ms));
    }
    if (end) {
      const ms = new Date(end).getTime();
      if (Number.isFinite(ms)) p.set("end", String(ms));
    }
    p.set("limit", String(decState.limit));
    p.set("offset", String(decState.offset));
    return p;
  }

  /* ── Fetch decisions list ── */

  async function decFetchDecisions(append) {
    if (decState.loading) return;
    decState.loading = true;
    const tl = $("#decTimeline");
    const loadBtn = $("#decLoadMore");
    const summary = $("#decSummaryBar");
    if (!append) {
      decState.decisions = [];
      decState.offset = 0;
      if (tl) tl.innerHTML = '<div class="dec-empty">Loading...</div>';
    }
    try {
      const params = decBuildParams();
      decState.lastFilters = Object.fromEntries(params.entries());
      const data = await fetchJson(`/api/v2/decisions?${params.toString()}`, 5000);
      const items = data.decisions || data.items || data.results || [];
      const total = data.total ?? null;
      if (append) {
        decState.decisions = decState.decisions.concat(items);
      } else {
        decState.decisions = items;
      }
      decState.hasMore = items.length >= decState.limit;
      decState.offset += items.length;
      decRenderTimeline();
      if (summary) {
        const totalTxt = total !== null ? ` of ${total}` : "";
        summary.textContent = `${decState.decisions.length}${totalTxt} decisions \u00b7 mode: ${state.mode}`;
      }
      if (loadBtn) loadBtn.style.display = decState.hasMore ? "" : "none";
    } catch (err) {
      if (tl && !append) tl.innerHTML = `<div class="dec-empty">Error loading decisions: ${esc(String(err.message || err))}</div>`;
      if (summary) summary.textContent = "Error loading decisions";
    } finally {
      decState.loading = false;
    }
  }

  /* ── Render timeline ── */

  function decRenderTimeline() {
    const tl = $("#decTimeline");
    if (!tl) return;
    if (!decState.decisions.length) {
      tl.innerHTML = '<div class="dec-empty">No decisions found for the current filters.</div>';
      return;
    }
    tl.innerHTML = "";
    for (const d of decState.decisions) {
      const item = document.createElement("div");
      item.className = "dec-item";
      item.dataset.decId = d.id || "";
      const evType = String(d.event_type || "unknown").toLowerCase();
      const statusVal = String(d.status || "unknown").toLowerCase();
      const tsMs = Number(d.timestamp_ms || 0);
      const w = tsMs ? whenFromMs(tsMs) : null;
      const agoTxt = w ? w.ago : "\u2014";
      const atTxt = w ? w.at : "\u2014";
      const action = d.action_taken || "\u2014";
      const reason = d.rejection_reason || "";
      item.innerHTML = `
        <div class="dec-item-left">
          <span class="dec-badge dec-badge-${esc(evType)}">${esc(evType)}</span>
          <span class="dec-item-sym">${esc(d.symbol || "\u2014")}</span>
        </div>
        <div class="dec-item-center">
          <div class="dec-item-action">${esc(action)}</div>
          ${reason ? `<div class="dec-item-reason" title="${esc(reason)}">${esc(reason)}</div>` : ""}
        </div>
        <div class="dec-item-right">
          <span class="dec-status dec-status-${esc(statusVal)}">${esc(statusVal)}</span>
          <span class="dec-item-ago" title="${esc(atTxt)}">${esc(agoTxt)}</span>
          <span class="dec-item-time">${esc(atTxt)}</span>
        </div>
      `;
      item.addEventListener("click", () => decOpenDetail(d.id));
      tl.appendChild(item);
    }
  }

  /* ── Decision detail modal ── */

  async function decOpenDetail(decisionId) {
    if (!decisionId) return;
    decState.currentDecisionId = decisionId;
    const modal = $("#decModal");
    const titleEl = $("#decModalTitle");
    const indEl = $("#decModalIndicators");
    const gateBody = $("#decModalGateBody");
    const metaKv = $("#decModalMetaKv");
    if (!modal) return;
    // Show modal immediately with loading state
    if (titleEl) titleEl.textContent = `Decision ${String(decisionId).slice(0, 12)}\u2026`;
    if (indEl) indEl.innerHTML = "Loading\u2026";
    if (gateBody) gateBody.innerHTML = "";
    if (metaKv) metaKv.innerHTML = "Loading\u2026";
    modal.classList.remove("is-hidden");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    const closeBtn = $("#decModalClose");
    if (closeBtn) closeBtn.focus();
    try {
      const data = await fetchJson(`/api/v2/decisions/${encodeURIComponent(decisionId)}?mode=${encodeURIComponent(state.mode)}`, 5000);
      const dec = data.decision || data;
      const ctx = data.context || dec.context || {};
      const gates = data.gates || dec.gates || [];
      // Title
      if (titleEl) {
        const sym = dec.symbol || "\u2014";
        const evType = dec.event_type || "\u2014";
        titleEl.textContent = `${sym} \u00b7 ${evType} \u00b7 ${String(decisionId).slice(0, 12)}`;
      }
      // Indicators
      if (indEl) {
        const indFields = [
          ["price", 6], ["rsi", 2], ["adx", 2], ["adx_slope", 4],
          ["macd_hist", 6], ["ema_fast", 6], ["ema_slow", 6], ["ema_macro", 6],
          ["bb_width_ratio", 4], ["stoch_k", 2], ["stoch_d", 2],
          ["atr", 6], ["atr_slope", 4], ["volume", 2], ["vol_sma", 2],
          ["rsi_entry_threshold", 2], ["min_adx_threshold", 2],
          ["sl_price", 6], ["tp_price", 6], ["trailing_sl", 6],
        ];
        const rows = [];
        for (const [key, dec2] of indFields) {
          const val = ctx[key];
          if (val !== null && val !== undefined) {
            rows.push(kvRow(key, fmt.num(val, dec2)));
          }
        }
        // Gate flags from context
        const gateFlags = ["gate_ranging", "gate_anomaly", "gate_extension", "gate_adx",
                          "gate_volume", "gate_adx_rising", "gate_btc_alignment",
                          "bullish_alignment", "bearish_alignment"];
        const gateRows = [];
        for (const gf of gateFlags) {
          const val = ctx[gf];
          if (val !== null && val !== undefined) {
            const passed = Number(val) === 1;
            gateRows.push(kvRow(gf, passed ? "PASS" : "FAIL", passed ? "hi" : "bad"));
          }
        }
        if (gateRows.length) {
          rows.push(kvSec("Context Gates"));
          rows.push(...gateRows);
        }
        indEl.innerHTML = rows.length ? rows.join("") : "No indicator data available.";
      }
      // Gate evaluations table
      if (gateBody) {
        if (gates.length) {
          gateBody.innerHTML = gates.map((g) => {
            const passed = Number(g.gate_passed) === 1;
            return `<tr>
              <td>${esc(g.gate_name || "\u2014")}</td>
              <td class="${passed ? "dec-gate-pass" : "dec-gate-fail"}">${passed ? "PASS" : "FAIL"}</td>
              <td>${g.metric_value !== null && g.metric_value !== undefined ? esc(fmt.num(g.metric_value, 4)) : "\u2014"}</td>
              <td>${g.threshold_value !== null && g.threshold_value !== undefined ? esc(fmt.num(g.threshold_value, 4)) : "\u2014"}</td>
              <td>${esc(g.operator || "\u2014")}</td>
              <td>${esc(g.explanation || "\u2014")}</td>
            </tr>`;
          }).join("");
        } else {
          gateBody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--faint);">No gate evaluations recorded.</td></tr>';
        }
      }
      // Metadata
      if (metaKv) {
        const mRows = [];
        mRows.push(kvRow("id", dec.id || "\u2014"));
        mRows.push(kvRow("event_type", dec.event_type || "\u2014"));
        mRows.push(kvRow("status", dec.status || "\u2014"));
        mRows.push(kvRow("decision_phase", dec.decision_phase || "\u2014"));
        mRows.push(kvRow("action_taken", dec.action_taken || "\u2014"));
        if (dec.rejection_reason) mRows.push(kvRow("rejection_reason", dec.rejection_reason, "bad wrap"));
        if (dec.triggered_by) mRows.push(kvRow("triggered_by", dec.triggered_by));
        const tsMs = Number(dec.timestamp_ms || 0);
        if (tsMs) {
          const w = whenFromMs(tsMs);
          mRows.push(kvRow("timestamp", w ? `${w.ago} \u00b7 ${w.at}` : "\u2014"));
        }
        // Parent decision link
        if (dec.parent_decision_id) {
          mRows.push(`<div class="kvrow"><div class="k">PARENT</div><div class="v"><span class="dec-link" data-dec-nav="${esc(dec.parent_decision_id)}">${esc(String(dec.parent_decision_id).slice(0, 16))}\u2026</span></div></div>`);
        }
        // Trade ID
        if (dec.trade_id !== null && dec.trade_id !== undefined) {
          mRows.push(kvRow("trade_id", String(dec.trade_id)));
        }
        metaKv.innerHTML = mRows.join("");
        // Bind parent link clicks
        const links = metaKv.querySelectorAll("[data-dec-nav]");
        for (const link of links) {
          link.addEventListener("click", (e) => {
            e.stopPropagation();
            const targetId = link.dataset.decNav;
            if (targetId) decOpenDetail(targetId);
          });
        }
      }
    } catch (err) {
      if (indEl) indEl.innerHTML = `Error: ${esc(String(err.message || err))}`;
      if (metaKv) metaKv.innerHTML = `Error loading decision detail.`;
    }
  }

  function decCloseModal() {
    const modal = $("#decModal");
    if (!modal) return false;
    if (modal.classList.contains("is-hidden")) return false;
    modal.classList.add("is-hidden");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    decState.currentDecisionId = null;
    return true;
  }

  /* ── Replay ── */

  async function decReplay() {
    const decId = decState.currentDecisionId;
    if (!decId) return;
    const btn = $("#decReplayBtn");
    if (btn) { btn.textContent = "REPLAYING\u2026"; btn.disabled = true; }
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 10000);
      const r = await fetch("/api/v2/decisions/replay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision_id: decId, mode: state.mode }),
        signal: ctrl.signal,
      });
      clearTimeout(t);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      decCloseModal();
      openModal({ title: `Replay: ${decId}`, meta: `mode: ${state.mode}`, body: pretty(data) });
    } catch (err) {
      decCloseModal();
      openModal({ title: "Replay Error", meta: decId, body: String(err.message || err) });
    } finally {
      if (btn) { btn.textContent = "REPLAY DECISION"; btn.disabled = false; }
    }
  }

  /* ── JSON export ── */

  function decExportJson() {
    const data = decState.decisions;
    if (!data.length) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const now = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    a.download = `decision-trace-${state.mode}-${now}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  /* ── Clear filters ── */

  function decClearFilters() {
    const sel = (id) => { const el = $(id); if (el) el.value = ""; };
    sel("#decFilterSymbol");
    sel("#decFilterEvent");
    sel("#decFilterStatus");
    sel("#decFilterStart");
    sel("#decFilterEnd");
    decState.decisions = [];
    decState.offset = 0;
    decState.hasMore = false;
    const tl = $("#decTimeline");
    if (tl) tl.innerHTML = '<div class="dec-empty">Apply filters to load decision events.</div>';
    const summary = $("#decSummaryBar");
    if (summary) summary.textContent = "\u2014";
    const loadBtn = $("#decLoadMore");
    if (loadBtn) loadBtn.style.display = "none";
  }

  /* ── Bind decisions UI ── */

  function bindDecisionsUi() {
    const vd = $("#viewDash");
    const vDec = $("#viewDecisions");
    if (vd) vd.addEventListener("click", () => setViewTab("dashboard"));
    if (vDec) vDec.addEventListener("click", () => setViewTab("decisions"));
    const applyBtn = $("#decApplyBtn");
    if (applyBtn) applyBtn.addEventListener("click", () => decFetchDecisions(false));
    const clearBtn = $("#decClearBtn");
    if (clearBtn) clearBtn.addEventListener("click", () => decClearFilters());
    const exportBtn = $("#decExportBtn");
    if (exportBtn) exportBtn.addEventListener("click", () => decExportJson());
    const loadMore = $("#decLoadMore");
    if (loadMore) loadMore.addEventListener("click", () => decFetchDecisions(true));
    // Decision modal close
    const decModal = $("#decModal");
    const decModalClose = $("#decModalClose");
    if (decModal) decModal.addEventListener("click", (e) => { if (e.target && e.target.closest("[data-dec-modal-close]")) decCloseModal(); });
    if (decModalClose) decModalClose.addEventListener("click", () => decCloseModal());
    // Replay
    const replayBtn = $("#decReplayBtn");
    if (replayBtn) replayBtn.addEventListener("click", () => decReplay());
    // Escape key handled by consolidated handler in bindUi()
  }

  // boot
  setSeg("live");
  setFeed("trades");
  bindUi();
  bindDecisionsUi();
  initResizer();
  tick();
})();
