#!/usr/bin/env node
/**
 * OpenClaw Shield — Core Security Audit Engine
 * Analyzes an OpenClaw config JSON and produces a structured security report.
 * 
 * Usage: const { auditConfig } = require('./audit'); const report = auditConfig(configObj);
 */

'use strict';

const SEVERITY = { critical: 4, high: 3, medium: 2, low: 1 };

function auditConfig(config, options = {}) {
  const vulns = [];
  const push = (v) => vulns.push(v);

  checkGatewayAuth(config, push);
  checkNetworkExposure(config, push);
  checkChannelSecurity(config, push);
  checkDmPolicy(config, push);
  checkSubagentPermissions(config, push);
  checkToolPermissions(config, push);
  checkSecretLeakage(config, push, options);
  checkSandboxExecution(config, push);
  checkPluginConfig(config, push);
  checkHeartbeatExposure(config, push);
  checkRemoteConfig(config, push);

  // Sort by severity (critical first)
  vulns.sort((a, b) => SEVERITY[b.severity] - SEVERITY[a.severity]);

  const score = computeScore(vulns);
  const riskLevel = score >= 80 ? 'LOW' : score >= 60 ? 'MEDIUM' : score >= 40 ? 'HIGH' : 'CRITICAL';
  const bpc = Math.max(0, Math.min(1, score / 100));

  return {
    risk_level: riskLevel,
    overall_score: score,
    vulnerabilities: vulns,
    vulnerability_count: {
      critical: vulns.filter(v => v.severity === 'critical').length,
      high: vulns.filter(v => v.severity === 'high').length,
      medium: vulns.filter(v => v.severity === 'medium').length,
      low: vulns.filter(v => v.severity === 'low').length,
      total: vulns.length,
    },
    best_practices_compliance: Math.round(bpc * 100) / 100,
    action_recommended: score >= 70 ? 'APPROVE' : score >= 40 ? 'REVIEW_AND_REMEDIATE' : 'BLOCK',
    safe_to_deploy: score >= 60,
    audit_timestamp: new Date().toISOString(),
    engine_version: '1.0.0',
  };
}

// ──────────────────────────────────────────────
// 1. Gateway Auth
// ──────────────────────────────────────────────
function checkGatewayAuth(config, push) {
  const gw = config.gateway || {};
  const auth = gw.auth || {};
  const controlUi = gw.controlUi || {};

  if (!auth.mode && !auth.token) {
    push({
      category: 'gateway_auth',
      severity: 'critical',
      issue: 'Gateway has no authentication configured — anyone with network access can control the agent.',
      recommendation: 'Set gateway.auth.mode to "token" and provide a strong gateway.auth.token.',
      auto_fix: { path: 'gateway.auth', value: { mode: 'token' } },
    });
  }

  if (auth.token && auth.token.length < 24) {
    push({
      category: 'gateway_auth',
      severity: 'high',
      issue: `Gateway auth token is only ${auth.token.length} characters — too short for production use.`,
      recommendation: 'Use a token of at least 32 characters generated with a CSPRNG.',
    });
  }

  if (controlUi.allowInsecureAuth === true) {
    push({
      category: 'gateway_auth',
      severity: 'high',
      issue: 'Control UI has allowInsecureAuth enabled — authentication can be bypassed or downgraded.',
      recommendation: 'Set gateway.controlUi.allowInsecureAuth to false.',
      auto_fix: { path: 'gateway.controlUi.allowInsecureAuth', value: false },
    });
  }

  if (controlUi.enabled === true && !auth.token) {
    push({
      category: 'gateway_auth',
      severity: 'high',
      issue: 'Control UI is enabled but no gateway auth token is set — the UI is accessible without credentials.',
      recommendation: 'Set a strong gateway.auth.token or disable the control UI.',
    });
  }
}

