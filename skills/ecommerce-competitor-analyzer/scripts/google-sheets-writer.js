/**
 * Google Sheets Writer
 * Handles OAuth2 and Service Account authentication
 *
 * Based on n8n Google Sheets integration
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Configuration from environment
const config = {
  useServiceAccount: process.env.GOOGLE_SHEETS_USE_SERVICE_ACCOUNT === 'true',
  clientId: process.env.GOOGLE_SHEETS_CLIENT_ID,
  clientSecret: process.env.GOOGLE_SHEETS_CLIENT_SECRET,
  redirectUri: process.env.GOOGLE_SHEETS_REDIRECT_URI || 'http://localhost:8080',
  sheetId: process.env.GOOGLE_SHEETS_ID_DEFAULT,
  sheetName: process.env.GOOGLE_SHEET_NAME_DEFAULT || '工作表1',
  gid: process.env.GOOGLE_SHEET_GID
};

// Token storage file
const tokenPath = path.join(__dirname, '..', '.google-tokens.json');
const serviceAccountKeyPath = path.join(__dirname, '..', 'service-account-key.json');

// Service account credentials (loaded if using service account)
let serviceAccountCredentials = null;

/**
 * Generate OAuth2 authorization URL
 */
function getAuthUrl() {
  const scope = 'https://www.googleapis.com/auth/spreadsheets';
  const state = crypto.randomBytes(16).toString('hex');

  const params = new URLSearchParams({
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    scope: scope,
    response_type: 'code',
    state: state,
    access_type: 'offline',
    prompt: 'consent'
  });

  return {
    url: `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`,
    state: state
  };
}

/**
 * Exchange authorization code for access token
 */
async function exchangeCodeForToken(code) {
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
  saveTokens(tokens);

  return tokens;
}

/**
 * Refresh access token using refresh token
 */
async function refreshAccessToken() {
  const tokens = loadTokens();

  if (!tokens || !tokens.refresh_token) {
    throw new Error('No refresh token available. Please re-authorize.');
  }

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      client_id: config.clientId,
      client_secret: config.clientSecret,
      refresh_token: tokens.refresh_token,
      grant_type: 'refresh_token'
    })
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Token refresh failed: ${error}`);
  }

  const newTokens = await response.json();

  // Update tokens (keep refresh_token if not returned)
  const updatedTokens = {
    ...tokens,
    access_token: newTokens.access_token,
    expires_in: newTokens.expires_in,
    expiry_date: Date.now() + (newTokens.expires_in * 1000)
  };

  saveTokens(updatedTokens);

  return updatedTokens;
}

/**
 * Load tokens from file
 */
function loadTokens() {
  if (fs.existsSync(tokenPath)) {
    return JSON.parse(fs.readFileSync(tokenPath, 'utf8'));
  }
  return null;
}

/**
 * Save tokens to file
 */
function saveTokens(tokens) {
  const tokenData = {
    ...tokens,
    expiry_date: tokens.expiry_date || (Date.now() + (tokens.expires_in * 1000))
  };
  fs.writeFileSync(tokenPath, JSON.stringify(tokenData, null, 2));
}

/**
 * Load service account credentials
 */
function loadServiceAccountCredentials() {
  if (serviceAccountCredentials) {
    return serviceAccountCredentials;
  }

  if (!fs.existsSync(serviceAccountKeyPath)) {
    return null;
  }

  try {
    serviceAccountCredentials = JSON.parse(fs.readFileSync(serviceAccountKeyPath, 'utf8'));
    return serviceAccountCredentials;
  } catch (error) {
    console.error('Failed to load service account key:', error.message);
    return null;
  }
}

/**
 * Get service account access token using JWT
 */
async function getServiceAccountToken() {
  const credentials = loadServiceAccountCredentials();

  if (!credentials) {
    throw new Error('Service account key file not found. Please create service-account-key.json');
  }

  // JWT implementation (simplified - for production use google-auth-library)
  const header = {
    alg: 'RS256',
    typ: 'JWT'
  };

  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: credentials.client_email,
    scope: 'https://www.googleapis.com/auth/spreadsheets',
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600
  };

  // For simplicity, we'll use a different approach - direct API call with service account
  // This requires the JWT to be signed, which is complex without external libraries

  // Alternative: Use OAuth2 flow with service account's client_id/client_secret
  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion: createJWT(credentials, header, payload)
    })
  });

  if (!response.ok) {
    // JWT approach failed, try using refresh_token if available
    // Service accounts can also use the OAuth2 flow with a pre-configured refresh token
    throw new Error(`Service account authentication failed: ${response.status}`);
  }

  const data = await response.json();
  return data.access_token;
}

/**
 * Create JWT for service account (simplified - needs proper signing)
 * For production, use google-auth-library
 */
function createJWT(credentials, header, payload) {
  // This is a placeholder - proper JWT signing requires crypto library
  // For now, return empty to trigger error and suggest using OAuth2
  throw new Error('JWT signing requires additional library. Please use OAuth2 authentication or install google-auth-library');
}

/**
 * Get valid access token (supports both OAuth2 and Service Account)
 */
async function getAccessToken() {
  // Check if service account is enabled
  if (config.useServiceAccount) {
    console.log('Using service account authentication...');
    return await getServiceAccountToken();
  }

  // Use OAuth2
  let tokens = loadTokens();

  if (!tokens) {
    throw new Error('Not authenticated. Please run authorization first.');
  }

  // Check if token is expired or will expire soon
  if (!tokens.expiry_date || tokens.expiry_date < Date.now() + 60000) {
    console.log('Token expired, refreshing...');
    tokens = await refreshAccessToken();
  }

  return tokens.access_token;
}

/**
 * Write data to Google Sheets
 * @param {Array} rows - Array of arrays (each row is an array of values)
 * @param {Object} options - Options
 */
async function writeToGoogleSheets(rows, options = {}) {
  const accessToken = await getAccessToken();

  const spreadsheetId = options.sheetId || config.sheetId;
  const sheetName = options.sheetName || config.sheetName;
  const range = options.range || `${sheetName}!A1`;

  // Prepare the request body
  const requestBody = {
    values: rows,
    valueInputOption: options.valueInputOption || 'USER_ENTERED'
  };

  // Use append or update based on options
  const useAppend = options.append !== false;
  const endpoint = useAppend ? 'append' : 'update';

  let url = `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${encodeURIComponent(range)}`;

  if (useAppend) {
    url += `:append?valueInputOption=${requestBody.valueInputOption}&insertDataOption=INSERT_ROWS`;
  } else {
    url += `?valueInputOption=${requestBody.valueInputOption}`;
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(requestBody)
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Google Sheets API error: ${response.status} - ${error}`);
  }

  const result = await response.json();

  console.log(`✅ Successfully wrote ${rows.length} rows to Google Sheets`);
  console.log(`   Spreadsheet: https://docs.google.com/spreadsheets/d/${spreadsheetId}`);

  return result;
}

