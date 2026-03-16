/**
 * content-distributor / platforms / browser-publish.ts
 * 基于 Playwright 的浏览器自动化发布器
 *
 * 通过 OpenClaw browser 工具或 Playwright 操作各平台编辑器
 * 支持: 知乎、掘金、CSDN、简书、小红书、今日头条、百家号
 *
 * 设计原则:
 * - 每个平台一个独立的 publish 函数
 * - 复用 auth-manager 管理的 browser profile / cookie
 * - 失败时截图保存到 output/screenshots/
 */

import fs from 'fs';
import path from 'path';

// ─── Types ───────────────────────────────────────────────────────────

export interface PublishOptions {
  title: string;
  content: string;           // 转换后的内容 (HTML/Markdown/纯文本)
  format: 'html' | 'markdown' | 'text';
  tags?: string[];
  coverImage?: string;       // 本地封面图路径
  column?: string;           // 知乎专栏 slug
  category?: string;         // 平台分类
  dryRun?: boolean;          // 只填写不提交
}

export interface PublishResult {
  platform: string;
  success: boolean;
  url?: string;
  error?: string;
  screenshot?: string;
}

// ─── Platform Configs ────────────────────────────────────────────────

export const PLATFORM_URLS: Record<string, string> = {
  zhihu:     'https://zhuanlan.zhihu.com/write',
  juejin:    'https://juejin.cn/editor/drafts/new?v=2',
  csdn:      'https://editor.csdn.net/md',
  jianshu:   'https://www.jianshu.com/writer',
  xhs:       'https://creator.xiaohongshu.com/publish/publish',
  toutiao:   'https://mp.toutiao.com/profile_v4/graphic/publish',
  baijiahao: 'https://baijiahao.baidu.com/builder/rc/edit',
  bilibili:  'https://member.bilibili.com/platform/upload/text/edit',
};

// ─── Instructions for Agent (OpenClaw browser tool) ──────────────────

/**
 * 生成各平台发布操作指令
 * Agent 使用 OpenClaw browser 工具执行这些步骤
 */
export function generatePublishInstructions(platform: string, opts: PublishOptions): string {
  const url = PLATFORM_URLS[platform];
  if (!url) return `❌ 未知平台: ${platform}`;

  const base = `
## ${platform} 发布操作指令

1. 打开编辑器: browser navigate url="${url}"
2. 等待页面加载: browser snapshot
3. 检查登录状态 (如未登录, 提示用户手动登录)
`;

  switch (platform) {
    case 'zhihu':
      return base + `
4. 输入标题: 找到标题输入框, type "${opts.title}"
5. 切换到 Markdown 模式 (如有)
6. 粘贴内容到编辑器
${opts.tags?.length ? `7. 添加话题标签: ${opts.tags.join(', ')}` : ''}
${opts.coverImage ? `8. 上传封面图: ${opts.coverImage}` : ''}
${opts.dryRun ? '⏸️ DRY RUN: 不点击发布按钮' : '9. 点击 "发布" 按钮'}
`;

    case 'juejin':
      return base + `
4. 输入标题: 找到标题输入框, type "${opts.title}"
5. 编辑器默认 Markdown 模式, 直接粘贴内容
6. 点击 "发布" 打开设置面板
${opts.tags?.length ? `7. 添加标签: ${opts.tags.join(', ')}` : ''}
${opts.category ? `8. 选择分类: ${opts.category}` : '7. 选择分类: 前端/后端/AI'}
${opts.coverImage ? `9. 上传封面图` : ''}
${opts.dryRun ? '⏸️ DRY RUN: 不点击最终确认' : '10. 确认发布'}
`;

    case 'csdn':
      return base + `
4. 默认 Markdown 编辑器
5. 输入标题
6. 粘贴 Markdown 内容
${opts.tags?.length ? `7. 添加标签: ${opts.tags.join(', ')}` : ''}
${opts.dryRun ? '⏸️ DRY RUN: 不点击发布' : '8. 点击 "发布文章"'}
`;

    case 'xhs':
      return base + `
4. 选择 "图文" 发布模式
5. 输入标题: "${opts.title}"
6. 粘贴纯文本内容 (已转换为 emoji 格式)
${opts.coverImage ? `7. 上传封面图: ${opts.coverImage}` : '7. 上传至少一张图片'}
${opts.tags?.length ? `8. 添加话题: ${opts.tags.map(t => '#' + t).join(' ')}` : ''}
${opts.dryRun ? '⏸️ DRY RUN: 不点击发布' : '9. 点击 "发布"'}
`;

    case 'toutiao':
      return base + `
4. 输入标题: "${opts.title}"
5. 切换到源代码模式
6. 粘贴 HTML 内容
${opts.coverImage ? `7. 上传封面图 (建议 16:9)` : ''}
${opts.dryRun ? '⏸️ DRY RUN: 不点击发布' : '8. 点击 "发布"'}
`;

    case 'baijiahao':
      return base + `
4. 输入标题: "${opts.title}"
5. 使用富文本编辑器, 粘贴 HTML
${opts.coverImage ? `6. 上传封面图` : ''}
${opts.dryRun ? '⏸️ DRY RUN: 不点击发布' : '7. 点击 "发布"'}
`;

    default:
      return base + `
4. 找到标题输入框, 输入标题
5. 找到内容编辑器, 粘贴内容
6. ${opts.dryRun ? '停止, 不发布' : '点击发布按钮'}
`;
  }
}

// ─── Content Clipboard Prep ──────────────────────────────────────────

/**
 * 将内容写入临时文件, 供 browser 工具读取粘贴
 */
export function prepareContentFile(content: string, platform: string): string {
  const tmpDir = path.join(process.cwd(), 'output', '.tmp');
  fs.mkdirSync(tmpDir, { recursive: true });

  const ext = content.includes('<') ? 'html' : 'txt';
  const tmpFile = path.join(tmpDir, `${platform}-content.${ext}`);
  fs.writeFileSync(tmpFile, content, 'utf-8');

  return tmpFile;
}

// ─── Batch Publisher ─────────────────────────────────────────────────

export interface BatchPublishOptions {
  platforms: string[];
  contents: Map<string, { content: string; format: string }>;
  title: string;
  tags?: string[];
  coverImage?: string;
  dryRun?: boolean;
}

/**
 * 生成批量发布计划
 * 返回各平台的操作指令, 由 Agent 按顺序执行
 */
export function generateBatchPlan(opts: BatchPublishOptions): string {
  const lines: string[] = [];
  lines.push(`# 📦 批量发布计划`);
  lines.push(`\n**文章**: ${opts.title}`);
  lines.push(`**目标平台** (${opts.platforms.length}): ${opts.platforms.join(', ')}`);
  lines.push(`**模式**: ${opts.dryRun ? '🔍 预览 (不发布)' : '🚀 正式发布'}`);
  lines.push('');

  for (const platform of opts.platforms) {
    const platformContent = opts.contents.get(platform);
    if (!platformContent) {
      lines.push(`\n## ❌ ${platform}: 缺少转换后的内容`);
      continue;
    }

    const tmpFile = prepareContentFile(platformContent.content, platform);
    const instructions = generatePublishInstructions(platform, {
      title: opts.title,
      content: platformContent.content,
      format: platformContent.format as 'html' | 'markdown' | 'text',
      tags: opts.tags,
      coverImage: opts.coverImage,
      dryRun: opts.dryRun,
    });

    lines.push(instructions);
    lines.push(`📄 内容文件: ${tmpFile}`);
    lines.push('---');
  }

  return lines.join('\n');
}
