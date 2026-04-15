#!/usr/bin/env node

/**
 * Out-of-Band Google Sheets Authorization
 * Authorization code will be displayed in the browser - just copy and paste
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

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
  console.log('🔐 Google Sheets 授权 (复制粘贴方式)');
  console.log('='.repeat(70) + '\n');

  loadEnv();

  console.log('⚠️  首次使用？请确保在 Google Cloud Console 添加此重定向 URI：');
  console.log('   urn:ietf:wg:oauth:2.0:oob\n');

  const config = {
    clientId: process.env.GOOGLE_SHEETS_CLIENT_ID,
    clientSecret: process.env.GOOGLE_SHEETS_CLIENT_SECRET,
    redirectUri: 'urn:ietf:wg:oauth:2.0:oob',
    sheetId: process.env.GOOGLE_SHEETS_ID_DEFAULT
  };

  // Generate auth URL
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

  console.log('📋 步骤 1：复制以下 URL 并在浏览器中打开\n');
  console.log('─'.repeat(70));
  console.log(authUrl);
  console.log('─'.repeat(70));
  console.log('\n💡 提示：点击上方 URL 会自动复制（取决于终端）\n');

  console.log('📝 步骤 2：完成授权后');
  console.log('   - 浏览器会显示一个授权码');
  console.log('   - 复制这个授权码\n');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  rl.question('🔑 粘贴授权码: ', async (code) => {
    code = code.trim();

    if (!code || code.length < 10) {
      console.log('\n❌ 授权码无效。授权已取消。');
      rl.close();
      process.exit(1);
    }

    console.log('\n⏳ 正在交换令牌...');

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
        let errorMsg = `令牌交换失败: ${response.status}`;

        try {
          const errorJson = JSON.parse(errorText);
          if (errorJson.error) {
            errorMsg = `错误: ${errorJson.error}`;
            if (errorJson.error_description) {
              errorMsg += `\n说明: ${errorJson.error_description}`;
            }
          }
        } catch (e) {
          // Not JSON, use text
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

      console.log('\n' + '='.repeat(70));
      console.log('✅ 授权成功！');
      console.log('='.repeat(70));

      console.log('\n📁 令牌已保存到:');
      console.log(`   ${tokenPath}`);

      console.log('\n🔑 访问令牌:');
      console.log('   ' + tokens.access_token.substring(0, 40) + '...');

      if (tokens.refresh_token) {
        console.log('\n🔄 刷新令牌:');
        console.log('   ' + tokens.refresh_token.substring(0, 40) + '...');
      }

      console.log('\n' + '='.repeat(70));
      console.log('🎉 现在可以使用 skill 写入 Google Sheets 了！');
      console.log('='.repeat(70));

      console.log('\n🧪 测试一下：');
      console.log('   node scripts/test-skill.js B08LNY11RK');

      console.log('\n📊 结果将写入到:');
      console.log(`   https://docs.google.com/spreadsheets/d/${config.sheetId}\n`);

      rl.close();
      process.exit(0);
    } catch (error) {
      console.error('\n' + '='.repeat(70));
      console.error('❌ 授权失败');
      console.error('='.repeat(70));
      console.error(`\n错误: ${error.message}\n`);

      console.error('💡 可能的问题:');
      console.error('1. 授权码无效或已过期（重新获取）');
      console.error('2. 重定向 URI 未在 Google Cloud Console 中配置');
      console.error('   请添加: urn:ietf:wg:oauth:2.0:oob');
      console.error('3. OAuth 客户端配置错误\n');

      rl.close();
      process.exit(1);
    }
  });
}

main();
