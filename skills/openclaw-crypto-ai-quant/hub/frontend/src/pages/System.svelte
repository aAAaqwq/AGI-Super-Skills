<script lang="ts">
  import { getSystemServices, serviceAction, getDbStats, getDiskUsage, getServiceLogs } from '../lib/api';

  let services: any[] = $state([]);
  let dbStats: any[] = $state([]);
  let disk: any[] = $state([]);
  let loading = $state(true);
  let actionError = $state('');
  let actionSuccess = $state('');

  let logService = $state('');
  let logLines: string = $state('');
  let loadingLogs = $state(false);

  let tab: 'services' | 'databases' | 'logs' | 'disk' = $state('services');

  async function refresh() {
    loading = true;
    try {
      const [svcs, stats, d] = await Promise.all([
        getSystemServices(),
        getDbStats(),
        getDiskUsage(),
      ]);
      services = svcs;
      dbStats = stats;
      disk = d;
    } catch {}
    loading = false;
  }

  async function doAction(name: string, action: string) {
    actionError = '';
    actionSuccess = '';
    try {
      const res = await serviceAction(name, action);
      if (res.ok) {
        actionSuccess = `${action} ${name}: OK`;
      } else {
        actionError = `${action} ${name}: ${res.stderr || 'failed'}`;
      }
      setTimeout(() => { actionSuccess = ''; }, 5000);
      await refresh();
    } catch (e: any) {
      actionError = e.message;
    }
  }

  async function loadLogs() {
    if (!logService) return;
    loadingLogs = true;
    try {
      const res = await getServiceLogs(logService, 100);
      logLines = res.log || '';
    } catch (e: any) {
      logLines = `Error: ${e.message}`;
    }
    loadingLogs = false;
  }

  $effect(() => { refresh(); });
</script>

