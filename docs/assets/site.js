(() => {
  "use strict";

  const root = document.documentElement;
  root.classList.add("js");
  const menuButton = document.querySelector("[data-menu-button]");
  const primaryNav = document.querySelector("[data-primary-nav]");
  const themeButton = document.querySelector("[data-theme-button]");
  const starCount = document.querySelector("[data-star-count]");
  const statsState = document.querySelector("[data-stats-state]");
  const forksCount = document.querySelector("[data-forks-count]");
  const verificationStatus = document.querySelector("[data-verification-status]");
  const receiptCommit = document.querySelector("[data-receipt-commit]");
  const statsCacheKey = "agi-super-team:repository-stats:v1";
  const themeCacheKey = "agi-super-team:theme:v1";
  const fifteenMinutes = 15 * 60 * 1000;
  const oneDay = 24 * 60 * 60 * 1000;

  function readStorage(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  function writeStorage(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (_error) {
      // Storage can be unavailable in private or locked-down browsing modes.
    }
  }

  function applyTheme(theme) {
    root.dataset.theme = theme;
    if (themeButton) {
      const nextTheme = theme === "dark" ? "light" : "dark";
      themeButton.setAttribute("aria-label", `Switch to ${nextTheme} theme`);
    }
  }

  const savedTheme = readStorage(themeCacheKey);
  const preferredTheme = window.matchMedia?.("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
  applyTheme(savedTheme === "light" || savedTheme === "dark" ? savedTheme : preferredTheme);

  themeButton?.addEventListener("click", () => {
    const theme = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(theme);
    writeStorage(themeCacheKey, theme);
  });

  function setMenu(open) {
    if (!menuButton || !primaryNav) return;
    menuButton.setAttribute("aria-expanded", String(open));
    primaryNav.dataset.open = String(open);
    const label = menuButton.querySelector(".sr-only");
    if (label) label.textContent = open ? "Close navigation" : "Open navigation";
  }

  menuButton?.addEventListener("click", () => {
    setMenu(menuButton.getAttribute("aria-expanded") !== "true");
  });
  primaryNav?.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) setMenu(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menuButton?.getAttribute("aria-expanded") === "true") {
      setMenu(false);
      menuButton.focus();
    }
  });

  document.querySelectorAll("[data-copy-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      const targetId = button.getAttribute("data-copy-target");
      const target = targetId ? document.getElementById(targetId) : null;
      if (!target) return;
      const value = target.textContent || "";
      try {
        await navigator.clipboard.writeText(value);
        const label = button.querySelector("span");
        const status = document.querySelector("[data-copy-status]");
        if (label) label.textContent = "Copied";
        if (status) status.textContent = "Installation commands copied.";
        window.setTimeout(() => {
          if (label) label.textContent = "Copy";
        }, 1800);
      } catch (_error) {
        const range = document.createRange();
        range.selectNodeContents(target);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
        const status = document.querySelector("[data-copy-status]");
        if (status) status.textContent = "Copy unavailable. Installation commands selected.";
      }
    });
  });

  function isRepositoryStats(value) {
    return Boolean(
      value &&
      value.schemaVersion === 1 &&
      value.repository === "aAAaqwq/AGI-Super-Team" &&
      Number.isInteger(value.stars) &&
      value.stars >= 0 &&
      Number.isInteger(value.forks) &&
      value.forks >= 0 &&
      !Number.isNaN(Date.parse(value.fetchedAt))
    );
  }

  function renderStats(stats, source) {
    if (!isRepositoryStats(stats)) return false;
    if (starCount) {
      starCount.textContent = new Intl.NumberFormat().format(stats.stars);
      starCount.hidden = false;
    }
    if (forksCount) {
      forksCount.textContent = `${new Intl.NumberFormat().format(stats.forks)} forks.`;
    }
    if (statsState) {
      const age = Date.now() - Date.parse(stats.fetchedAt);
      const label = source === "live" && age <= fifteenMinutes ? "Live" : "Cached";
      const stale = age > oneDay ? " · older than 24 hours" : "";
      statsState.textContent = `${label} GitHub data${stale}.`;
    }
    return true;
  }

  async function fetchJson(url, timeout = 3000) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error(`Request failed with ${response.status}`);
      return await response.json();
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function loadRepositoryStats() {
    let rendered = false;
    let newestStats = null;
    const localCache = readStorage(statsCacheKey);
    if (localCache) {
      try {
        const cached = JSON.parse(localCache);
        if (isRepositoryStats(cached)) {
          newestStats = cached;
          rendered = renderStats(cached, "cached") || rendered;
        }
      } catch (_error) {
        // Ignore malformed browser cache and continue to the versioned site cache.
      }
    }

    try {
      const built = await fetchJson("data/repo-stats.json");
      if (isRepositoryStats(built)) {
        const isNewer =
          !newestStats || Date.parse(built.fetchedAt) > Date.parse(newestStats.fetchedAt);
        if (isNewer) {
          newestStats = built;
          rendered = renderStats(built, "cached") || rendered;
          writeStorage(statsCacheKey, JSON.stringify(built));
        }
      }
    } catch (_error) {
      // The browser cache, when available, remains visible.
    }

    if (
      newestStats &&
      Date.now() - Date.parse(newestStats.fetchedAt) <= fifteenMinutes
    ) {
      return;
    }

    try {
      const payload = await fetchJson("https://api.github.com/repos/aAAaqwq/AGI-Super-Team");
      const live = {
        schemaVersion: 1,
        repository: "aAAaqwq/AGI-Super-Team",
        stars: payload.stargazers_count,
        forks: payload.forks_count,
        fetchedAt: new Date().toISOString(),
        source: "github-rest-api-browser",
      };
      if (isRepositoryStats(live)) {
        renderStats(live, "live");
        writeStorage(statsCacheKey, JSON.stringify(live));
        rendered = true;
      }
    } catch (_error) {
      if (!rendered && statsState) {
        statsState.textContent = "GitHub data is temporarily unavailable.";
      }
    }
  }

  async function loadVerificationReceipt() {
    try {
      const receipt = await fetchJson("data/verification-receipt.json");
      const checks = Array.isArray(receipt.checks) ? receipt.checks : [];
      const allPassed = checks.length > 0 && checks.every((check) => check.result === "pass");
      const matchesSite = receipt.commit && receipt.commit === receipt.siteCommit;
      if (receipt.result !== "pass" || !allPassed || !matchesSite) return;
      if (verificationStatus) {
        verificationStatus.textContent = "Verified";
        verificationStatus.classList.remove("status-pending");
        verificationStatus.classList.add("status-verified");
      }
      if (receiptCommit) receiptCommit.textContent = receipt.commit.slice(0, 12);
    } catch (_error) {
      // Static pending state is intentional when the receipt is absent or stale.
    }
  }

  async function loadStarHistorySummary() {
    try {
      const history = await fetchJson("data/star-history.json");
      const points = Array.isArray(history.points) ? history.points : [];
      const summary = document.querySelector("[data-history-summary]");
      if (!summary || !Number.isInteger(history.latestStars)) return;
      if (points.length < 2) {
        summary.textContent = `${history.latestStars} current stars. Historical values will appear after the authenticated Pages refresh.`;
        return;
      }
      const first = points[0];
      const last = points[points.length - 1];
      summary.textContent = `${history.latestStars} current stars. The reconstructed series runs from ${first.date} to ${last.date}; unstars can revise earlier values.`;

      const rows = document.querySelector("[data-history-rows]");
      const details = document.querySelector("[data-history-details]");
      if (!rows || !details) return;
      points.slice(-5).forEach((point) => {
        const row = document.createElement("tr");
        const date = document.createElement("th");
        const stars = document.createElement("td");
        date.scope = "row";
        date.textContent = point.date;
        stars.textContent = new Intl.NumberFormat().format(point.stars);
        row.append(date, stars);
        rows.append(row);
      });
      details.hidden = false;
    } catch (_error) {
      // The visible pending explanation remains available without JavaScript data.
    }
  }

  loadRepositoryStats();
  loadVerificationReceipt();
  loadStarHistorySummary();
})();
