<script lang="ts">
  import './app.css';
  import Sidebar from './components/Sidebar.svelte';
  import Dashboard from './pages/Dashboard.svelte';
  import Config from './pages/Config.svelte';
  import Backtest from './pages/Backtest.svelte';
  import Sweep from './pages/Sweep.svelte';
  import Factory from './pages/Factory.svelte';
  import GridView from './pages/GridView.svelte';
  import System from './pages/System.svelte';

  let currentPage = $state(window.location.hash.slice(1) || 'dashboard');
  let sidebarOpen = $state(false);
  let sidebarCollapsed = $state(true);

  function handleHashChange() {
    currentPage = window.location.hash.slice(1) || 'dashboard';
    sidebarOpen = false;
  }

  $effect(() => {
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  });
</script>

<!-- Mobile hamburger -->
<button class="hamburger" onclick={() => sidebarOpen = !sidebarOpen} aria-label="Toggle menu">
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    {#if sidebarOpen}
      <path d="M5 5L15 15M15 5L5 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
    {:else}
      <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
    {/if}
  </svg>
</button>

<!-- Overlay backdrop for mobile -->
{#if sidebarOpen}
  <button class="overlay" onclick={() => sidebarOpen = false} aria-label="Close menu"></button>
{/if}

<Sidebar {currentPage} open={sidebarOpen} collapsed={sidebarCollapsed} onNavigate={() => sidebarOpen = false} onToggleCollapse={() => sidebarCollapsed = !sidebarCollapsed} />

<main class="main-content">
  {#if currentPage === 'dashboard'}
    <Dashboard />
  {:else if currentPage === 'config'}
    <Config />
  {:else if currentPage === 'backtest'}
    <Backtest />
  {:else if currentPage === 'sweep'}
    <Sweep />
  {:else if currentPage === 'factory'}
    <Factory />
  {:else if currentPage === 'grid'}
    <GridView />
  {:else if currentPage === 'system'}
    <System />
  {:else}
    <div class="not-found">
      <h1>404</h1>
      <p>Unknown page: <code>{currentPage}</code></p>
    </div>
  {/if}
</main>

<style>
  .main-content {
    flex: 1;
    padding: var(--sp-lg);
    padding-bottom: calc(var(--sp-lg) + var(--safe-bottom));
    overflow-y: auto;
    overflow-x: hidden;
    animation: fadeIn 0.25s ease;
  }

  .hamburger {
    display: none;
    position: fixed;
    top: var(--sp-sm);
    left: var(--sp-sm);
    z-index: calc(var(--z-sidebar) + 1);
    width: 40px;
    height: 40px;
    border-radius: var(--radius-md);
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0;
    align-items: center;
    justify-content: center;
    -webkit-tap-highlight-color: transparent;
  }

  .overlay {
    display: none;
    position: fixed;
    inset: 0;
    z-index: var(--z-overlay);
    background: rgba(0,0,0,0.6);
    backdrop-filter: blur(2px);
    border: none;
    padding: 0;
    cursor: default;
  }

  .not-found {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 60vh;
    color: var(--text-muted);
  }
  .not-found h1 {
    font-size: 48px;
    font-weight: 700;
    color: var(--text-dim);
    margin-bottom: 8px;
  }
  .not-found code {
    font-family: 'IBM Plex Mono', monospace;
    color: var(--accent);
  }

  @media (max-width: 768px) {
    .hamburger {
      display: flex;
    }
    .overlay {
      display: block;
      animation: fadeIn 0.2s ease;
    }
    .main-content {
      padding: var(--sp-md);
      padding-top: 56px;
    }
  }
</style>
