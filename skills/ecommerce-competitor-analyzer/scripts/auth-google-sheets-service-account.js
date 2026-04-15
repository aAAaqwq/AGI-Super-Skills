#!/usr/bin/env node

/**
 * Google Sheets Service Account Setup Guide
 *
 * Service accounts are simpler than OAuth2 for server-to-server communication
 * No user authorization required - just need to share the sheet with the service account email
 */

const fs = require('fs');
const path = require('path');

console.log('\n' + '='.repeat(70));
console.log('🔐 Google Sheets Service Account Setup');
console.log('='.repeat(70) + '\n');

console.log('Service accounts are recommended for server applications.\n');

console.log('📋 Steps to set up:\n');

console.log('1. Create a Service Account');
console.log('   - Go to: https://console.cloud.google.com/iam-admin/serviceaccounts');
console.log('   - Click "Create Service Account"');
console.log('   - Name: ecommerce-competitor-analyzer');
console.log('   - Click "Create and Continue"\n');

console.log('2. Grant Permissions');
console.log('   - Role: Editor (or Sheets Editor)\n');

console.log('3. Create Key');
console.log('   - Click on the service account');
console.log('   - Go to "Keys" tab');
console.log('   - Click "Add Key" → "Create New Key"');
console.log('   - Key type: JSON');
console.log('   - Download the JSON file\n');

console.log('4. Save the Key');
console.log('   - Rename the downloaded file to: service-account-key.json');
console.log('   - Move it to: ' + path.join(__dirname, '..'));
console.log('   - Or paste the content below:\n');

console.log('5. Share the Google Sheet');
console.log('   - Open your Google Sheet');
console.log('   - Click "Share" button');
console.log('   - Add the service account email (looks like: xxx@xxx.iam.gserviceaccount.com)');
console.log('   - Grant "Editor" permission\n');

console.log('6. Update .env file');
console.log('   - Add: GOOGLE_SHEETS_USE_SERVICE_ACCOUNT=true');
console.log('   - Remove or comment out: GOOGLE_SHEETS_CLIENT_ID/SECRET/REDIRECT_URI\n');

console.log('='.repeat(70));
console.log('✅ After completing these steps, the skill will use service account auth');
console.log('='.repeat(70) + '\n');

// Check if service account key already exists
const keyPath = path.join(__dirname, '..', 'service-account-key.json');
if (fs.existsSync(keyPath)) {
  console.log('✅ Service account key found at: service-account-key.json');
  console.log('   You can skip step 4!\n');
} else {
  console.log('⚠️  Service account key not found');
  console.log('   Please complete step 4 to create and save the key\n');
}
