/**
 * content-distributor / publish.ts
 * 多平台发布编排器
 *
 * 用法:
 *   tsx publish.ts <markdown-file> --platforms wechat,zhihu,xhs [options]
 *   tsx publish.ts article.md --platforms wechat --template tech --publish
 *   tsx publish.ts article.md --platforms zhihu,juejin,csdn --dry-run
 *   tsx publish.ts article.md --all --dry-run
 *
 * 流程:
 * 1. 读取 Markdown
 * 2. 对每个目标平台: convert → 格式转换
 * 3. 微信公众号: 调用官方 API
 * 4. 其他平台: 生成 Playwright 操作指令 (由 Agent 执行)
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { convert, type PlatformName, type TemplateName } from './convert.js';
import { publishToWechat, type WechatConfig } from './platforms/wechat.js';
import { generateBatchPlan, PLATFORM_URLS } from './platforms/browser-publish.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ─── CLI ─────────────────────────────────────────────────────────────

interface PublishArgs {
  input: string;
  platforms: PlatformName[];
  template: TemplateName;
  dryRun: boolean;
  publish: boolean;          // 微信: 是否直接发布 (默认只创建草稿)
  tags?: string[];
  coverImage?: string;
  title?: string;
  outputDir: string;
}

function parseArgs(): PublishArgs {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    console.log(`
📦 content-distributor / publish

用法:
  tsx publish.ts <markdown-file> [options]

选项:
  --platforms <list>   目标平台 (逗号分隔): wechat,zhihu,csdn,juejin,jianshu,xhs,toutiao,baijiahao,twitter
  --all                发布到所有平台
  --template <name>    排版模板: tech | minimal | business | dark-tech (默认: tech)
  --tags <list>        标签 (逗号分隔)
  --cover <path>       封面图路径
  --title <title>      文章标题 (覆盖 Markdown h1)
  --dry-run            只转换不发布, 生成操作计划
  --publish            微信公众号: 直接发布 (默认只创建草稿)
  --output <dir>       输出目录

示例:
  tsx publish.ts article.md --platforms wechat --template tech
  tsx publish.ts article.md --platforms zhihu,juejin --dry-run
  tsx publish.ts article.md --all --dry-run --tags "AI,技术"
`);
    process.exit(0);
  }

  const input = args[0];
  const platformsIdx = args.indexOf('--platforms');
  const templateIdx = args.indexOf('--template');
  const tagsIdx = args.indexOf('--tags');
  const coverIdx = args.indexOf('--cover');
  const titleIdx = args.indexOf('--title');
  const outputIdx = args.indexOf('--output');

  const ALL_PLATFORMS: PlatformName[] = [
    'wechat', 'zhihu', 'csdn', 'juejin', 'jianshu',
    'xhs', 'toutiao', 'baijiahao', 'twitter',
  ];

  let platforms: PlatformName[];
  if (args.includes('--all')) {
    platforms = ALL_PLATFORMS;
  } else if (platformsIdx >= 0) {
    platforms = args[platformsIdx + 1].split(',').map(s => s.trim()) as PlatformName[];
  } else {
    platforms = ['wechat']; // 默认公众号
  }

  return {
    input,
    platforms,
    template: (templateIdx >= 0 ? args[templateIdx + 1] : 'tech') as TemplateName,
    dryRun: args.includes('--dry-run'),
    publish: args.includes('--publish'),
    tags: tagsIdx >= 0 ? args[tagsIdx + 1].split(',').map(s => s.trim()) : undefined,
    coverImage: coverIdx >= 0 ? args[coverIdx + 1] : undefined,
    title: titleIdx >= 0 ? args[titleIdx + 1] : undefined,
    outputDir: outputIdx >= 0 ? args[outputIdx + 1] : path.join(__dirname, '..', 'output'),
  };
}

// ─── Main ────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const opts = parseArgs();

  if (!fs.existsSync(opts.input)) {
    console.error(`❌ 文件不存在: ${opts.input}`);
    process.exit(1);
  }

  console.log(`\n📦 content-distributor`);
  console.log(`📝 文章: ${path.basename(opts.input)}`);
  console.log(`🎨 模板: ${opts.template}`);
  console.log(`🎯 平台: ${opts.platforms.join(', ')}`);
  console.log(`📁 输出: ${opts.outputDir}`);
  console.log(`🔍 模式: ${opts.dryRun ? 'DRY RUN' : '正式发布'}`);
  console.log('');

  // 1. 转换所有平台
  console.log('🔄 格式转换中...\n');
  const results = convert({
    input: opts.input,
    template: opts.template,
    all: true,
    outputDir: opts.outputDir,
    title: opts.title,
  });

  // 保存转换结果
  fs.mkdirSync(opts.outputDir, { recursive: true });
  for (const r of results) {
    const ext = r.format === 'html' ? 'html' : r.format === 'markdown' ? 'md' : 'txt';
    const outPath = path.join(opts.outputDir, `${r.platform}.${ext}`);
    fs.writeFileSync(outPath, r.content, 'utf-8');
    console.log(`  ✅ ${r.platform} → ${ext} (${(r.content.length / 1024).toFixed(1)}KB)`);
  }

  const title = results[0]?.title || '未命名文章';

  // 2. 微信公众号 API 发布
  if (opts.platforms.includes('wechat')) {
    const appId = process.env.WECHAT_APPID;
    const appSecret = process.env.WECHAT_APPSECRET;

    if (!appId || !appSecret) {
      console.log('\n⚠️ 微信公众号: WECHAT_APPID / WECHAT_APPSECRET 未配置');
      console.log('  设置环境变量后重试, 或使用 --dry-run 模式');
    } else if (!opts.dryRun) {
      console.log('\n🔑 微信公众号发布...');
      const wechatResult = results.find(r => r.platform === 'wechat');
      if (wechatResult) {
        const config: WechatConfig = { appId, appSecret };
        const result = await publishToWechat(config, {
          title,
          content: wechatResult.content,
          author: 'Daniel Li',
        }, {
          publish: opts.publish,
          thumbPath: opts.coverImage,
          contentBasePath: path.dirname(opts.input),
        });
        console.log(`  ✅ 草稿 ID: ${result.draftId}`);
        if (result.publishId) {
          console.log(`  🚀 发布 ID: ${result.publishId}`);
        }
      }
    }
  }

  // 3. 其他平台: 生成 Playwright 操作指令
  const browserPlatforms = opts.platforms.filter(p => p !== 'wechat' && PLATFORM_URLS[p]);
  if (browserPlatforms.length > 0) {
    console.log(`\n📋 浏览器发布计划 (${browserPlatforms.length} 个平台):\n`);

    const contentMap = new Map<string, { content: string; format: string }>();
    for (const r of results) {
      contentMap.set(r.platform, { content: r.content, format: r.format });
    }

    const plan = generateBatchPlan({
      platforms: browserPlatforms,
      contents: contentMap,
      title,
      tags: opts.tags,
      coverImage: opts.coverImage,
      dryRun: opts.dryRun,
    });

    const planPath = path.join(opts.outputDir, 'publish-plan.md');
    fs.writeFileSync(planPath, plan, 'utf-8');
    console.log(plan);
    console.log(`\n📄 操作计划已保存: ${planPath}`);
  }

  console.log('\n✅ 完成!\n');
}

main().catch(err => {
  console.error('❌ 发布失败:', err);
  process.exit(1);
});
