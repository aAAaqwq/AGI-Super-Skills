#!/usr/bin/env node

/**
 * Environment Variable Verification Script
 * Checks if all required and optional environment variables are configured
 */

const fs = require('fs');
const path = require('path');

// ANSI color codes for terminal output
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  blue: '\x1b[34m'
};

function log(color, symbol, message) {
  console.log(`${color}${symbol}${colors.reset} ${message}`);
}

function checkEnvFile() {
  const envPath = path.join(__dirname, '..', '.env');

  if (!fs.existsSync(envPath)) {
    log(colors.red, '❌', '.env file not found');
    log(colors.yellow, '💡', 'Copy .env.example to .env and fill in your values');
    return false;
  }

  log(colors.green, '✅', '.env file found');
  return true;
}

function checkRequiredEnv(key) {
  const value = process.env[key];

  if (!value || value === '' || value.includes('your_') || value.includes('YOUR_')) {
    log(colors.red, '❌', `${key}: Not configured`);
    return false;
  }

  // Check for realistic length
  if (value.length < 10) {
    log(colors.yellow, '⚠️', `${key}: Value seems too short (length: ${value.length})`);
    return false;
  }

  // Mask for display
  const masked = value.substring(0, 8) + '...' + value.substring(value.length - 4);
  log(colors.green, '✅', `${key}: Configured (${masked})`);
  return true;
}

function checkOptionalEnv(key) {
  const value = process.env[key];

  if (!value || value === '') {
    log(colors.blue, 'ℹ️', `${key}: Optional (not configured)`);
    return null;
  }

  const masked = value.substring(0, 8) + '...' + value.substring(value.length - 4);
  log(colors.green, '✅', `${key}: Configured (${masked})`);
  return true;
}

function loadEnvFile() {
  const envPath = path.join(__dirname, '..', '.env');

  try {
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
  } catch (error) {
    log(colors.red, '❌', `Failed to load .env: ${error.message}`);
    return false;
  }

  return true;
}

function main() {
  console.log('\n🔍 Environment Variable Verification\n');
  console.log('=' .repeat(50));

  // Check if .env file exists
  if (!checkEnvFile()) {
    console.log('\n' + '='.repeat(50));
    process.exit(1);
  }

  // Load .env file
  console.log();
  if (!loadEnvFile()) {
    console.log('\n' + '='.repeat(50));
    process.exit(1);
  }

  console.log();
  console.log('Required Variables:');
  console.log('-'.repeat(50));

  // Check required variables
  const requiredVars = ['OLOSTEP_API_KEY', 'GEMINI_API_KEY'];
  let requiredOk = true;

  for (const key of requiredVars) {
    if (!checkRequiredEnv(key)) {
      requiredOk = false;
    }
  }

  console.log();
  console.log('Optional Variables:');
  console.log('-'.repeat(50));

  // Check optional variables
  const optionalVars = ['GOOGLE_SHEETS_CREDENTIALS', 'GOOGLE_SHEETS_ID', 'MARKDOWN_OUTPUT_DIR'];
  for (const key of optionalVars) {
    checkOptionalEnv(key);
  }

  console.log();
  console.log('='.repeat(50));

  if (requiredOk) {
    log(colors.green, '\n✅', 'All required environment variables are configured!');
    log(colors.blue, '💡', 'You can now use the skill:\n');
    console.log('   "分析 B0C4YT8S6H"');
    console.log('   "分析 B0C4YT8S6H, B08N5WRQ1Y, B0CLFH7CCV"\n');
  } else {
    log(colors.red, '\n❌', 'Some required environment variables are missing');
    log(colors.yellow, '💡', 'Please edit .env file and add the missing values\n');
    console.log('See docs/SETUP.md for detailed instructions\n');
    process.exit(1);
  }
}

// Run the script
main();
