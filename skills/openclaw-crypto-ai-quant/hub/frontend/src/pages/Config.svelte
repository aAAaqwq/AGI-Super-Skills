<script lang="ts">
  import { getConfigRaw, putConfig, reloadConfig, getConfigHistory, getConfigDiff, getConfigFiles } from '../lib/api';

  let files: any[] = $state([]);
  let selectedFile = $state('main');
  let yamlText = $state('');
  let originalText = $state('');
  let dirty = $derived(yamlText !== originalText);
  let saving = $state(false);
  let loading = $state(false);
  let error = $state('');
  let success = $state('');
  let tab: 'editor' | 'history' | 'diff' = $state('editor');

  let history: any[] = $state([]);
  let loadingHistory = $state(false);

  let diffA = $state('');
  let diffB = $state('current');
  let diffResult: string[] = $state([]);
  let loadingDiff = $state(false);

  async function loadFiles() {
    try { files = await getConfigFiles(); } catch {}
  }

  async function loadConfig() {
    loading = true;
    error = '';
    try {
      const raw = await getConfigRaw(selectedFile);
      yamlText = raw;
      originalText = raw;
    } catch (e: any) {
      error = e.message || 'Failed to load config';
    } finally {
      loading = false;
    }
  }

  async function save() {
    saving = true; error = ''; success = '';
    try {
      const res = await putConfig(yamlText, selectedFile);
      originalText = yamlText;
      success = `Saved! Backup: ${res.backup || 'none'}`;
      setTimeout(() => { success = ''; }, 5000);
    } catch (e: any) {
      error = e.message || 'Failed to save';
    } finally {
      saving = false;
    }
  }

  async function saveAndReload() {
    await save();
    if (!error) {
      try {
        await reloadConfig(selectedFile);
        success = 'Saved & hot-reload triggered!';
        setTimeout(() => { success = ''; }, 5000);
      } catch (e: any) {
        error = `Saved but reload failed: ${e.message}`;
      }
    }
  }

  async function loadHistory() {
    loadingHistory = true;
    try { history = await getConfigHistory(selectedFile); } catch {}
    loadingHistory = false;
  }

  async function loadDiff() {
    if (!diffA) return;
    loadingDiff = true;
    try {
      const res = await getConfigDiff(diffA, diffB, selectedFile);
      diffResult = res.diff || [];
    } catch (e: any) {
      diffResult = [`Error: ${e.message}`];
    }
    loadingDiff = false;
  }

  function colorDiffLine(line: string): string {
    const escaped = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    if (line.startsWith('+')) return `<span class="diff-add">${escaped}</span>`;
    if (line.startsWith('-')) return `<span class="diff-del">${escaped}</span>`;
    return `<span class="diff-ctx">${escaped}</span>`;
  }

  $effect(() => { loadFiles(); loadConfig(); });

  function onFileChange(e: Event) {
    selectedFile = (e.target as HTMLSelectElement).value;
    loadConfig();
    if (tab === 'history') loadHistory();
  }
</script>