/**
 * Batch update cells in Google Sheets
 */
async function batchUpdateToGoogleSheets(updates, options = {}) {
  const accessToken = await getAccessToken();
  const spreadsheetId = options.sheetId || config.sheetId;

  const requestBody = {
    valueInputOption: options.valueInputOption || 'USER_ENTERED',
    data: updates.map(update => ({
      range: update.range,
      values: update.values
    }))
  };

  const response = await fetch(
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values:batchUpdate`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Google Sheets batch update error: ${response.status} - ${error}`);
  }

  const result = await response.json();

  console.log(`✅ Successfully batch updated ${updates.length} ranges`);
  return result;
}

/**
 * Find first empty row in sheet
 */
async function findFirstEmptyRow() {
  const accessToken = await getAccessToken();
  const spreadsheetId = config.sheetId;
  const sheetName = config.sheetName;

  const response = await fetch(
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${encodeURIComponent(sheetName)}!A:A`,
    {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Google Sheets read error: ${response.status} - ${error}`);
  }

  const data = await response.json();

  // Find first empty row (skip header)
  if (data.values && data.values.length > 0) {
    return data.values.length + 1;
  }

  return 2; // Start at row 2 (row 1 is header)
}

/**
 * Write analysis results to Google Sheets
 */
async function writeAnalysisResults(results) {
  // Prepare header row
  const headerRow = [
    'ASIN',
    '产品标题',
    '价格',
    '评分',
    '文案分析摘要',
    '视觉分析摘要',
    '评论分析摘要',
    '市场分析摘要'
  ];

  // Prepare data rows
  const dataRows = [];
  for (const result of results) {
    if (!result.success) continue;

    const extracted = result.extracted || {};
    const analysis = result.analysis || '';

    // Extract summaries (first 300 chars of each section)
    const summary = extractSummaries(analysis);

    dataRows.push([
      extracted.asin || result.asin || '',
      extracted.title || '未知',
      extracted.price || '未知',
      extracted.rating || '未知',
      summary.brain || '',
      summary.face || '',
      summary.voice || '',
      summary.pulse || ''
    ]);
  }

  const sheetName = config.sheetName;
  const accessToken = await getAccessToken();
  const spreadsheetId = config.sheetId;

  // Append header first
  try {
    const headerResponse = await fetch(
      `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${encodeURIComponent(sheetName)}!A1:append?valueInputOption=USER_ENTERED`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          values: [headerRow]
        })
      }
    );
    // Header write result (ignore if already exists)
  } catch (e) {
    // Ignore header write error
  }

  // Then append data rows
  const response = await fetch(
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${encodeURIComponent(sheetName)}!A:A:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        values: dataRows
      })
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to append data: ${response.status} - ${errorText}`);
  }

  const result = await response.json();

  console.log(`✅ Successfully appended ${dataRows.length} rows to Google Sheets`);
  console.log(`   Updated range: ${result.updates.updatedRange}`);
  console.log(`   View: https://docs.google.com/spreadsheets/d/${spreadsheetId}`);

  return result;
}

/**
 * Extract summaries from analysis text
 */
function extractSummaries(analysis) {
  const sections = {
    brain: '',
    face: '',
    voice: '',
    pulse: ''
  };

  // Find each section and extract first 300 chars
  const sectionPatterns = [
    { name: 'brain', pattern: /第一部分[：:]*.*?文案.*?\n([\s\S]*?)(?=第二部分|第三部分|$)/i },
    { name: 'face', pattern: /第二部分[：:]*.*?视觉.*?\n([\s\S]*?)(?=第三部分|第四部分|$)/i },
    { name: 'voice', pattern: /第三部分[：:]*.*?评论.*?\n([\s\S]*?)(?=第四部分|$)/i },
    { name: 'pulse', pattern: /第四部分[：:]*.*?市场.*?\n([\s\S]*?)$/i }
  ];

  for (const section of sectionPatterns) {
    const match = analysis.match(section.pattern);
    if (match) {
      sections[section.name] = match[1].trim().substring(0, 300);
    }
  }

  return sections;
}

/**
 * Clear authentication
 */
function clearAuth() {
  if (fs.existsSync(tokenPath)) {
    fs.unlinkSync(tokenPath);
    console.log('✅ Authentication cleared');
  }
}

// Export functions
module.exports = {
  getAuthUrl,
  exchangeCodeForToken,
  getAccessToken,
  writeToGoogleSheets,
  batchUpdateToGoogleSheets,
  writeAnalysisResults,
  findFirstEmptyRow,
  clearAuth,
  config
};
