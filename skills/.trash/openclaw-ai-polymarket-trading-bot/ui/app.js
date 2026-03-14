let lastSnapshot = null;
let marketRemainingSec = null;

const statusEl = document.getElementById('status');
const snapshotEl = document.getElementById('snapshot');
const historyEl = document.getElementById('history');
const statsEl = document.getElementById('stats');
const whaleStatsEl = document.getElementById('whaleStats');
const whalesEl = document.getElementById('whales');
const entryEl = document.getElementById('entryYes');
const delayEl = document.getElementById('delaySec');
const pendingInfoEl = document.getElementById('pendingInfo');

const history = JSON.parse(localStorage.getItem('pm_compare_history') || '[]');
let pending = JSON.parse(localStorage.getItem('pm_compare_pending') || 'null');

function sideFromProb(p){ return p >= 0.5 ? 'YES' : 'NO'; }
function fmt(n,d=4){ return Number(n).toFixed(d); }
function fmtCountdown(sec){
  const s = Math.max(0, Number(sec||0));
  const mm = String(Math.floor(s/60)).padStart(1,'0');
  const ss = String(s%60).padStart(2,'0');
  return `${mm}:${ss}`;
}

async function refreshPrediction(){
  statusEl.textContent = 'loading...';
  const res = await fetch('/api/prediction');
  const data = await res.json();
  lastSnapshot = data;

  const p5 = data.prediction.pUp5m;
  const side = sideFromProb(p5);

  const meta = data.marketMeta || {};
  const remain = Number(meta.remainingSec ?? -1);
  marketRemainingSec = remain >= 0 ? remain : null;
  const remainText = remain >= 0 ? fmtCountdown(remain) : 'n/a';

  snapshotEl.innerHTML = `
    <div><strong>Market</strong><br>${data.marketId}</div>
    <div><strong>Current YES</strong><br>${fmt(data.currentYes)}</div>
    <div><strong>Pred Side (5m)</strong><br>${side}</div>
    <div><strong>P(UP 5m)</strong><br>${fmt(p5,3)}</div>
    <div><strong>Confidence</strong><br>${fmt(data.prediction.confidence,2)}</div>
    <div><strong>Live Slug</strong><br>${meta.slug || '-'}</div>
    <div><strong>Ends In</strong><br><span id="remainTimer">${remainText}</span></div>
    <div><strong>Question</strong><br>${meta.question || '-'}</div>
  `;

  const whale = data.whale || {};
  whaleStatsEl.textContent = `Whale Net YES: $${fmt(whale.netYesNotional || 0,2)} | Gross: $${fmt(whale.grossNotional || 0,2)} | Trades sampled: ${whale.tradeCount || 0}`;
  const wallets = whale.topWallets || [];
  whalesEl.innerHTML = wallets.map((w) => {
    const bias = w.netYes > 0 ? 'YES' : w.netYes < 0 ? 'NO' : 'NEUTRAL';
    return `<tr><td>${w.wallet.slice(0,6)}...${w.wallet.slice(-4)}</td><td>${fmt(w.netYes,2)}</td><td>${fmt(w.gross,2)}</td><td>${bias}</td></tr>`;
  }).join('') || '<tr><td colspan="4" class="muted">No whale wallets in current sample.</td></tr>';

  entryEl.value = fmt(data.currentYes);
  statusEl.textContent = 'ready';
}

function renderHistory(){
  historyEl.innerHTML = history.slice().reverse().map((x) => `
    <tr>
      <td>${new Date(x.ts).toLocaleString()}</td>
      <td>${x.marketId}</td>
      <td>${x.predSide}</td>
      <td>${fmt(x.entryYes)}</td>
      <td>${fmt(x.exitYes)}</td>
      <td>${x.actualSide}</td>
      <td>${x.correct ? '✅' : '❌'}</td>
    </tr>
  `).join('');

  const total = history.length;
  const win = history.filter((x)=>x.correct).length;
  const acc = total ? (win/total*100).toFixed(1) : '0.0';
  statsEl.textContent = `Total: ${total} | Correct: ${win} | Accuracy: ${acc}%`;
}

document.getElementById('refresh').addEventListener('click', refreshPrediction);

document.getElementById('startAuto').addEventListener('click', () => {
  if (!lastSnapshot) return alert('Get prediction first');
  if (pending) return alert('An auto-compare is already pending');

  const entryYes = Number(entryEl.value);
  const delaySec = Number(delayEl.value || 300);
  if (Number.isNaN(entryYes) || entryYes <= 0 || entryYes >= 1) return alert('Invalid entry YES price');
  if (Number.isNaN(delaySec) || delaySec < 10) return alert('Delay must be at least 10 seconds');

  pending = {
    marketId: lastSnapshot.marketId,
    predSide: sideFromProb(lastSnapshot.prediction.pUp5m),
    entryYes,
    startedAt: Date.now(),
    settleAt: Date.now() + delaySec * 1000
  };
  localStorage.setItem('pm_compare_pending', JSON.stringify(pending));
  renderPending();
});

async function settlePendingIfReady() {
  if (!pending) return;
  if (Date.now() < pending.settleAt) {
    renderPending();
    return;
  }

  try {
    const res = await fetch('/api/prediction');
    const data = await res.json();
    const exitYes = Number(data.currentYes);

    const actualSide = exitYes >= pending.entryYes ? 'YES' : 'NO';
    const row = {
      ts: Date.now(),
      marketId: pending.marketId,
      predSide: pending.predSide,
      actualSide,
      entryYes: pending.entryYes,
      exitYes,
      correct: pending.predSide === actualSide
    };

    history.push(row);
    localStorage.setItem('pm_compare_history', JSON.stringify(history));
    pending = null;
    localStorage.removeItem('pm_compare_pending');
    renderHistory();
    renderPending();
    await refreshPrediction();
  } catch (e) {
    console.error('auto settle error', e);
  }
}

function renderPending() {
  if (!pending) {
    pendingInfoEl.textContent = 'No pending auto-compare.';
    return;
  }
  const left = Math.max(0, Math.ceil((pending.settleAt - Date.now()) / 1000));
  pendingInfoEl.textContent = `Pending ${pending.marketId} | Pred: ${pending.predSide} | Entry YES: ${fmt(pending.entryYes)} | settles in ${left}s`;
}

function tickMarketTimer() {
  if (marketRemainingSec == null) return;
  marketRemainingSec = Math.max(0, marketRemainingSec - 1);
  const el = document.getElementById('remainTimer');
  if (el) el.textContent = fmtCountdown(marketRemainingSec);

  // auto-refresh market snapshot when timer reaches zero
  if (marketRemainingSec === 0) {
    refreshPrediction().catch(() => {});
  }
}

renderHistory();
renderPending();
refreshPrediction();
setInterval(settlePendingIfReady, 3000);
setInterval(renderPending, 1000);
setInterval(tickMarketTimer, 1000);
