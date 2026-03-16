/**
 * content-distributor / demo.ts
 * 快速验证: 读一篇测试 Markdown → 转换为公众号 HTML
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { convert } from './convert.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEMO_DIR = path.join(__dirname, '..', 'output', 'demo');

// 测试文章
const DEMO_MD = `# AI Agent 时代已经到来

> 2026 年，AI Agent 不再是概念，而是生产力工具。

## 什么是 AI Agent？

AI Agent 是一种**自主决策、自动执行**的智能体。它不只是回答问题，而是能够：

- 🔍 主动搜索和分析信息
- 📝 独立完成复杂任务
- 🤖 与其他 Agent 协作
- 📊 持续学习和优化

## 核心技术栈

目前主流的 Agent 框架包括：

| 框架 | 语言 | 特点 |
|------|------|------|
| OpenClaw | Node.js | 多 Agent 协作, 本地优先 |
| LangChain | Python | 生态丰富, 社区活跃 |
| AutoGen | Python | 微软出品, 多 Agent 对话 |

### 代码示例

\`\`\`typescript
// 一个简单的 Agent 定义
const agent = new Agent({
  name: "researcher",
  model: "claude-opus-4.6",
  tools: ["web_search", "file_read", "code_exec"],
  instructions: "你是一个专业研究员"
});

await agent.run("分析 2026 年 AI 行业趋势");
\`\`\`

## 未来展望

AI Agent 将从**辅助工具**进化为**数字员工**。想象一下：

1. 一个 Agent 团队自动处理你的邮件
2. 另一个团队管理你的投资组合
3. 还有一个团队帮你创作和分发内容

---

**这不是科幻，这是现在。**

关注我，一起探索 AI Agent 的无限可能 🚀
`;

async function main(): Promise<void> {
  // 写入测试 Markdown
  fs.mkdirSync(DEMO_DIR, { recursive: true });
  const mdPath = path.join(DEMO_DIR, 'demo-article.md');
  fs.writeFileSync(mdPath, DEMO_MD, 'utf-8');

  console.log('📝 Demo: Markdown → 多平台转换\n');
  console.log('═'.repeat(50));

  // 1. 通用 HTML
  console.log('\n🎨 通用 HTML (tech 模板):');
  const genericResults = convert({ input: mdPath, template: 'tech' });
  for (const r of genericResults) {
    const outPath = path.join(DEMO_DIR, `generic.html`);
    fs.writeFileSync(outPath, r.content, 'utf-8');
    console.log(`  ✅ ${outPath} (${(r.content.length / 1024).toFixed(1)}KB)`);
  }

  // 2. 微信公众号 (CSS 内联)
  console.log('\n📱 微信公众号 (CSS 内联):');
  const wechatResults = convert({ input: mdPath, template: 'tech', platform: 'wechat' });
  for (const r of wechatResults) {
    const outPath = path.join(DEMO_DIR, `wechat.html`);
    fs.writeFileSync(outPath, r.content, 'utf-8');
    console.log(`  ✅ ${outPath} (${(r.content.length / 1024).toFixed(1)}KB)`);

    // 检查 CSS 是否内联
    const hasStyleTag = r.content.includes('<style');
    const hasInlineStyle = r.content.includes('style="');
    console.log(`  📋 <style> 标签: ${hasStyleTag ? '❌ 仍存在' : '✅ 已移除'}`);
    console.log(`  📋 inline style: ${hasInlineStyle ? '✅ 已内联' : '❌ 未内联'}`);
  }

  // 3. 小红书 (纯文本)
  console.log('\n📕 小红书 (纯文本 + emoji):');
  const xhsResults = convert({ input: mdPath, template: 'tech', platform: 'xhs' });
  for (const r of xhsResults) {
    const outPath = path.join(DEMO_DIR, `xhs.txt`);
    fs.writeFileSync(outPath, r.content, 'utf-8');
    console.log(`  ✅ ${outPath} (${(r.content.length / 1024).toFixed(1)}KB)`);
    // 显示前 10 行
    const preview = r.content.split('\n').slice(0, 10).join('\n');
    console.log(`\n  ── 预览 ──`);
    console.log(`  ${preview.split('\n').join('\n  ')}`);
  }

  // 4. 知乎 (Markdown)
  console.log('\n\n📘 知乎 (Markdown):');
  const zhihuResults = convert({ input: mdPath, platform: 'zhihu' });
  for (const r of zhihuResults) {
    const outPath = path.join(DEMO_DIR, `zhihu.md`);
    fs.writeFileSync(outPath, r.content, 'utf-8');
    console.log(`  ✅ ${outPath} (${(r.content.length / 1024).toFixed(1)}KB)`);
  }

  // 5. Twitter thread
  console.log('\n🐦 Twitter (Thread 拆分):');
  const twitterResults = convert({ input: mdPath, platform: 'twitter' });
  for (const r of twitterResults) {
    const outPath = path.join(DEMO_DIR, `twitter.txt`);
    fs.writeFileSync(outPath, r.content, 'utf-8');
    console.log(`  ✅ ${outPath}`);
    const tweets = r.content.split('---').length;
    console.log(`  📋 拆分为 ${tweets} 条推文`);
  }

  // 6. 全部平台
  console.log('\n📦 全部平台:');
  const allResults = convert({ input: mdPath, template: 'business', all: true });
  for (const r of allResults) {
    const ext = r.format === 'html' ? 'html' : r.format === 'markdown' ? 'md' : 'txt';
    const outPath = path.join(DEMO_DIR, 'all', `${r.platform}.${ext}`);
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, r.content, 'utf-8');
    console.log(`  ✅ ${r.platform}.${ext} (${r.format}, ${(r.content.length / 1024).toFixed(1)}KB)`);
  }

  console.log('\n═'.repeat(50));
  console.log(`\n✅ Demo 完成! 输出目录: ${DEMO_DIR}\n`);
}

main().catch(console.error);
