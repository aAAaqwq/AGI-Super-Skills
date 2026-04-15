#!/usr/bin/env node

/**
 * Simple Manual Google Sheets Authorization
 * Copy authorization code from browser URL
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
  console.log('\n' + '='.repeat(70));
  console.log('🔐 Google Sheets 手动授权');
  console.log('='.repeat(70) + '\n');

  loadEnv();

  const config = {
    clientId: process.env.GOOGLE_SHEETS_CLIENT_ID,
    clientSecret: process.env.GOOGLE_SHEETS_CLIENT_SECRET,
    redirectUri: process.env.GOOGLE_SHEETS_REDIRECT_URI || 'urn:ietf:wg:oauth:2.0:oob',
    sheetId: process.env.GOOGLE_SHEETS_ID_DEFAULT
  };

  console.log('📋 配置:');
  console.log(`   Spreadsheet ID: ${config.sheetId}\n`);

  // Generate auth URL using "out of band" redirect URI
  const scope = 'https://www.googleapis.com/auth/spreadsheets';
  const params = new URLSearchParams({
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    scope: scope,
    response_type: 'code',
    access_type: 'offline',
    prompt: 'consent'
  });

  const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;

  console.log('🔗 步骤 1：在浏览器中打开以下 URL：\n');
  console.log(`   ${authUrl}\n`);

  console.log('📝 步骤 2：授权后，会显示一个授权码');
  console.log('   复制这个授权码\n');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  rl.question('粘贴授权码: ', async (code) => {
    code = code.trim();

    if (!code) {
      console.log('\n❌ 未提供授权码。授权已取消。');
      rl.close();
      process.exit(1);
    }

    console.log('\n🔄 正在交换令牌...');

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
        throw new Error(`令牌交换失败: ${error}`);
      }

      const tokens = await response.json();

      // Save tokens
      const tokenPath = path.join(__dirname, '..', '.google-tokens.json');
      const tokenData = {
        ...tokens,
        expiry_date: Date.now() + (tokens.expires_in * 1000)
      };

      fs.writeFileSync(tokenPath, JSON.stringify(tokenData, null, 2));

      console.log('\n✅ 授权成功！\n');
      console.log('   令牌已保存到: .google-tokens.json');
      console.log('   访问令牌: ' + tokens.access_token.substring(0, 30) + '...');
      if (tokens.refresh_token) {
        console.log('   刷新令牌: ' + tokens.refresh_token.substring(0, 30) + '...');
      }

      console.log('\n' + '='.repeat(70));
      console.log('✅ 现在可以使用 skill 写入 Google Sheets 了！');
      console.log('='.repeat(70) + '\n');

      console.log('🧪 测试一下：');
      console.log('   node scripts/test-skill.js B08LNY11RK\n');

      rl.close();
      process.exit(0);
    } catch (error) {
      console.error('\n❌ 授权失败:', error.message);
      console.error('\n可能的问题:');
      console.error('1. 授权码无效或已过期');
      console.error('2. 客户端密钥不正确');
      console.error('3. 重定向 URI 不匹配');
      rl.close();
      process.exit(1);
    }
  });
}

main();
