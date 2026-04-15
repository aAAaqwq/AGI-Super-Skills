#!/usr/bin/env node

/**
 * 手动授权流程 - 从浏览器 URL 复制授权码
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
  console.log('🔐 Google Sheets 手动授权流程');
  console.log('='.repeat(70) + '\n');

  loadEnv();

  const config = {
    clientId: process.env.GOOGLE_SHEETS_CLIENT_ID,
    clientSecret: process.env.GOOGLE_SHEETS_CLIENT_SECRET,
    redirectUri: process.env.GOOGLE_SHEETS_REDIRECT_URI || 'http://localhost:8081',
    sheetId: process.env.GOOGLE_SHEETS_ID_DEFAULT
  };

  console.log('📋 配置信息:');
  console.log(`   客户端 ID: ${config.clientId.substring(0, 20)}...`);
  console.log(`   重定向 URI: ${config.redirectUri}`);
  console.log(`   表格 ID: ${config.sheetId}\n`);

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

  console.log('━'.repeat(70));
  console.log('📍 步骤 1：在浏览器中打开以下 URL');
  console.log('━'.repeat(70));
  console.log(`\n${authUrl}\n`);
  console.log('💡 提示：选中 URL 后按 Cmd+C 复制\n');

  console.log('━'.repeat(70));
  console.log('📍 步骤 2：授权后处理');
  console.log('━'.repeat(70));
  console.log(`
   1. 登录你的 Google 账号
   2. 点击"允许"授权应用访问 Google Sheets
   3. 浏览器会尝试跳转到 ${config.redirectUri}
   4. 你会看到类似 "无法访问此网站" 或页面不存在（这是正常的！）
   5. ⚠️  **重要**：复制浏览器地址栏中的完整 URL
   6. 里面包含授权码（code 参数）

   示例 URL:
   ${config.redirectUri}/?code=4/0Axxxxxxxxxxxx&scope=...
                    ↑
                这部分就是授权码
`);

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  rl.question('\n🔑 粘贴完整的回调 URL (或只粘贴授权码): ', async (input) => {
    input = input.trim();

    if (!input) {
      console.log('\n❌ 未输入授权信息。授权已取消。');
      rl.close();
      process.exit(1);
    }

    // Extract code from URL or use input directly
    let code = input;
    if (input.includes('code=')) {
      const match = input.match(/[?&]code=([^&]+)/);
      if (match) {
        code = match[1];
      }
    }

    if (code.length < 10) {
      console.log('\n❌ 授权码太短，可能不完整。');
      rl.close();
      process.exit(1);
    }

    console.log('\n⏳ 正在交换令牌...');
    console.log(`   授权码: ${code.substring(0, 20)}...\n`);

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

      console.log('\n🧪 测试命令:');
      console.log('   node scripts/test-skill.js B08LNY11RK');

      console.log('\n📊 结果将写入:');
      console.log(`   https://docs.google.com/spreadsheets/d/${config.sheetId}\n`);

      rl.close();
      process.exit(0);
    } catch (error) {
      console.error('\n' + '━'.repeat(70));
      console.error('❌ 授权失败');
      console.error('━'.repeat(70));
      console.error(`\n${error.message}\n`);

      console.error('💡 常见问题:');
      console.error('1. 授权码已过期（重新获取）');
      console.error('2. 重定向 URI 未在 Google Cloud Console 中配置');
      console.error(`   需要添加: ${config.redirectUri}`);
      console.error('3. 授权码格式不正确\n');

      rl.close();
      process.exit(1);
    }
  });
}

main();