// ──────────────────────────────────────────────
// 2. Network Exposure
// ──────────────────────────────────────────────
function checkNetworkExposure(config, push) {
  const gw = config.gateway || {};
  const bind = (gw.bind || '').toLowerCase();

  if (bind && bind !== 'loopback' && bind !== 'localhost' && bind !== '127.0.0.1' && bind !== '::1') {
    const sev = (bind === '0.0.0.0' || bind === '::' || bind === 'all') ? 'critical' : 'high';
    push({
      category: 'network_exposure',
      severity: sev,
      issue: `Gateway binds to "${gw.bind}" — the API is accessible from the network.`,
      recommendation: 'Set gateway.bind to "loopback" unless you explicitly need remote access.',
      auto_fix: { path: 'gateway.bind', value: 'loopback' },
    });
  }

  const ts = gw.tailscale || {};
  if (ts.mode === 'on' || ts.mode === 'funnel') {
    if (ts.mode === 'funnel') {
      push({
        category: 'network_exposure',
        severity: 'critical',
        issue: 'Tailscale Funnel is enabled — gateway is publicly reachable on the internet.',
        recommendation: 'Use tailscale.mode "on" (private tailnet only) instead of "funnel" unless public access is intended.',
      });
    }
  }

  const proxies = gw.trustedProxies || [];
  const dangerousProxies = proxies.filter(p => p === '*' || p === '0.0.0.0/0' || p === '::/0');
  if (dangerousProxies.length > 0) {
    push({
      category: 'network_exposure',
      severity: 'high',
      issue: `trustedProxies contains wildcard entries: ${dangerousProxies.join(', ')} — any source IP can spoof headers.`,
      recommendation: 'Restrict trustedProxies to specific proxy IPs (e.g. 127.0.0.1, ::1).',
    });
  }
}

// ──────────────────────────────────────────────
// 3. Channel Security
// ──────────────────────────────────────────────
function checkChannelSecurity(config, push) {
  const channels = config.channels || {};

  for (const [name, ch] of Object.entries(channels)) {
    const allowFrom = ch.allowFrom || [];

    if (allowFrom.includes('*')) {
      push({
        category: 'channel_security',
        severity: 'high',
        issue: `Channel "${name}" uses wildcard allowFrom: ["*"] — any user can interact with the agent.`,
        recommendation: `Restrict ${name}.allowFrom to specific user IDs or remove the wildcard.`,
        auto_fix: { path: `channels.${name}.allowFrom`, value: '[]' },
      });
    }

    if (allowFrom.length === 0 && ch.enabled !== false) {
      push({
        category: 'channel_security',
        severity: 'medium',
        issue: `Channel "${name}" has an empty allowFrom list — depending on defaults, this may allow all or deny all.`,
        recommendation: `Explicitly configure ${name}.allowFrom with authorized user IDs.`,
      });
    }
  }
}

// ──────────────────────────────────────────────
// 4. DM Policy
// ──────────────────────────────────────────────
function checkDmPolicy(config, push) {
  const channels = config.channels || {};

  for (const [name, ch] of Object.entries(channels)) {
    if (ch.dmPolicy === 'open') {
      push({
        category: 'dm_policy',
        severity: 'medium',
        issue: `Channel "${name}" has dmPolicy set to "open" — any user can DM the agent without pairing.`,
        recommendation: 'Set dmPolicy to "pairing" to require explicit user approval.',
        auto_fix: { path: `channels.${name}.dmPolicy`, value: 'pairing' },
      });
    }

    if (!ch.dmPolicy && ch.enabled !== false) {
      push({
        category: 'dm_policy',
        severity: 'low',
        issue: `Channel "${name}" has no explicit dmPolicy — relying on default behavior.`,
        recommendation: 'Explicitly set dmPolicy to "pairing" for clarity and security.',
      });
    }
  }
}