<div class="page">
  <div class="page-header">
    <h1>Config</h1>
    <select class="file-select" onchange={onFileChange} value={selectedFile}>
      {#each files as f}
        <option value={f.variant} disabled={!f.exists}>
          {f.variant}{f.exists ? '' : ' (missing)'}
        </option>
      {/each}
    </select>
  </div>

  <div class="tabs">
    <button class="tab" class:active={tab === 'editor'} onclick={() => tab = 'editor'}>Editor</button>
    <button class="tab" class:active={tab === 'history'} onclick={() => { tab = 'history'; loadHistory(); }}>History</button>
    <button class="tab" class:active={tab === 'diff'} onclick={() => { tab = 'diff'; loadHistory(); }}>Diff</button>
  </div>

  {#if error}
    <div class="alert alert-error">{error}</div>
  {/if}
  {#if success}
    <div class="alert alert-success">{success}</div>
  {/if}

  {#if tab === 'editor'}
    <div class="editor-section">
      <div class="editor-toolbar">
        <span class="file-label">{selectedFile}.yaml</span>
        {#if dirty}
          <span class="dirty-badge">unsaved</span>
        {/if}
        <div class="toolbar-actions">
          <button class="btn btn-ghost" onclick={() => { yamlText = originalText; }} disabled={!dirty}>Revert</button>
          <button class="btn btn-primary" onclick={save} disabled={!dirty || saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button class="btn btn-green" onclick={saveAndReload} disabled={!dirty || saving}>
            Save & Reload
          </button>
        </div>
      </div>
      {#if loading}
        <div class="loading-state">Loading config...</div>
      {:else}
        <textarea
          class="yaml-editor"
          bind:value={yamlText}
          spellcheck="false"
          wrap="off"
        ></textarea>
      {/if}
    </div>

  {:else if tab === 'history'}
    <div class="history-section">
      {#if loadingHistory}
        <div class="loading-state">Loading history...</div>
      {:else if history.length === 0}
        <div class="empty-state">No backups yet for {selectedFile}</div>
      {:else}
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Backup File</th><th>Modified</th><th>Size</th></tr>
            </thead>
            <tbody>
              {#each history as h}
                <tr>
                  <td class="mono">{h.filename}</td>
                  <td>{h.modified ? new Date(h.modified).toLocaleString() : '—'}</td>
                  <td>{(h.size / 1024).toFixed(1)} KB</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

  {:else if tab === 'diff'}
    <div class="diff-section">
      <div class="diff-controls">
        <label>
          <span class="label-text">Version A</span>
          <select bind:value={diffA}>
            <option value="">select backup</option>
            {#each history as h}
              <option value={h.filename}>{h.filename}</option>
            {/each}
          </select>
        </label>
        <label>
          <span class="label-text">Version B</span>
          <select bind:value={diffB}>
            <option value="current">current</option>
            {#each history as h}
              <option value={h.filename}>{h.filename}</option>
            {/each}
          </select>
        </label>
        <button class="btn btn-primary" onclick={loadDiff} disabled={!diffA || loadingDiff}>
          {loadingDiff ? 'Loading...' : 'Compare'}
        </button>
      </div>
      {#if diffResult.length > 0}
        <pre class="diff-view">{#each diffResult as line}{@html colorDiffLine(line)}
{/each}</pre>
      {/if}
    </div>
  {/if}
</div>

<style>
  .page { max-width: 1200px; animation: slideUp 0.3s ease; }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--sp-md);
    gap: var(--sp-md);
  }
  .page-header h1 {
    font-size: 20px;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
  }

  .file-select {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 14px;
    border-radius: var(--radius-md);
    font-size: 13px;
    font-family: 'IBM Plex Mono', monospace;
  }

  .tabs {
    display: flex;
    gap: 2px;
    margin-bottom: var(--sp-md);
    background: var(--bg);
    border-radius: var(--radius-md);
    padding: 3px;
    border: 1px solid var(--border);
    width: fit-content;
  }
  .tab {
    padding: 8px 16px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border-radius: 5px;
    transition: all var(--t-fast);
  }
  .tab.active {
    color: var(--accent);
    background: var(--accent-bg);
  }

  .alert {
    padding: 10px 14px;
    border-radius: var(--radius-md);
    font-size: 13px;
    margin-bottom: 12px;
    animation: slideUp 0.2s ease;
  }
  .alert-error {
    background: var(--red-bg);
    color: var(--red);
    border: 1px solid rgba(255,107,107,0.2);
  }
  .alert-success {
    background: var(--green-bg);
    color: var(--green);
    border: 1px solid rgba(81,207,102,0.2);
  }

  .editor-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    flex-wrap: wrap;
  }
  .file-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
    font-family: 'IBM Plex Mono', monospace;
  }
  .dirty-badge {
    font-size: 10px;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    background: var(--yellow-bg);
    color: var(--yellow);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .toolbar-actions {
    margin-left: auto;
    display: flex;
    gap: 8px;
  }

  .btn {
    padding: 8px 16px;
    border: none;
    border-radius: var(--radius-md);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .btn:disabled { opacity: 0.35; cursor: default; }
  .btn:active:not(:disabled) { transform: scale(0.97); }
  .btn-primary { background: var(--accent); color: var(--bg); }
  .btn-ghost { background: var(--surface); color: var(--text); border: 1px solid var(--border); }
  .btn-green { background: var(--green); color: var(--bg); }

  .yaml-editor {
    width: 100%;
    min-height: 600px;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 16px;
    font-family: 'IBM Plex Mono', 'Fira Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    resize: vertical;
    tab-size: 2;
    transition: border-color var(--t-fast);
  }
  .yaml-editor:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-bg);
  }

  .loading-state, .empty-state {
    color: var(--text-dim);
    padding: 40px 0;
    text-align: center;
    font-size: 13px;
  }

  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .data-table th {
    text-align: left;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
    font-weight: 600;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .data-table td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .diff-controls {
    display: flex;
    gap: 16px;
    align-items: end;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }
  .diff-controls label {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .label-text {
    font-size: 11px;
    color: var(--text-dim);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .diff-controls select {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 12px;
    border-radius: var(--radius-md);
    font-size: 12px;
    font-family: 'IBM Plex Mono', monospace;
    min-width: 200px;
  }

  .diff-view {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 16px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    line-height: 1.6;
    overflow-x: auto;
    white-space: pre;
  }

  :global(.diff-add) { color: var(--green); }
  :global(.diff-del) { color: var(--red); }
  :global(.diff-ctx) { color: var(--text-dim); }

  @media (max-width: 768px) {
    .page-header { flex-direction: column; align-items: stretch; }
    .tabs { width: 100%; }
    .tab { flex: 1; text-align: center; }
    .editor-toolbar { flex-direction: column; align-items: stretch; }
    .toolbar-actions { margin-left: 0; }
    .yaml-editor { min-height: 400px; font-size: 12px; }
    .diff-controls { flex-direction: column; }
    .diff-controls select { min-width: 0; width: 100%; }
    .btn { padding: 12px 16px; }
  }
</style>
