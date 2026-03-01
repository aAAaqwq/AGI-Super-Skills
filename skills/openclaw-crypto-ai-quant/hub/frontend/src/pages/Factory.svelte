<script lang="ts">
  import { getFactoryRuns, getFactoryRun, getFactoryReport, getFactoryCandidates } from '../lib/api';

  let runs: any[] = $state([]);
  let loading = $state(true);
  let error = $state('');

  let selectedRun: any = $state(null);
  let runDetail: any = $state(null);
  let report: any = $state(null);
  let candidates: any[] = $state([]);
  let loadingDetail = $state(false);

  async function loadRuns() {
    loading = true;
    try {
      runs = await getFactoryRuns();
    } catch (e: any) {
      error = e.message || 'Failed to load runs';
    }
    loading = false;
  }

  async function selectRun(run: any) {
    selectedRun = run;
    loadingDetail = true;
    report = null;
    candidates = [];
    runDetail = null;
    try {
      const [detail, rep, cands] = await Promise.all([
        getFactoryRun(run.date, run.run_id),
        run.has_report ? getFactoryReport(run.date, run.run_id).catch(() => null) : Promise.resolve(null),
        getFactoryCandidates(run.date, run.run_id).catch(() => []),
      ]);
      runDetail = detail;
      report = rep;
      candidates = cands;
    } catch (e: any) {
      error = e.message;
    }
    loadingDetail = false;
  }

  function fmtNum(n: any, d = 2): string {
    if (n == null || isNaN(n)) return '—';
    return Number(n).toFixed(d);
  }

  $effect(() => { loadRuns(); });
</script>

