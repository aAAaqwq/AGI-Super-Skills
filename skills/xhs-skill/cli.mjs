import { parseArgs } from 'node:util';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import qrcodeTerminal from 'qrcode-terminal';

import { decodeQrFromPng } from './lib/qr.mjs';
import {
  normalizeCookiesPayload,
  cookiesToHeaderString,
  summarizeCookies,
} from './lib/cookies.mjs';

function usage() {
  return `xhs-skill

Usage:
  xhs-skill qr show --in <pngPath>
  xhs-skill qr show-text --text <string>

  xhs-skill cookies normalize --in <jsonPath> --out <outPath>
  xhs-skill cookies to-header --in <cookiesJsonPath>
  xhs-skill cookies status --in <cookiesJsonPath>

Notes:
  - QR decode currently supports PNG input (agent-browser-stealth should save screenshots as PNG).
  - cookies JSON can be either an array of cookies or an object containing {cookies:[...]}.
`;
}

function die(msg, code = 2) {
  const e = new Error(msg);
  e.exitCode = code;
  throw e;
}

async function ensureDirForFile(p) {
  await mkdir(dirname(p), { recursive: true });
}

async function cmdQrShow(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      in: { type: 'string' },
      json: { type: 'boolean', default: false },
      ascii: { type: 'boolean', default: true },
    },
    allowPositionals: true,
  });

  const inPath = values.in ? resolve(values.in) : null;
  if (!inPath) die('Missing --in <pngPath>');

  const { text } = await decodeQrFromPng(inPath);
  if (values.json) {
    console.log(JSON.stringify({ qr_text: text, source_png: inPath }, null, 2));
    return;
  }

  console.log(text);
  if (values.ascii) {
    qrcodeTerminal.generate(text, { small: true });
  }
}

async function cmdQrShowText(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      text: { type: 'string' },
      json: { type: 'boolean', default: false },
      ascii: { type: 'boolean', default: true },
    },
    allowPositionals: true,
  });

  const text = values.text;
  if (!text) die('Missing --text <string>');

  if (values.json) {
    console.log(JSON.stringify({ qr_text: text }, null, 2));
    return;
  }

  console.log(text);
  if (values.ascii) {
    qrcodeTerminal.generate(text, { small: true });
  }
}

async function cmdCookiesNormalize(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      in: { type: 'string' },
      out: { type: 'string' },
    },
    allowPositionals: true,
  });

  const inPath = values.in ? resolve(values.in) : null;
  const outPath = values.out ? resolve(values.out) : null;
  if (!inPath) die('Missing --in <jsonPath>');
  if (!outPath) die('Missing --out <outPath>');

  const raw = await readFile(inPath, 'utf8');
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    die(`Invalid JSON: ${inPath}`);
  }

  const normalized = normalizeCookiesPayload(parsed);
  await ensureDirForFile(outPath);
  await writeFile(outPath, JSON.stringify(normalized, null, 2) + '\n', 'utf8');
  console.log(`Wrote ${normalized.cookies.length} cookies to ${outPath}`);
}

async function cmdCookiesToHeader(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      in: { type: 'string' },
      json: { type: 'boolean', default: false },
    },
    allowPositionals: true,
  });

  const inPath = values.in ? resolve(values.in) : null;
  if (!inPath) die('Missing --in <cookiesJsonPath>');

  const raw = await readFile(inPath, 'utf8');
  const parsed = JSON.parse(raw);
  const normalized = normalizeCookiesPayload(parsed);
  const header = cookiesToHeaderString(normalized.cookies);

  if (values.json) {
    console.log(JSON.stringify({ header, cookie_count: normalized.cookies.length }, null, 2));
    return;
  }
  console.log('Cookie: ' + header);
}

async function cmdCookiesStatus(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      in: { type: 'string' },
      json: { type: 'boolean', default: false },
    },
    allowPositionals: true,
  });

  const inPath = values.in ? resolve(values.in) : null;
  if (!inPath) die('Missing --in <cookiesJsonPath>');

  const raw = await readFile(inPath, 'utf8');
  const parsed = JSON.parse(raw);
  const normalized = normalizeCookiesPayload(parsed);
  const summary = summarizeCookies(normalized.cookies);

  if (values.json) {
    console.log(JSON.stringify({ ...summary, source: inPath }, null, 2));
    return;
  }

  console.log(`cookies: ${summary.count}`);
  console.log(`domains: ${summary.domains.join(', ') || '(none)'}`);
  console.log(`sessionCookies: ${summary.sessionCount}`);
  console.log(`persistentCookies: ${summary.persistentCount}`);
  if (summary.earliestExpiry) console.log(`earliestExpiry: ${summary.earliestExpiry}`);
  if (summary.latestExpiry) console.log(`latestExpiry: ${summary.latestExpiry}`);
}

export async function main(argv) {
  const [cmd, sub, ...rest] = argv;

  if (!cmd || cmd === '-h' || cmd === '--help' || cmd === 'help') {
    console.log(usage());
    return;
  }

  try {
    if (cmd === 'qr' && sub === 'show') return await cmdQrShow(rest);
    if (cmd === 'qr' && sub === 'show-text') return await cmdQrShowText(rest);

    if (cmd === 'cookies' && sub === 'normalize') return await cmdCookiesNormalize(rest);
    if (cmd === 'cookies' && sub === 'to-header') return await cmdCookiesToHeader(rest);
    if (cmd === 'cookies' && sub === 'status') return await cmdCookiesStatus(rest);

    die(`Unknown command: ${cmd} ${sub || ''}`.trim());
  } catch (e) {
    if (e && typeof e === 'object' && 'exitCode' in e) {
      console.error(e.message);
      process.exitCode = e.exitCode;
      return;
    }
    throw e;
  }
}
