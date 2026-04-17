const https = require('https');

// Coding Agent 核心类
class CodingAgent {
  constructor() {
    this.name = 'coding-agent';
    this.enabled = true;
    this.pty = true;
    // Gemini API 配置（已填入你的 API Key）
    this.apiKey = "AIzaSyCKWmPmAkZWvI2KiblawWPUESyCp9dEjk0";
    this.modelUrl = "https://generativelanguage.googleapis.com/v1/models/gemini-3.1-pro:generateContent";
  }

  // 调用 Gemini API 的核心方法
  async callGemini(prompt) {
    return new Promise((resolve, reject) => {
      // 构建 Gemini API 请求体
      const postData = JSON.stringify({
        contents: [{
          parts: [{ text: prompt }]
        }],
        generationConfig: {
          temperature: 0.15,
          maxOutputTokens: 8192,
          topP: 0.88
        }
      });

      // 请求配置
      const options = {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        }
      };

      // 拼接 API Key 到请求 URL
      const requestUrl = `${this.modelUrl}?key=${this.apiKey}`;
      
      // 发送 HTTPS 请求
      const req = https.request(requestUrl, options, (res) => {
        let responseData = '';
        res.on('data', (chunk) => { responseData += chunk; });
        res.on('end', () => {
          try {
            const result = JSON.parse(responseData);
            // 提取 Gemini 返回的代码内容
            const code = result.candidates[0].content.parts[0].text;
            resolve(code);
          } catch (e) {
            reject(`解析响应失败: ${e.message}`);
          }
        });
      });

      // 捕获请求错误
      req.on('error', (e) => reject(`API 请求失败: ${e.message}`));
      req.write(postData);
      req.end();
    });
  }

  // 运行 Coding Agent
  async run(input) {
    try {
      // 构建编程专属提示词
      const codingPrompt = `
你是专业的编程助手，严格遵循以下规则：
1. 生成可直接运行的代码，添加清晰的中文注释；
2. 代码符合行业规范（PEP8/ESLint 等）；
3. 只返回代码和必要的说明，无多余内容。

用户需求：${input.trim()}
      `;
      
      // 调用 Gemini API 并返回结果
      const response = await this.callGemini(codingPrompt);
      return response;
    } catch (error) {
      return `Coding Agent 错误: ${error}\n请检查你的 Google API Key 是否有效。`;
    }
  }
}

// 初始化并启动 Coding Agent
const agent = new CodingAgent();
console.log('=== Coding Agent 已启动 ===');
console.log('输入你的编程需求（按 Ctrl+C 退出）：\n');

// 监听终端输入
process.stdin.on('data', async (input) => {
  const userInput = input.toString().trim();
  if (userInput) {
    const output = await agent.run(userInput);
    console.log('\n=== 生成结果 ===\n');
    console.log(output);
    console.log('\n================\n');
  }
});