<div class="page">
  <h1>Factory</h1>

  {#if error}
    <div class="alert alert-error">{error}</div>
  {/if}

  <div class="content-grid">
    <div class="runs-panel">
      <h2>Runs</h2>
      {#if loading}
        <div class="empty-state">Loading...</div>
      {:else if runs.length === 0}
        <div class="empty-state">No factory runs found</div>
      {:else}
        {#each runs as r (r.date + '/' + r.run_id)}
          <button
            class="run-card"
            class:active={selectedRun?.run_id === r.run_id && selectedRun?.date === r.date}
            onclick={() => selectRun(r)}
          >
            <div class="run-date">{r.date}</div>
            <div class="run-id">{r.run_id}</div>
            <div class="run-meta">
              <span class="pill-blue">{r.profile}</span>
              {#if r.has_report}
                <span class="pill-green">report</span>
              {/if}
            </div>
          </button>
        {/each}
      {/if}
    </div>

    <div class="detail-panel">
      {#if loadingDetail}
        <div class="empty-state">Loading run detail...</div>
      {:else if selectedRun && runDetail}
        <h2>{selectedRun.run_id}</h2>
        <div class="meta-section">
          <div class="meta-row"><span class="meta-label">Date</span><span>{selectedRun.date}</span></div>
          <div class="meta-row"><span class="meta-label">Profile</span><span>{runDetail.metadata?.args?.profile ?? '—'}</span></div>
          <div class="meta-row"><span class="meta-label">Candidates</span><span>{runDetail.metadata?.args?.num_candidates ?? '—'}</span></div>
          <div class="meta-row"><span class="meta-label">Subdirs</span><span>{runDetail.subdirs?.join(', ') ?? '—'}</span></div>
        </div>

        {#if report}
          <h3>Report</h3>
          {#if report.candidates && Array.isArray(report.candidates)}
            <div class="table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Config</th>
                    <th>Score</th>
                    <th>PnL</th>
                    <th>Trades</th>
                    <th>Win%</th>
                    <th>DD%</th>
                    <th>Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {#each report.candidates as c, i}
                    <tr>
                      <td>{i + 1}</td>
                      <td class="mono">{c.config_id ?? c.id ?? '—'}</td>
                      <td>{fmtNum(c.score_v1 ?? c.score)}</td>
                      <td>${fmtNum(c.pnl ?? c.net_pnl)}</td>
                      <td>{c.trades ?? c.total_trades ?? '—'}</td>
                      <td>{fmtNum((c.win_rate ?? 0) * 100, 1)}%</td>
                      <td>{fmtNum(c.max_drawdown_pct ?? c.drawdown_pct, 1)}%</td>
                      <td>
                        <span class="verdict" class:pass={c.verdict === 'PASS' || c.verdict === 'pass'} class:fail={c.verdict !== 'PASS' && c.verdict !== 'pass'}>
                          {c.verdict ?? '—'}
                        </span>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <pre class="code-block">{JSON.stringify(report, null, 2)}</pre>
          {/if}
        {/if}

        {#if candidates.length > 0}
          <h3>Config Files</h3>
          <div class="config-list">
            {#each candidates as c}
              <div class="config-item">
                <span class="mono">{c.filename}</span>
                <span class="config-size">{(c.size / 1024).toFixed(1)} KB</span>
              </div>
            {/each}
          </div>
        {/if}
      {:else}
        <div class="empty-state">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--text-dim)" stroke-width="1"><path d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>
          <p>Select a factory run</p>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .page { max-width: 1400px; animation: slideUp 0.3s ease; }

  h1 { font-size: 20px; font-weight: 700; margin-bottom: var(--sp-md); letter-spacing: -0.02em; }
  h2 { font-size: 15px; font-weight: 600; margin-bottom: var(--sp-sm); }
  h3 {
    font-size: 10px; font-weight: 600; margin: var(--sp-md) 0 var(--sp-sm);
    color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.08em;
  }

  .alert {
    padding: 10px 14px; border-radius: var(--radius-md);
    font-size: 13px; margin-bottom: 12px; animation: slideUp 0.2s ease;
  }
  .alert-error {
    background: var(--red-bg); color: var(--red);
    border: 1px solid rgba(255,107,107,0.2);
  }

  .content-grid { display: grid; grid-template-columns: 260px 1fr; gap: var(--sp-md); }

  .runs-panel {
    border-right: 1px solid var(--border);
    padding-right: var(--sp-md);
    max-height: 80vh;
    overflow-y: auto;
  }

  .run-card {
    display: block; width: 100%; text-align: left;
    padding: 10px 12px; background: none; border: 1px solid transparent;
    border-radius: var(--radius-md); cursor: pointer; margin-bottom: 4px;
    color: var(--text); transition: all var(--t-fast);
  }
  .run-card:hover { background: var(--surface); }
  .run-card.active { border-color: var(--accent); background: var(--accent-bg); }

  .run-date { font-size: 11px; color: var(--text-dim); font-family: 'IBM Plex Mono', monospace; }
  .run-id { font-family: 'IBM Plex Mono', monospace; font-size: 12px; margin-top: 2px; font-weight: 500; }
  .run-meta { display: flex; gap: 6px; margin-top: 6px; }

  .pill-blue {
    font-size: 10px; padding: 2px 8px; border-radius: var(--radius-sm);
    background: var(--accent-bg); color: var(--accent); font-weight: 600; letter-spacing: 0.02em;
  }
  .pill-green {
    font-size: 10px; padding: 2px 8px; border-radius: var(--radius-sm);
    background: var(--green-bg); color: var(--green); font-weight: 600; letter-spacing: 0.02em;
  }

  .meta-section { margin-bottom: var(--sp-md); }
  .meta-row {
    display: flex; gap: 12px; padding: 5px 0; font-size: 13px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .meta-label { color: var(--text-dim); min-width: 100px; font-weight: 500; font-size: 12px; }

  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }

  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border);
    color: var(--text-dim); font-weight: 600; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.06em;
  }
  .data-table td { padding: 10px 12px; border-bottom: 1px solid var(--border-subtle); }

  .verdict {
    font-size: 10px; padding: 2px 8px; border-radius: var(--radius-sm);
    font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
  }
  .verdict.pass { background: var(--green-bg); color: var(--green); }
  .verdict.fail { background: var(--red-bg); color: var(--red); }

  .code-block {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 16px;
    font-family: 'IBM Plex Mono', monospace; font-size: 12px;
    max-height: 500px; overflow: auto; white-space: pre-wrap;
  }

  .config-list { display: flex; flex-direction: column; gap: 4px; }
  .config-item {
    display: flex; justify-content: space-between; padding: 8px 12px;
    font-size: 13px; background: var(--surface); border-radius: var(--radius-md);
    border: 1px solid var(--border-subtle);
  }
  .config-size { color: var(--text-dim); font-size: 12px; font-family: 'IBM Plex Mono', monospace; }

  .empty-state {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 8px; padding: 40px 0;
    color: var(--text-dim); font-size: 13px;
  }

  @media (max-width: 768px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
    .runs-panel {
      border-right: none;
      border-bottom: 1px solid var(--border);
      padding-right: 0;
      padding-bottom: var(--sp-md);
      max-height: 40vh;
    }
  }
</style>
