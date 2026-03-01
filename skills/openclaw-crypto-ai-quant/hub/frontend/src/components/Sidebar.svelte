<script lang="ts">
  let { currentPage, open = false, collapsed = false, onNavigate, onToggleCollapse }: {
    currentPage: string;
    open?: boolean;
    collapsed?: boolean;
    onNavigate?: () => void;
    onToggleCollapse?: () => void;
  } = $props();

  /* SVG icon paths (20x20 viewBox) — crisp, minimal line icons */
  const links = [
    { id: 'dashboard', label: 'Dashboard',
      icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2v10a1 1 0 01-1 1h-3m-4 0v-6a1 1 0 00-1-1h-2a1 1 0 00-1 1v6m8 0H7' },
    { id: 'config', label: 'Config',
      icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4' },
    { id: 'backtest', label: 'Backtest',
      icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
    { id: 'sweep', label: 'Sweep',
      icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' },
    { id: 'factory', label: 'Factory',
      icon: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z' },
    { id: 'grid', label: 'Grid View',
      icon: 'M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z' },
    { id: 'system', label: 'System',
      icon: 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01' },
  ];

  function handleClick() {
    onNavigate?.();
  }
</script>

<nav class="sidebar" class:open class:collapsed>
  <div class="logo">
    <div class="logo-mark">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="2" width="20" height="20" rx="4" stroke="var(--accent)" stroke-width="1.5"/>
        <path d="M7 14l3-4 3 3 4-5" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div class="logo-text">
      <strong>AQC Hub</strong>
      <span class="version">v0.1</span>
    </div>
  </div>

  <ul>
    {#each links as link}
      <li>
        <a
          href="#{link.id}"
          class:active={currentPage === link.id}
          data-label={link.label}
          onclick={handleClick}
        >
          <svg class="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d={link.icon}/>
          </svg>
          <span class="nav-label">{link.label}</span>
          {#if currentPage === link.id}
            <span class="active-dot"></span>
          {/if}
        </a>
      </li>
    {/each}
  </ul>

  <button class="collapse-btn" onclick={onToggleCollapse} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      {#if collapsed}
        <path d="M9 18l6-6-6-6"/>
      {:else}
        <path d="M15 18l-6-6 6-6"/>
      {/if}
    </svg>
  </button>

  <div class="sidebar-footer">
    <div class="connection-status" id="ws-status">
      <span class="dot"></span>
      <span class="conn-label">Connecting</span>
    </div>
  </div>
</nav>

<style>
  .sidebar {
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: 100dvh;
    z-index: var(--z-sidebar);
    transition: width var(--t-slow) var(--ease-out),
                min-width var(--t-slow) var(--ease-out),
                transform var(--t-slow) var(--ease-out);
    overflow: hidden;
  }
  .sidebar.collapsed {
    width: 56px;
    min-width: 56px;
    overflow: visible;
  }

  .logo {
    padding: 20px 20px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .collapsed .logo {
    justify-content: center;
    padding: 20px 0 16px;
  }
  .collapsed .logo-text { display: none; }

  .logo-mark {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .logo-text {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .logo-text strong {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.2;
  }

  .version {
    font-size: 10px;
    color: var(--text-dim);
    font-weight: 500;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: 0.03em;
  }

  ul {
    list-style: none;
    flex: 1;
    padding: 12px 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .collapsed ul { padding: 12px 4px; }

  li a {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    border-radius: var(--radius-md);
    transition: all var(--t-fast);
    position: relative;
    -webkit-tap-highlight-color: transparent;
  }

  li a:hover {
    background: var(--bg-tertiary);
    color: var(--text);
  }

  li a.active {
    background: var(--accent-bg);
    color: var(--accent);
  }

  .nav-icon {
    flex-shrink: 0;
    opacity: 0.7;
  }
  li a.active .nav-icon {
    opacity: 1;
  }

  .nav-label {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
  }
  .collapsed .nav-label { display: none; }
  .collapsed .active-dot { display: none; }
  .collapsed li a {
    justify-content: center;
    padding: 10px 0;
    overflow: visible;
  }

  /* ─── Tooltip (collapsed mode only) ─── */
  .collapsed li a::after {
    content: attr(data-label);
    position: absolute;
    left: calc(100% + 10px);
    top: 50%;
    transform: translateY(-50%);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text);
    white-space: nowrap;
    pointer-events: none;
    opacity: 0;
    transition: opacity var(--t-fast);
    z-index: calc(var(--z-sidebar) + 10);
    box-shadow: 0 2px 8px rgba(0,0,0,0.45);
  }
  .collapsed li a:hover::after {
    opacity: 1;
  }

  .active-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--accent);
    flex-shrink: 0;
  }

  .sidebar-footer {
    padding: 16px 20px;
    border-top: 1px solid var(--border);
  }

  .connection-status {
    font-size: 11px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'IBM Plex Mono', monospace;
  }

  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--yellow);
    box-shadow: 0 0 6px var(--yellow);
    animation: pulse 2s ease-in-out infinite;
  }

  .conn-label {
    letter-spacing: 0.02em;
  }
  .collapsed .conn-label { display: none; }
  .collapsed .sidebar-footer { padding: 16px 0; justify-content: center; display: flex; }
  .collapsed .connection-status { justify-content: center; }

  .collapse-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 8px 8px;
    padding: 6px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
    flex-shrink: 0;
  }
  .collapse-btn:hover {
    background: var(--bg-tertiary);
    color: var(--text);
  }
  .collapsed .collapse-btn {
    margin: 0 4px 8px;
  }

  /* ─── Mobile ─── */
  @media (max-width: 768px) {
    .sidebar {
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      transform: translateX(-100%);
      box-shadow: var(--shadow-lg);
    }
    .sidebar.open {
      transform: translateX(0);
    }

    li a {
      padding: 14px 16px;
      font-size: 15px;
    }

    .nav-icon {
      width: 20px;
      height: 20px;
    }
    .collapse-btn { display: none; }
  }
</style>