<div class="page">
  <h1>System</h1>

  {#if actionError}
    <div class="alert alert-error">{actionError}</div>
  {/if}
  {#if actionSuccess}
    <div class="alert alert-success">{actionSuccess}</div>
  {/if}

  <div class="tabs">
    <button class="tab" class:active={tab === 'services'} onclick={() => tab = 'services'}>Services</button>
    <button class="tab" class:active={tab === 'databases'} onclick={() => tab = 'databases'}>Databases</button>
    <button class="tab" class:active={tab === 'logs'} onclick={() => tab = 'logs'}>Logs</button>
    <button class="tab" class:active={tab === 'disk'} onclick={() => tab = 'disk'}>Disk</button>
  </div>

  {#if loading}
    <div class="empty-state">Loading...</div>
  {:else if tab === 'services'}
    <div class="services-grid">
      {#each services as svc (svc.name)}
        <div class="service-card" class:svc-active={svc.active === 'active'} class:svc-failed={svc.active === 'failed'}>
          <div class="svc-header">
            <div class="svc-status-dot" class:alive={svc.active === 'active'} class:dead={svc.active === 'failed'}></div>
            <span class="svc-name">{svc.name}</span>
          </div>
          <div class="svc-meta">
            <span>PID: <strong>{svc.pid || '—'}</strong></span>
            <span>State: <strong>{svc.sub}</strong></span>
          </div>
          <div class="svc-actions">
            <button class="btn-sm" onclick={() => doAction(svc.name, 'restart')}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg>
              Restart
            </button>
            {#if svc.active !== 'active'}
              <button class="btn-sm btn-start" onclick={() => doAction(svc.name, 'start')}>Start</button>
            {:else}
              <button class="btn-sm btn-stop" onclick={() => doAction(svc.name, 'stop')}>Stop</button>
            {/if}
          </div>
        </div>
      {/each}
    </div>

  {:else if tab === 'databases'}
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Database</th>
            <th>Size</th>
            <th>Modified</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {#each dbStats as db}
            <tr>
              <td class="mono">{db.label}</td>
              <td class="mono">{db.size_mb} MB</td>
              <td>{db.modified ? new Date(db.modified).toLocaleString() : '—'}</td>
              <td>
                <span class="status-chip" class:ok={db.exists} class:bad={!db.exists}>
                  {db.exists ? 'exists' : 'missing'}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

  {:else if tab === 'logs'}
    <div class="logs-section">
      <div class="logs-controls">
        <select bind:value={logService}>
          <option value="">select service</option>
          {#each services as svc}
            <option value={svc.name}>{svc.name}</option>
          {/each}
        </select>
        <button class="btn btn-primary" onclick={loadLogs} disabled={!logService || loadingLogs}>
          {loadingLogs ? 'Loading...' : 'Load Logs'}
        </button>
      </div>
      {#if logLines}
        <pre class="log-output">{logLines}</pre>
      {/if}
    </div>

  {:else if tab === 'disk'}
    <div class="disk-section">
      {#each disk as d}
        <div class="disk-row">
          <span class="disk-label">{d.label}</span>
          <span class="disk-size">{d.size}</span>
          <span class="disk-path mono">{d.path}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page { max-width: 1200px; animation: slideUp 0.3s ease; }

  h1 { font-size: 20px; font-weight: 700; margin-bottom: var(--sp-md); letter-spacing: -0.02em; }

  .alert {
    padding: 10px 14px; border-radius: var(--radius-md);
    font-size: 13px; margin-bottom: 12px; animation: slideUp 0.2s ease;
  }
  .alert-error { background: var(--red-bg); color: var(--red); border: 1px solid rgba(255,107,107,0.2); }
  .alert-success { background: var(--green-bg); color: var(--green); border: 1px solid rgba(81,207,102,0.2); }

  .tabs {
    display: flex; gap: 2px; margin-bottom: var(--sp-md);
    background: var(--bg); border-radius: var(--radius-md);
    padding: 3px; border: 1px solid var(--border); width: fit-content;
  }
  .tab {
    padding: 8px 16px; background: transparent; border: none;
    color: var(--text-muted); font-size: 13px; font-weight: 500;
    cursor: pointer; border-radius: 5px; transition: all var(--t-fast);
  }
  .tab.active { color: var(--accent); background: var(--accent-bg); }

  .services-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 10px;
  }

  .service-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 14px;
    transition: border-color var(--t-fast);
  }
  .service-card.svc-active { border-color: rgba(81,207,102,0.2); }
  .service-card.svc-failed { border-color: rgba(255,107,107,0.2); }

  .svc-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 8px;
  }
  .svc-status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--text-dim); flex-shrink: 0;
  }
  .svc-status-dot.alive {
    background: var(--green);
    box-shadow: 0 0 6px var(--green);
    animation: pulse 2s ease-in-out infinite;
  }
  .svc-status-dot.dead { background: var(--red); }

  .svc-name {
    font-size: 12px; font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    word-break: break-all;
  }
  .svc-meta {
    font-size: 11px; color: var(--text-muted);
    display: flex; gap: 16px; margin-bottom: 10px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .svc-meta strong { color: var(--text); font-weight: 500; }
  .svc-actions { display: flex; gap: 6px; }

  .btn-sm {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 6px 12px; border: 1px solid var(--border); border-radius: var(--radius-md);
    background: var(--surface); color: var(--text); font-size: 11px;
    font-weight: 500; cursor: pointer; transition: all var(--t-fast);
  }
  .btn-sm:hover { background: var(--surface-hover); }
  .btn-sm:active { transform: scale(0.97); }
  .btn-start { color: var(--green); border-color: rgba(81,207,102,0.3); }
  .btn-stop { color: var(--red); border-color: rgba(255,107,107,0.3); }

  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }

  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--border);
    color: var(--text-dim); font-weight: 600; font-size: 10px;
    text-transform: uppercase; letter-spacing: 0.06em;
  }
  .data-table td { padding: 10px 14px; border-bottom: 1px solid var(--border-subtle); }

  .status-chip {
    font-size: 10px; padding: 2px 8px; border-radius: var(--radius-sm);
    font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
  }
  .status-chip.ok { background: var(--green-bg); color: var(--green); }
  .status-chip.bad { background: var(--red-bg); color: var(--red); }

  .logs-controls {
    display: flex; gap: 12px; align-items: end; margin-bottom: 12px;
    flex-wrap: wrap;
  }
  .logs-controls select {
    background: var(--surface); border: 1px solid var(--border);
    color: var(--text); padding: 8px 12px; border-radius: var(--radius-md);
    font-size: 12px; font-family: 'IBM Plex Mono', monospace;
    min-width: 240px;
  }

  .btn {
    padding: 8px 16px; border: none; border-radius: var(--radius-md);
    font-size: 12px; font-weight: 600; cursor: pointer;
    transition: all var(--t-fast);
  }
  .btn:disabled { opacity: 0.35; cursor: default; }
  .btn:active:not(:disabled) { transform: scale(0.97); }
  .btn-primary { background: var(--accent); color: var(--bg); }

  .log-output {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 16px;
    font-family: 'IBM Plex Mono', monospace; font-size: 11px; line-height: 1.6;
    max-height: 600px; overflow-y: auto; white-space: pre-wrap;
  }

  .disk-section { display: flex; flex-direction: column; gap: 8px; }
  .disk-row {
    display: flex; gap: 16px; align-items: center; padding: 12px 16px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius-lg); transition: border-color var(--t-fast);
  }
  .disk-row:hover { border-color: var(--text-dim); }
  .disk-label { font-weight: 600; font-size: 13px; min-width: 120px; }
  .disk-size {
    font-size: 18px; font-weight: 700; min-width: 80px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .disk-path { color: var(--text-dim); font-size: 12px; }

  .empty-state {
    color: var(--text-dim); padding: 40px 0;
    text-align: center; font-size: 13px;
  }

  @media (max-width: 768px) {
    .tabs { width: 100%; }
    .tab { flex: 1; text-align: center; padding: 10px 8px; }
    .services-grid {
      grid-template-columns: 1fr;
    }
    .logs-controls { flex-direction: column; }
    .logs-controls select { min-width: 0; width: 100%; }
    .btn { padding: 12px 16px; }
    .disk-row { flex-wrap: wrap; gap: 8px; }
    .disk-label { min-width: auto; }
    .disk-path { width: 100%; }
  }
</style>
