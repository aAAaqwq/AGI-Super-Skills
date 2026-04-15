#!/usr/bin/env node
/**
 * Amazon Ads API v3 — Campaigns & Performance
 * Usage:
 *   node ads.js --profiles
 *   node ads.js --campaigns [--out file.json]
 *   node ads.js --summary
 */

const fs = require('fs');

const CREDS_PATH = process.env.AMAZON_ADS_PATH || './amazon-ads-api.json';

const ENDPOINTS = { na: 'advertising-api.amazon.com', eu: 'advertising-api-eu.amazon.com', fe: 'advertising-api-fe.amazon.com' };

function getCreds() { return JSON.parse(fs.readFileSync(CREDS_PATH, 'utf8')); }

function getApiBase() {
  const creds = getCreds();
  return 'https://' + (ENDPOINTS[creds.region] || ENDPOINTS.eu);
}

async function getAccessToken() {
  const creds = getCreds();
  const res = await fetch('https://api.amazon.com/auth/o2/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: creds.refreshToken,
      client_id: creds.lwaClientId,
      client_secret: creds.lwaClientSecret,
    }),
  });
  const t = await res.json();
  if (!t.access_token) throw new Error('Ads auth failed: ' + JSON.stringify(t));
  return t.access_token;
}

async function apiCall(path, method = 'GET', body = null, contentType = 'application/json') {
  const creds = getCreds();
  const token = await getAccessToken();
  const opts = {
    method,
    headers: {
      'Amazon-Advertising-API-ClientId': creds.lwaClientId,
      'Amazon-Advertising-API-Scope': creds.profileId,
      'Authorization': 'Bearer ' + token,
      'Content-Type': contentType,
      'Accept': contentType,
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(getApiBase() + path, opts);
  return res.json();
}

async function getProfiles() {
  const creds = getCreds();
  const token = await getAccessToken();
  const res = await fetch(getApiBase() + '/v2/profiles', {
    headers: {
      'Amazon-Advertising-API-ClientId': creds.lwaClientId,
      'Authorization': 'Bearer ' + token,
    },
  });
  return res.json();
}

async function getCampaigns() {
  return apiCall('/sp/campaigns/list', 'POST', {}, 'application/vnd.spcampaign.v3+json');
}

function parseArgs() {
  const a = process.argv.slice(2);
  const out = { command: null, out: null };
  for (let i = 0; i < a.length; i++) {
    if (a[i] === '--profiles') out.command = 'profiles';
    else if (a[i] === '--campaigns') out.command = 'campaigns';
    else if (a[i] === '--summary') out.command = 'summary';
    else if (a[i] === '--out') out.out = a[++i];
  }
  return out;
}

async function main() {
  const args = parseArgs();
  if (!args.command) {
    console.log('Usage:');
    console.log('  node ads.js --profiles');
    console.log('  node ads.js --campaigns [--out file.json]');
    console.log('  node ads.js --summary');
    process.exit(0);
  }

  if (args.command === 'profiles') {
    const profiles = await getProfiles();
    console.log(JSON.stringify(profiles, null, 2));
    return;
  }

  if (args.command === 'campaigns' || args.command === 'summary') {
    const data = await getCampaigns();
    const campaigns = data.campaigns || [];
    const enabled = campaigns.filter(c => c.state === 'ENABLED');
    const paused = campaigns.filter(c => c.state === 'PAUSED');
    const totalBudget = enabled.reduce((sum, c) => sum + (c.budget?.budget || 0), 0);

    console.log(`\n📊 Amazon Ads Summary\n`);
    console.log(`Active campaigns : ${enabled.length}`);
    console.log(`Paused campaigns : ${paused.length}`);
    console.log(`Total daily budget: ${totalBudget.toFixed(2)}\n`);
    campaigns.forEach(c => {
      console.log(`  [${c.state}] ${c.name} — ${c.budget?.budget}/day (${c.targetingType})`);
    });

    if (args.out) {
      fs.writeFileSync(args.out, JSON.stringify({ fetchedAt: new Date().toISOString(), totalResults: data.totalResults, campaigns }, null, 2));
      console.log(`\nSaved to ${args.out}`);
    }
    return campaigns;
  }
}

main().catch(e => { console.error(e.message || e); process.exit(1); });
module.exports = { getProfiles, getCampaigns, getAccessToken };
