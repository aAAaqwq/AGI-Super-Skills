<script lang="ts">
  import { runSweep, getSweepJobs, getSweepStatus, getSweepResults, cancelSweep } from '../lib/api';
  import { getConfigLabel, LIVE_MODE } from '../lib/mode-labels';

  const candidateConfigs = ['paper1'] as const;

  let config = $state('main');
  let sweepSpec = $state('');
  let balance = $state(10000);
  let launching = $state(false);
  let error = $state('');

  let jobs: any[] = $state([]);
  let activeJob: string | null = $state(null);
  let activeStatus: any = $state(null);
  let activeResults: any = $state(null);
  let stderrLines: string[] = $state([]);

  let pollTimer: ReturnType<typeof setInterval> | null = null;

  async function launch() {
    if (!sweepSpec.trim()) { error = 'Sweep spec path required'; return; }
    launching = true;
    error = '';
    try {
      const res = await runSweep({
        config,
        sweep_spec: sweepSpec.trim(),
        initial_balance: balance,
      });
      activeJob = res.job_id;
      activeResults = null;
      stderrLines = [];
      startPolling();
      await refreshJobs();
    } catch (e: any) {
      error = e.message || 'Failed to launch';
    }
    launching = false;
  }

  async function refreshJobs() {
    try {
      jobs = await getSweepJobs();
    } catch {}
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(async () => {
      if (!activeJob) return;
      try {
        const s = await getSweepStatus(activeJob);
        activeStatus = s;
        stderrLines = s.stderr_tail || [];
        if (s.status !== 'running') {
          stopPolling();
          if (s.status === 'done') {
            try {
              activeResults = await getSweepResults(activeJob);
            } catch {}
          }
          await refreshJobs();
        }
      } catch {}
    }, 3000);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  async function cancel() {
    if (!activeJob) return;
    try { await cancelSweep(activeJob); stopPolling(); await refreshJobs(); } catch {}
  }

  function selectJob(id: string) {
    activeJob = id;
    activeResults = null;
    stderrLines = [];
    const job = jobs.find((j: any) => j.id === id);
    if (job?.status === 'running') {
      startPolling();
    } else if (job?.status === 'done') {
      getSweepResults(id).then(r => { activeResults = r; }).catch(() => {});
      getSweepStatus(id).then(s => { stderrLines = s.stderr_tail || []; }).catch(() => {});
    }
  }

  function fmtNum(n: any, d = 2): string {
    if (n == null || isNaN(n)) return '—';
    return Number(n).toFixed(d);
  }

  $effect(() => {
    refreshJobs();
    return () => stopPolling();
  });
</script>

<div class="sweep-page">
  <h1>Parameter Sweep</h1>

  <div class="launcher">
    <div class="form-row">
      <label>Config <select bind:value={config}>
        <option value="main">{getConfigLabel('main')}</option>
        <optgroup label="Live Engine">
          <option value={LIVE_MODE}>{getConfigLabel(LIVE_MODE)}</option>
        </optgroup>
        <optgroup label="Candidate Family">
          {#each candidateConfigs as option}
            <option value={option}>{getConfigLabel(option)}</option>
          {/each}
        </optgroup>
      </select></label>
      <label>Balance <input type="number" bind:value={balance} min="100" step="100" /></label>
      <label class="wide">Sweep Spec <input type="text" bind:value={sweepSpec} placeholder="config/sweep_spec.yaml" /></label>
      <button class="btn btn-primary" onclick={launch} disabled={launching || !sweepSpec.trim()}>
        {launching ? 'Launching...' : 'Run Sweep'}
      </button>
    </div>
    {#if error}
      <div class="alert alert-error">{error}</div>
    {/if}
  </div>

  <div class="content-grid">
    <div class="jobs-panel">
      <h2>Jobs</h2>
      {#if jobs.length === 0}
        <div class="empty">No sweep jobs yet</div>
      {:else}
        {#each jobs as j (j.id)}
          <button class="job-card" class:active={activeJob === j.id} onclick={() => selectJob(j.id)}>
            <div class="job-id">{j.id.slice(0, 8)}</div>
            <div class="job-meta">
              <span class="status-pill {j.status}">{j.status}</span>
              <span class="job-time">{j.created_at ? new Date(j.created_at).toLocaleTimeString() : ''}</span>
            </div>
          </button>
        {/each}
      {/if}
    </div>

    <div class="result-panel">
      {#if activeJob && activeStatus?.status === 'running'}
        <div class="progress-section">
          <div class="progress-header">
            <span>Running sweep...</span>
            <button class="btn btn-secondary" onclick={cancel}>Cancel</button>
          </div>
          <pre class="stderr-log">{stderrLines.join('\n')}</pre>
        </div>
      {:else if activeResults}
        <div class="result-section">
          <h2>Sweep Results</h2>
          {#if Array.isArray(activeResults)}
            <table class="results-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Config ID</th>
                  <th>Net PnL</th>
                  <th>Win Rate</th>
                  <th>Max DD</th>
                  <th>Sharpe</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                {#each activeResults as r, i}
                  <tr>
                    <td>{i + 1}</td>
                    <td class="mono">{r.config_id ?? r.id ?? '—'}</td>
                    <td>${fmtNum(r.report?.net_pnl ?? r.net_pnl)}</td>
                    <td>{fmtNum(((r.report?.win_rate ?? r.win_rate ?? 0) * 100), 1)}%</td>
                    <td>{fmtNum(r.report?.max_drawdown_pct ?? r.max_drawdown_pct, 1)}%</td>
                    <td>{fmtNum(r.report?.sharpe_ratio ?? r.sharpe_ratio)}</td>
                    <td>{r.report?.total_trades ?? r.total_trades ?? '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <pre class="result-json">{JSON.stringify(activeResults, null, 2)}</pre>
          {/if}
        </div>
      {:else if activeStatus?.error}
        <div class="alert alert-error">{activeStatus.error}</div>
        {#if stderrLines.length > 0}
          <pre class="stderr-log">{stderrLines.join('\n')}</pre>
        {/if}
      {:else}
        <div class="empty">Select a job or run a new sweep</div>
      {/if}
    </div>
  </div>
</div>

<style>
  /* ─── Page entry ─── */
  .sweep-page {
    max-width: 1400px;
    animation: slideUp 0.3s ease;
  }

  /* ─── Typography ─── */
  h1 {
    font-size: 20px;
    font-weight: 600;
    margin-bottom: var(--sp-md);
    letter-spacing: -0.01em;
  }
  h2 {
    font-size: 15px;
    font-weight: 600;
    margin-bottom: var(--sp-sm);
  }

  /* ─── Launcher ─── */
  .launcher {
    margin-bottom: var(--sp-lg);
  }

  .form-row {
    display: flex;
    gap: var(--sp-md);
    align-items: end;
    flex-wrap: wrap;
  }

  .form-row label {
    display: flex;
    flex-direction: column;
    gap: var(--sp-xs);
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
    letter-spacing: 0.02em;
  }

  .form-row label.wide {
    flex: 1;
    min-width: 200px;
  }

  .form-row input,
  .form-row select {
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 12px;
    border-radius: var(--radius-md);
    font-size: 13px;
    transition: border-color var(--t-fast), box-shadow var(--t-fast);
  }

  .form-row input:focus,
  .form-row select:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-bg);
  }

  /* ─── Buttons ─── */
  .btn {
    padding: 8px 16px;
    border: none;
    border-radius: var(--radius-md);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background var(--t-fast) var(--ease-out),
                transform var(--t-fast) var(--ease-out);
    letter-spacing: 0.02em;
  }
  .btn:hover {
    transform: translateY(-1px);
  }
  .btn:active {
    transform: scale(0.97);
  }
  .btn:disabled {
    opacity: 0.35;
    cursor: default;
    pointer-events: none;
    transform: none;
  }
  .btn-primary {
    background: var(--accent);
    color: #fff;
  }
  .btn-secondary {
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
  }
  .btn-secondary:hover {
    background: var(--surface-hover);
  }

  /* ─── Alerts ─── */
  .alert {
    padding: 10px var(--sp-md);
    border-radius: var(--radius-md);
    font-size: 13px;
    margin-top: var(--sp-sm);
  }
  .alert-error {
    background: var(--red-bg);
    color: var(--red);
    border: 1px solid rgba(255, 107, 107, 0.25);
  }

  /* ─── Content grid ─── */
  .content-grid {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: var(--sp-md);
  }

  /* ─── Jobs panel ─── */
  .jobs-panel {
    border-right: 1px solid var(--border);
    padding-right: var(--sp-md);
  }

  .job-card {
    display: block;
    width: 100%;
    text-align: left;
    padding: 10px 12px;
    background: none;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    cursor: pointer;
    margin-bottom: var(--sp-xs);
    color: var(--text);
    transition: background var(--t-fast) var(--ease-out),
                border-color var(--t-fast) var(--ease-out);
  }
  .job-card:hover {
    background: var(--surface);
  }
  .job-card.active {
    border-color: var(--accent);
    background: var(--accent-bg);
  }

  .job-id {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: -0.01em;
  }
  .job-meta {
    display: flex;
    gap: var(--sp-sm);
    align-items: center;
    margin-top: var(--sp-xs);
  }
  .job-time {
    font-size: 11px;
    color: var(--text-muted);
  }

  /* ─── Status pills ─── */
  .status-pill {
    font-size: 10px;
    padding: 2px 8px;
    border-radius: var(--radius-sm, 4px);
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  .status-pill.running {
    background: var(--accent-bg);
    color: var(--accent);
  }
  .status-pill.done {
    background: var(--green-bg);
    color: var(--green);
  }
  .status-pill.failed {
    background: var(--red-bg);
    color: var(--red);
  }
  .status-pill.cancelled {
    background: var(--yellow-bg);
    color: var(--yellow);
  }

  /* ─── Progress ─── */
  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--sp-sm);
  }

  .stderr-log {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--sp-md);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    line-height: 1.6;
    max-height: 400px;
    overflow-y: auto;
    white-space: pre-wrap;
    color: var(--text-muted);
  }

  /* ─── Results table ─── */
  .results-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .results-table th {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .results-table td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-subtle);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
  }
  .results-table tbody tr {
    transition: background var(--t-fast);
  }
  .results-table tbody tr:hover {
    background: var(--surface);
  }

  .mono {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: -0.01em;
  }

  /* ─── Result JSON fallback ─── */
  .result-json {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--sp-md);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    max-height: 600px;
    overflow: auto;
    white-space: pre-wrap;
  }

  /* ─── Empty state ─── */
  .empty {
    color: var(--text-muted);
    font-style: italic;
    padding: var(--sp-lg) 0;
  }

  /* ─── Mobile ─── */
  @media (max-width: 768px) {
    .content-grid {
      grid-template-columns: 1fr;
    }

    .jobs-panel {
      border-right: none;
      border-bottom: 1px solid var(--border);
      padding-right: 0;
      padding-bottom: var(--sp-md);
    }

    .form-row {
      flex-direction: column;
      gap: var(--sp-sm);
    }

    .form-row label,
    .form-row label.wide {
      width: 100%;
      flex: unset;
      min-width: unset;
    }

    .form-row input,
    .form-row select {
      width: 100%;
    }

    .btn {
      padding: 12px 16px;
      width: 100%;
      text-align: center;
    }

    .results-table {
      font-size: 12px;
    }
    .results-table th,
    .results-table td {
      padding: 6px 8px;
    }

    /* Horizontal scroll for wide tables */
    .result-section {
      overflow-x: auto;
    }
  }
</style>
