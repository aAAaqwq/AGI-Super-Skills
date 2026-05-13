#!/usr/bin/env node
/**
 * OpenClaw Shield CLI
 * Usage:
 *   shield audit <config.json>          — run security audit
 *   shield audit --stdin                 — read config from stdin
 *   shield sanitize <config.json>        — strip secrets from config
 *   shield sanitize --stdin              — read from stdin
 *   shield audit --live                  — audit the running OpenClaw instance
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { auditConfig } = require('../src/audit');
const { sanitizeAndStringify } = require('../src/sanitize');

const args = process.argv.slice(2);
const command = args[0];

function usage() {
  console.log(`OpenClaw Shield v1.0.0 — Security Audit for OpenClaw Configs

Usage:
  shield audit <config.json>    Audit a config file
  shield audit --stdin          Audit config from stdin
  shield audit --live           Audit the running OpenClaw config
  shield sanitize <config.json> Strip secrets from config
  shield sanitize --stdin       Strip secrets from stdin
  shield --help                 Show this help

Options:
  --json          Output raw JSON (default for audit)
  --pretty        Pretty-print JSON output
  --summary       Human-readable summary instead of JSON

Examples:
  node bin/shield.js audit ~/.openclaw/openclaw.json
  openclaw config.get | node bin/shield.js audit --stdin
  node bin/shield.js audit --live --summary
`);
}

function loadConfig() {
  if (args.includes('--live')) {
    try {
      const raw = execSync('openclaw config.get', { encoding: 'utf-8', timeout: 10000 });
      return JSON.parse(raw);
    } catch (e) {
      // config.get may not be available, try reading the file directly
      const configPath = path.join(process.env.HOME || '/root', '.openclaw', 'openclaw.json');
      if (fs.existsSync(configPath)) {
        return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      }
      console.error('Error: Could not load live config. Is OpenClaw running?');
      process.exit(1);
    }
  }

  if (args.includes('--stdin')) {
    const input = fs.readFileSync('/dev/stdin', 'utf-8');
    return JSON.parse(input);
  }

  const filePath = args.find(a => !a.startsWith('-'));
  if (filePath && filePath !== command) {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }

  // Try second positional arg
  const fileArg = args[1];
  if (fileArg && !fileArg.startsWith('-')) {
    return JSON.parse(fs.readFileSync(fileArg, 'utf-8'));
  }

  console.error('Error: No config source specified. Use a file path, --stdin, or --live.');
  process.exit(1);
}

function formatSummary(report) {
  const lines = [];
  const icons = { critical: '🔴', high: '🟠', medium: '🟡', low: '🔵' };

  lines.push('');
  lines.push('╔══════════════════════════════════════════════════╗');
  lines.push('║         🛡️  OpenClaw Shield Audit Report         ║');
  lines.push('╚══════════════════════════════════════════════════╝');
  lines.push('');
  lines.push(`  Risk Level:    ${report.risk_level}`);
  lines.push(`  Score:         ${report.overall_score}/100`);
  lines.push(`  Safe to Deploy: ${report.safe_to_deploy ? '✅ Yes' : '❌ No'}`);
  lines.push(`  Action:        ${report.action_recommended}`);
  lines.push('');
  lines.push(`  Vulnerabilities: ${report.vulnerability_count.total}`);
  lines.push(`    🔴 Critical: ${report.vulnerability_count.critical}`);
  lines.push(`    🟠 High:     ${report.vulnerability_count.high}`);
  lines.push(`    🟡 Medium:   ${report.vulnerability_count.medium}`);
  lines.push(`    🔵 Low:      ${report.vulnerability_count.low}`);
  lines.push('');
  lines.push('─'.repeat(52));

  for (const v of report.vulnerabilities) {
    lines.push('');
    lines.push(`  ${icons[v.severity]} [${v.severity.toUpperCase()}] ${v.category}`);
    lines.push(`    Issue: ${v.issue}`);
    lines.push(`    Fix:   ${v.recommendation}`);
  }

  lines.push('');
  lines.push('─'.repeat(52));
  lines.push(`  Compliance: ${(report.best_practices_compliance * 100).toFixed(0)}%`);
  lines.push(`  Audit time: ${report.audit_timestamp}`);
  lines.push(`  Engine:     v${report.engine_version}`);
  lines.push('');

  return lines.join('\n');
}

// ── Main ──

if (!command || args.includes('--help') || args.includes('-h')) {
  usage();
  process.exit(0);
}

try {
  if (command === 'audit') {
    const config = loadConfig();
    const report = auditConfig(config);

    if (args.includes('--summary')) {
      console.log(formatSummary(report));
    } else {
      console.log(JSON.stringify(report, null, 2));
    }

    // Exit code based on risk
    process.exit(report.risk_level === 'CRITICAL' ? 2 : report.risk_level === 'HIGH' ? 1 : 0);

  } else if (command === 'sanitize') {
    const config = loadConfig();
    console.log(sanitizeAndStringify(config));

  } else {
    console.error(`Unknown command: ${command}. Use --help for usage.`);
    process.exit(1);
  }
} catch (e) {
  console.error(`Error: ${e.message}`);
  process.exit(1);
}
