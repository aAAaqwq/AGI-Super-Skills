#!/usr/bin/env node

/**
 * Google Sheets OAuth2 Authorization Script
 * Run this script to authorize access to Google Sheets
 */

const fs = require('fs');
const path = require('path');

// Load environment variables
function loadEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  if (!fs.existsSync(envPath)) {
    console.error('❌ .env file not found');
    process.exit(1);
  }

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

// Check dependencies
function checkDependencies() {
  try {
    require('http');
    require('crypto');
  } catch (error) {
    console.error('❌ Missing required dependencies');
    console.error('Please ensure you are running Node.js 14+');
    process.exit(1);
  }
}

// Main authorization flow
async function main() {
  console.log('\n' + '='.repeat(60));
  console.log('🔐 Google Sheets OAuth2 Authorization');
  console.log('='.repeat(60) + '\n');

  loadEnv();
  checkDependencies();

  const { getAuthUrl, exchangeCodeForToken, config } = require('./google-sheets-writer.js');

  // Check configuration
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

  // Generate authorization URL
  const { url, state } = getAuthUrl();

  console.log('🔗 Step 1: Open this URL in your browser:\n');
  console.log(`   ${url}\n`);
  console.log('⚠️  Note: If the redirect URI mismatch error occurs, update your OAuth2 client');
  console.log(`   to include this redirect URI: ${config.redirectUri}\n`);

  // Start a simple HTTP server to handle callback
  const http = require('http');
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (url.pathname === '/callback') {
      const code = url.searchParams.get('code');
      const returnedState = url.searchParams.get('state');

      if (returnedState !== state) {
        res.writeHead(400);
        res.end('Invalid state parameter');
        console.error('❌ State mismatch');
        server.close();
        return;
      }

      if (code) {
        console.log('\n✅ Received authorization code');
        console.log('🔄 Exchanging for tokens...');

        exchangeCodeForToken(code)
          .then((tokens) => {
            console.log('✅ Authorization successful!\n');
            console.log('   Tokens saved to: .google-tokens.json');
            console.log('   Access Token: ' + tokens.access_token.substring(0, 20) + '...');
            if (tokens.refresh_token) {
              console.log('   Refresh Token: ' + tokens.refresh_token.substring(0, 20) + '...');
            }
            console.log('\n' + '='.repeat(60));
            console.log('✅ You can now use the skill to write to Google Sheets!');
            console.log('='.repeat(60) + '\n');

            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(`
              <html>
                <head>
                  <title>Authorization Successful</title>
                  <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .success { color: #4CAF50; font-size: 24px; }
                  </style>
                </head>
                <body>
                  <div class="success">✅ Authorization Successful!</div>
                  <p>You can close this window and return to the terminal.</p>
                </body>
              </html>
            `);

            server.close();
            setTimeout(() => process.exit(0), 1000);
          })
          .catch((error) => {
            console.error('\n❌ Token exchange failed:', error.message);
            res.writeHead(500, { 'Content-Type': 'text/html' });
            res.end(`
              <html>
                <head><title>Authorization Failed</title></head>
                <body>
                  <h1>❌ Authorization Failed</h1>
                  <p>${error.message}</p>
                </body>
              </html>
            `);
            server.close();
            setTimeout(() => process.exit(1), 1000);
          });
      } else {
        const error = url.searchParams.get('error');
        console.error('\n❌ Authorization denied:', error);
        res.writeHead(400, { 'Content-Type': 'text/html' });
        res.end(`
          <html>
            <head><title>Authorization Failed</title></head>
            <body>
              <h1>❌ Authorization Failed</h1>
              <p>Reason: ${error}</p>
            </body>
          </html>
        `);
        server.close();
        setTimeout(() => process.exit(1), 1000);
      }
    } else {
      res.writeHead(404);
      res.end('Not found');
    }
  });

  const PORT = 8081;
  server.listen(PORT, () => {
    console.log(`🌐 Local server started on http://localhost:${PORT}`);
    console.log('⏳ Waiting for authorization callback...\n');
  });

  // Timeout after 5 minutes
  setTimeout(() => {
    console.log('\n⏱️ Authorization timeout (5 minutes)');
    server.close();
    process.exit(1);
  }, 5 * 60 * 1000);
}

// Run the script
main().catch(error => {
  console.error('❌ Error:', error);
  process.exit(1);
});
