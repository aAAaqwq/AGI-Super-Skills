#!/usr/bin/env node

/**
 * Exchange authorization code for access token
 */

const fs = require('fs');
const path = require('path');

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
  const code = process.argv[2];

  if (!code) {
    console.error('❌ 请提供授权码');
    console.error('用法: node exchange-token.js <授权码>');
    process.exit(1);
  }

  console.log('\n⏳ 正在交换令牌...');

  loadEnv();

  const config = {
    clientId: process.env.GOOGLE_SHEETS_CLIENT_ID,
    clientSecret: process.env.GOOGLE_SHEETS_CLIENT_SECRET,
    redirectUri: process.env.GOOGLE_SHEETS_REDIRECT_URI || 'http://localhost:8081'
  };

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
      const errorText = await response.text();
      let errorMsg = `令牌交换失败 (${response.status})`;

      try {
        const errorJson = JSON.parse(errorText);
        if (errorJson.error) {
          errorMsg = `错误: ${errorJson.error}`;
          if (errorJson.error_description) {
            errorMsg += `\n${errorJson.error_description}`;
          }
        }
      } catch (e) {
        errorMsg += `\n${errorText}`;
      }

      throw new Error(errorMsg);
    }

    const tokens = await response.json();

    // Save tokens
    const tokenPath = path.join(__dirname, '..', '.google-tokens.json');
    const tokenData = {
      ...tokens,
      expiry_date: Date.now() + (tokens.expires_in * 1000)
    };

    fs.writeFileSync(tokenPath, JSON.stringify(tokenData, null, 2));

    console.log('━'.repeat(70));
    console.log('✅ 授权成功！');
    console.log('━'.repeat(70));
    console.log(`\n📁 令牌已保存: ${tokenPath}`);
    console.log(`\n🔑 访问令牌: ${tokens.access_token.substring(0, 40)}...`);

    if (tokens.refresh_token) {
      console.log(`🔄 刷新令牌: ${tokens.refresh_token.substring(0, 40)}...`);
    }

    console.log('\n━'.repeat(70));
    console.log('🎉 现在可以使用 skill 写入 Google Sheets 了！');
    console.log('━'.repeat(70));

    console.log('\n🧪 测试一下：');
    console.log('   node scripts/test-skill.js B08LNY11RK');

    console.log('\n📊 结果将写入到:');
    console.log(`   https://docs.google.com/spreadsheets/d/${process.env.GOOGLE_SHEETS_ID_DEFAULT}\n`);

  } catch (error) {
    console.error('\n' + '━'.repeat(70));
    console.error('❌ 令牌交换失败');
    console.error('━'.repeat(70));
    console.error(`\n${error.message}\n`);
    process.exit(1);
  }
}

main();