// ──────────────────────────────────────────────
// 5. Subagent Permissions
// ──────────────────────────────────────────────
function checkSubagentPermissions(config, push) {
  const agents = (config.agents && config.agents.list) || [];

  for (const agent of agents) {
    const sa = agent.subagents || {};
    const allowed = sa.allowAgents || [];

    if (allowed.includes('*')) {
      push({
        category: 'subagent_perms',
        severity: 'high',
        issue: `Agent "${agent.id}" has wildcard subagent permission (allowAgents: ["*"]) — can spawn any agent.`,
        recommendation: `Restrict ${agent.id}.subagents.allowAgents to specific agent IDs.`,
        auto_fix: { path: `agents.list[id=${agent.id}].subagents.allowAgents`, value: 'remove_wildcard' },
      });
    }

    // Check for self-delegation (circular risk)
    if (allowed.includes(agent.id)) {
      push({
        category: 'subagent_perms',
        severity: 'low',
        issue: `Agent "${agent.id}" can spawn itself — potential infinite recursion risk.`,
        recommendation: `Remove "${agent.id}" from its own allowAgents list unless self-delegation is intentional.`,
      });
    }
  }

  // Check for circular delegation chains
  const graph = {};
  for (const agent of agents) {
    graph[agent.id] = (agent.subagents || {}).allowAgents || [];
  }
  const cycles = findCycles(graph);
  if (cycles.length > 0) {
    push({
      category: 'subagent_perms',
      severity: 'medium',
      issue: `Circular subagent delegation detected: ${cycles.map(c => c.join(' → ')).join('; ')}`,
      recommendation: 'Break circular delegation chains to prevent infinite agent loops.',
    });
  }

  // Check for no maxConcurrent limits
  const defaults = (config.agents && config.agents.defaults) || {};
  const defSub = defaults.subagents || {};
  if (!defSub.maxConcurrent && defSub.maxConcurrent !== 0) {
    push({
      category: 'subagent_perms',
      severity: 'low',
      issue: 'No global subagent maxConcurrent limit set — agents could spawn unlimited subagents.',
      recommendation: 'Set agents.defaults.subagents.maxConcurrent to a reasonable limit (e.g., 4-8).',
    });
  }
}

function findCycles(graph) {
  const cycles = [];
  const visited = new Set();
  const stack = new Set();

  function dfs(node, path) {
    if (stack.has(node)) {
      const cycleStart = path.indexOf(node);
      if (cycleStart >= 0) {
        cycles.push(path.slice(cycleStart).concat(node));
      }
      return;
    }
    if (visited.has(node)) return;
    visited.add(node);
    stack.add(node);
    path.push(node);
    for (const neighbor of (graph[node] || [])) {
      if (graph[neighbor]) { // only check known agents
        dfs(neighbor, [...path]);
      }
    }
    stack.delete(node);
  }

  for (const node of Object.keys(graph)) {
    dfs(node, []);
  }
  return cycles;
}

// ──────────────────────────────────────────────
// 6. Tool Permissions
// ──────────────────────────────────────────────
function checkToolPermissions(config, push) {
  const agents = (config.agents && config.agents.list) || [];
  const fullProfileAgents = agents.filter(a => a.tools && a.tools.profile === 'full');

  if (fullProfileAgents.length > 0) {
    // More than half the agents having full tools is a smell
    const ratio = fullProfileAgents.length / agents.length;
    if (ratio > 0.5) {
      push({
        category: 'tool_permissions',
        severity: 'medium',
        issue: `${fullProfileAgents.length}/${agents.length} agents have tools.profile: "full" — most agents are over-privileged.`,
        recommendation: 'Apply principle of least privilege: only admin/main agents should have full tool access. Others should use restrictive profiles.',
        affected_agents: fullProfileAgents.map(a => a.id),
      });
    }

    for (const agent of fullProfileAgents) {
      if (agent.id !== 'main') {
        push({
          category: 'tool_permissions',
          severity: 'low',
          issue: `Non-main agent "${agent.id}" has tools.profile: "full" — can access all tools including destructive ones.`,
          recommendation: `Consider restricting ${agent.id} to only the tools it needs.`,
        });
      }
    }
  }
}

