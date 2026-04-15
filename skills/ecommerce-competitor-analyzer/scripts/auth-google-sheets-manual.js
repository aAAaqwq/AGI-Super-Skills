#!/usr/bin/env node

/**
 * Manual Google Sheets OAuth2 Authorization
 * Simpler alternative for users who prefer manual flow
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

// Load environment variables
function loadEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  const envContent = fs.readFileSync(envPath, 'utf8');
  const lines = envContent.split('\n');

  for (const line of lines) {
    const trimmedLine = line.trim();
    if (trimmedLine && !trimmedLine.startsWith('#')) {
      const [key, ...valueParts] = trimmedLine.split('=');
      const value = valueParts.join('=').trim();
      if (key && value) {
        process.env[key.trim()] = value;
      }
    }
  }
}

async function main() {
  console.log('\n' + '='.repeat(60));
  console.log('🔐 Google Sheets OAuth2 Manual Authorization');
  console.log('='.repeat(60) + '\n');

  loadEnv();

  const config = {
    clientId: process.env.GOOGLE_SHEETS_CLIENT_ID,
    clientSecret: process.env.GOOGLE_SHEETS_CLIENT_SECRET,
    redirectUri: process.env.GOOGLE_SHEETS_REDIRECT_URI || 'http://localhost:8080',
    sheetId: process.env.GOOGLE_SHEETS_ID_DEFAULT,
    sheetName: process.env.GOOGLE_SHEET_NAME_DEFAULT || '工作表1',
    gid: process.env.GOOGLE_SHEET_GID
  };

  if (!config.clientId || !config.clientSecret) {
    console.error('❌ Google Sheets credentials not found in .env');
    console.error('Please set GOOGLE_SHEETS_CLIENT_ID and GOOGLE_SHEETS_CLIENT_SECRET');
    process.exit(1);
  }

  console.log('📋 Configuration:');
  console.log(`   Spreadsheet ID: ${config.sheetId}`);
  console.log(`   Sheet Name: ${config.sheetName}`);
  if (config.gid) {
    console.log(`   GID: ${config.gid}`);
  }
  console.log();

  // Generate auth URL
  const crypto = require('crypto');
  const state = crypto.randomBytes(16).toString('hex');

  const scope = 'https://www.googleapis.com/auth/spreadsheets';
  const params = new URLSearchParams({
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    scope: scope,
    response_type: 'code',
    state: state,
    access_type: 'offline',
    prompt: 'consent'
  });

  const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;

  console.log('🔗 Step 1: Open this URL in your browser:\n');
  console.log(`   ${authUrl}\n`);

  console.log('⚠️  Important: Make sure your OAuth2 client has this redirect URI:');
  console.log(`   ${config.redirectUri}\n`);

  console.log('📝 Step 2: After authorizing, you will be redirected to a page');
  console.log('   that shows an error (this is normal).');
  console.log('   Copy the "code" parameter from the URL.\n');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  rl.question('Paste the authorization code here: ', async (code) => {
    code = code.trim();

    if (!code) {
      console.log('\n❌ No code provided. Authorization canceled.');
      rl.close();
      process.exit(1);
    }

    console.log('\n🔄 Exchanging code for tokens...');

    try {
      const response = await fetch('https://oauth2.googleapis.com/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
          code: code,
          client_id: config.clientId,
          client_secret: config.clientSecret,
          redirect_uri: config.redirectUri,
          grant_type: 'authorization_code'
        })
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Token exchange failed: ${error}`);
      }

      const tokens = await response.json();

      // Save tokens
      const tokenPath = path.join(__dirname, '..', '.google-tokens.json');
      const tokenData = {
        ...tokens,
        expiry_date: Date.now() + (tokens.expires_in * 1000)
      };

      fs.writeFileSync(tokenPath, JSON.stringify(tokenData, null, 2));

      console.log('✅ Authorization successful!\n');
      console.log('   Tokens saved to: .google-tokens.json');
      console.log('   Access Token: ' + tokens.access_token.substring(0, 20) + '...');
      if (tokens.refresh_token) {
        console.log('   Refresh Token: ' + tokens.refresh_token.substring(0, 20) + '...');
      }

      console.log('\n' + '='.repeat(60));
      console.log('✅ You can now use the skill to write to Google Sheets!');
      console.log('='.repeat(60) + '\n');

      rl.close();
    } catch (error) {
      console.error('\n❌ Authorization failed:', error.message);
      console.error('\nPossible issues:');
      console.error('1. Invalid authorization code');
      console.error('2. Redirect URI mismatch in OAuth2 client settings');
      console.error('3. OAuth2 client does not have correct scopes');
      rl.close();
      process.exit(1);
    }
  });
}

main();
