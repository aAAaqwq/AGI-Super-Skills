#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { readFile } from 'node:fs/promises';

import { normalizeCookiesPayload } from '../lib/cookies.mjs';

function usage() {
  return `verify_login

Usage:
  node ./scripts/verify_login.mjs --cookies <cookiesJsonPath> --current-url <url> --probe-final-url <url> [--probe-final-url <url> ...] [--probe-status <code>] [--probe-status <code> ...] [--json]

Checks (all required):
  1) left /login
  2) probe final url(s) do not end at /login and status != 401 (if provided)

Bonus (not required):
  - cookies include a session-like cookie (web_session or name contains "session")
`;
}

function normUrl(v) {
  if (!v) return '';
  return String(v).trim();
}

function isLoginUrl(url) {
  const s = normUrl(url).toLowerCase();
  if (!s) return true;
  return s.includes('/login');
}

function hasSessionLikeCookie(cookies) {
  let hasWebSession = false;
  let hasAnySessionName = false;
  for (const c of cookies) {
    if (!c || typeof c !== 'object') continue;
    const name = String(c.name || '').trim();
    const value = String(c.value || '').trim();
    if (!name || !value) continue;
    if (name === 'web_session') hasWebSession = true;
    if (name.toLowerCase().includes('session')) hasAnySessionName = true;
  }
  return {
    has_web_session: hasWebSession,
    has_session_like: hasWebSession || hasAnySessionName,
  };
}

function asArray(v) {
  if (!v) return [];
  return Array.isArray(v) ? v : [v];
}

async function main(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      cookies: { type: 'string' },
      'current-url': { type: 'string' },
      'probe-final-url': { type: 'string', multiple: true },
      'probe-status': { type: 'string', multiple: true },
      json: { type: 'boolean', default: true },
      help: { type: 'boolean', default: false },
    },
    allowPositionals: true,
  });

  if (values.help) {
    console.log(usage());
    return;
  }

  if (!values.cookies) {
    throw new Error('Missing --cookies <cookiesJsonPath>');
  }

  const raw = await readFile(values.cookies, 'utf8');
  const parsed = JSON.parse(raw);
  const normalized = normalizeCookiesPayload(parsed);

  const currentUrl = normUrl(values['current-url']);
  const probeFinalUrls = asArray(values['probe-final-url']).map(normUrl).filter(Boolean);
  const probeStatuses = asArray(values['probe-status'])
    .map((x) => Number(x))
    .filter((x) => Number.isFinite(x));
  const sessionLike = hasSessionLikeCookie(normalized.cookies);

  const probeOk =
    probeFinalUrls.length > 0 &&
    probeFinalUrls.every((u) => !isLoginUrl(u)) &&
    probeStatuses.every((s) => s !== 401);

  const checks = {
    left_login: {
      ok: !!currentUrl && !isLoginUrl(currentUrl),
      value: currentUrl || null,
    },
    backend_not_rejected: {
      ok: probeOk,
      value: {
        probe_final_urls: probeFinalUrls,
        probe_statuses: probeStatuses.length ? probeStatuses : null,
      },
    },
    has_session_like_cookie: {
      ok: sessionLike.has_session_like,
      value: {
        has_web_session: sessionLike.has_web_session,
      },
    },
  };

  const requiredChecks = ['left_login', 'backend_not_rejected'];
  const missing = requiredChecks.filter((k) => !checks[k]?.ok);

  const warnings = [];
  if (!checks.has_session_like_cookie.ok) {
    warnings.push(
      'No session-like cookie detected. This may still be OK if the platform changed cookie shape, but expect higher flakiness.'
    );
  }

  const result = {
    ok: missing.length === 0,
    checks,
    cookie_count: normalized.cookies.length,
    missing,
    warnings,
  };

  if (values.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(`ok: ${result.ok}`);
    console.log(`missing: ${result.missing.join(', ') || '(none)'}`);
  }

  if (!result.ok) {
    process.exitCode = 2;
  }
}

main(process.argv.slice(2)).catch((e) => {
  console.error(e?.message || String(e));
  process.exitCode = 1;
});