// ──────────────────────────────────────────────
// 7. Secret Leakage
// ──────────────────────────────────────────────
function checkSecretLeakage(config, push, options = {}) {
  const secretPatterns = [
    { pattern: /sk-or-v1-[a-f0-9]{64}/i, type: 'OpenRouter API key' },
    { pattern: /sk-[a-zA-Z0-9]{20,}/i, type: 'API key (sk-* pattern)' },
    { pattern: /\b[0-9]+:[A-Za-z0-9_-]{35,}\b/, type: 'Telegram bot token' },
    { pattern: /0x[a-fA-F0-9]{64}/i, type: 'Private key (hex 256-bit)' },
    { pattern: /xai-[a-zA-Z0-9]{20,}/i, type: 'xAI API key' },
    { pattern: /ghp_[a-zA-Z0-9]{36,}/i, type: 'GitHub personal access token' },
    { pattern: /gho_[a-zA-Z0-9]{36,}/i, type: 'GitHub OAuth token' },
    { pattern: /glpat-[a-zA-Z0-9_-]{20,}/i, type: 'GitLab personal access token' },
    { pattern: /AKIA[0-9A-Z]{16}/i, type: 'AWS access key' },
    { pattern: /-----BEGIN (RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----/, type: 'PEM private key' },
  ];

  const configStr = JSON.stringify(config);
  const foundSecrets = new Set();

  // Check top-level env
  scanObj('env', config.env || {}, secretPatterns, push, foundSecrets);

  // Check skill entries env
  const skills = (config.skills && config.skills.entries) || {};
  for (const [skillName, skill] of Object.entries(skills)) {
    scanObj(`skills.entries.${skillName}.env`, skill.env || {}, secretPatterns, push, foundSecrets);
  }

  // Check channel configs for tokens
  const channels = config.channels || {};
  for (const [chName, ch] of Object.entries(channels)) {
    if (ch.botToken) {
      for (const sp of secretPatterns) {
        if (sp.pattern.test(ch.botToken)) {
          const key = `channels.${chName}.botToken`;
          if (!foundSecrets.has(key)) {
            foundSecrets.add(key);
            push({
              category: 'secret_leakage',
              severity: 'critical',
              issue: `Channel "${chName}" has a ${sp.type} in botToken — this is expected for channel config but MUST NOT be shared.`,
              recommendation: 'Ensure this config file is never shared, committed to git, or sent to external services without sanitization.',
            });
          }
        }
      }
    }
  }

  // Check gateway auth token exposure
  const gwToken = (config.gateway && config.gateway.auth && config.gateway.auth.token) || '';
  if (gwToken) {
    push({
      category: 'secret_leakage',
      severity: 'medium',
      issue: 'Gateway auth token is stored in plaintext in the config file.',
      recommendation: 'Consider using environment variable references or a secrets manager for the gateway token.',
    });
  }

  // Check remote token
  const remote = (config.gateway && config.gateway.remote) || {};
  if (remote.token && remote.token !== '' && remote.token !== 'blabla') {
    push({
      category: 'secret_leakage',
      severity: 'medium',
      issue: 'Gateway remote.token is stored in plaintext — this token grants remote gateway access.',
      recommendation: 'Use environment variable references for remote tokens.',
    });
  } else if (remote.token === 'blabla' || remote.token === 'changeme' || remote.token === 'test') {
    push({
      category: 'secret_leakage',
      severity: 'high',
      issue: `Gateway remote.token is set to a placeholder value ("${remote.token}") — this is trivially guessable.`,
      recommendation: 'Generate a strong random token for gateway.remote.token.',
    });
  }
}

function scanObj(path, obj, patterns, push, found) {
  for (const [key, val] of Object.entries(obj)) {
    if (typeof val !== 'string') continue;
    for (const sp of patterns) {
      if (sp.pattern.test(val)) {
        const loc = `${path}.${key}`;
        if (!found.has(loc)) {
          found.add(loc);
          push({
            category: 'secret_leakage',
            severity: 'critical',
            issue: `${sp.type} found in plaintext at ${loc}.`,
            recommendation: `Move ${loc} to an environment variable or secrets manager. Never share this config without sanitizing it first.`,
          });
        }
      }
    }
  }
}

// ──────────────────────────────────────────────
// 8. Sandbox/Execution
// ──────────────────────────────────────────────
function checkSandboxExecution(config, push) {
  // Check for agents without workspace isolation
  const agents = (config.agents && config.agents.list) || [];
  const noWorkspace = agents.filter(a => !a.workspace && !a.default);

  if (noWorkspace.length > 0) {
    push({
      category: 'sandbox_execution',
      severity: 'medium',
      issue: `${noWorkspace.length} non-default agent(s) have no explicit workspace — they share the default workspace. Agents: ${noWorkspace.map(a => a.id).join(', ')}`,
      recommendation: 'Assign separate workspaces to each agent for isolation.',
    });
  }

  // Check if command execution controls exist
  const defaults = (config.agents && config.agents.defaults) || {};
  if (!defaults.sandbox && !defaults.execution) {
    push({
      category: 'sandbox_execution',
      severity: 'low',
      issue: 'No explicit sandbox or execution policy defined in agent defaults.',
      recommendation: 'Consider setting execution restrictions for non-admin agents.',
    });
  }
}

// ──────────────────────────────────────────────
// 9. Plugin Config
// ──────────────────────────────────────────────
function checkPluginConfig(config, push) {
  const plugins = (config.plugins && config.plugins.entries) || {};
  const channels = config.channels || {};

  for (const [pluginName, plugin] of Object.entries(plugins)) {
    if (plugin.enabled === true && !channels[pluginName]) {
      push({
        category: 'plugin_config',
        severity: 'medium',
        issue: `Plugin "${pluginName}" is enabled but has no corresponding channel configuration.`,
        recommendation: `Add a channels.${pluginName} configuration or disable the plugin.`,
      });
    }
  }

  // Check for channels without corresponding plugins
  for (const [chName, ch] of Object.entries(channels)) {
    if (ch.enabled !== false && !plugins[chName]) {
      push({
        category: 'plugin_config',
        severity: 'low',
        issue: `Channel "${chName}" is configured but has no corresponding plugin entry.`,
        recommendation: `Add plugins.entries.${chName} or verify the channel is loaded by default.`,
      });
    }
  }
}

// ──────────────────────────────────────────────
// 10. Heartbeat Exposure
// ──────────────────────────────────────────────
function checkHeartbeatExposure(config, push) {
  const agents = (config.agents && config.agents.list) || [];

  for (const agent of agents) {
    const hb = agent.heartbeat || {};
    if (hb.prompt && typeof hb.prompt === 'string') {
      // Check if heartbeat prompt contains sensitive paths or secrets
      if (/password|secret|key|token|credential/i.test(hb.prompt)) {
        push({
          category: 'heartbeat_exposure',
          severity: 'medium',
          issue: `Agent "${agent.id}" heartbeat prompt may reference sensitive information.`,
          recommendation: 'Avoid embedding secrets or sensitive paths directly in heartbeat prompts.',
        });
      }
    }

    // Very frequent heartbeats increase attack surface via prompt injection
    if (hb.every) {
      const minutes = parseInterval(hb.every);
      if (minutes > 0 && minutes < 5) {
        push({
          category: 'heartbeat_exposure',
          severity: 'low',
          issue: `Agent "${agent.id}" heartbeat interval is very frequent (${hb.every}) — increases prompt injection surface.`,
          recommendation: 'Use heartbeat intervals of at least 10-15 minutes unless high-frequency is required.',
        });
      }
    }
  }
}

function parseInterval(str) {
  const m = /^(\d+)\s*(m|min|minutes?)$/i.exec(str);
  if (m) return parseInt(m[1], 10);
  const h = /^(\d+)\s*(h|hr|hours?)$/i.exec(str);
  if (h) return parseInt(h[1], 10) * 60;
  return 0;
}

// ──────────────────────────────────────────────
// 11. Remote Config
// ──────────────────────────────────────────────
function checkRemoteConfig(config, push) {
  const remote = (config.gateway && config.gateway.remote) || {};

  if (remote.url) {
    push({
      category: 'remote_config',
      severity: 'medium',
      issue: `Remote gateway URL is configured: ${remote.url}`,
      recommendation: 'Ensure the remote URL is only accessible on trusted networks (e.g., Tailscale, VPN).',
    });

    if (remote.url.startsWith('ws://') && !remote.url.includes('localhost') && !remote.url.includes('127.0.0.1')) {
      push({
        category: 'remote_config',
        severity: 'high',
        issue: 'Remote gateway uses unencrypted WebSocket (ws://) — traffic can be intercepted.',
        recommendation: 'Use wss:// (encrypted WebSocket) for remote connections.',
        auto_fix: { path: 'gateway.remote.url', value: remote.url.replace('ws://', 'wss://') },
      });
    }
  }

  // Check trustedProxies breadth
  const proxies = (config.gateway && config.gateway.trustedProxies) || [];
  if (proxies.length > 5) {
    push({
      category: 'remote_config',
      severity: 'low',
      issue: `${proxies.length} trusted proxies configured — wide proxy trust increases header-spoofing risk.`,
      recommendation: 'Minimize trusted proxies to only those actually in the request path.',
    });
  }
}

// ──────────────────────────────────────────────
// Scoring
// ──────────────────────────────────────────────
function computeScore(vulns) {
  // Start at 100, deduct per vulnerability
  let score = 100;
  const deductions = { critical: 15, high: 8, medium: 4, low: 1 };

  for (const v of vulns) {
    score -= deductions[v.severity] || 2;
  }

  return Math.max(0, Math.min(100, score));
}

module.exports = { auditConfig };
