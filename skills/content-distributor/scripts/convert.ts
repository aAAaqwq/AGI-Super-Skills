/**
 * content-distributor / convert.ts
 * Markdown → 多平台格式转换器
 *
 * 用法:
 *   tsx convert.ts <markdown-file> [--template tech|minimal|business|dark-tech] [--platform wechat|zhihu|csdn|juejin|xhs|toutiao]
 *   tsx convert.ts input.md --template tech --platform wechat
 *   tsx convert.ts input.md --platform xhs          # 小红书纯文本
 *   tsx convert.ts input.md --all                    # 输出所有平台格式
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import MarkdownIt from 'markdown-it';
import juice from 'juice';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATES_DIR = path.join(__dirname, '..', 'templates');
const OUTPUT_DIR = path.join(__dirname, '..', 'output');

// ─── Types ───────────────────────────────────────────────────────────

export type TemplateName = 'tech' | 'minimal' | 'business' | 'dark-tech';
export type PlatformName = 'wechat' | 'zhihu' | 'csdn' | 'juejin' | 'jianshu'
  | 'xhs' | 'toutiao' | 'baijiahao' | 'bilibili' | 'weibo' | 'twitter';

export interface ConvertOptions {
  /** 输入 Markdown 文件路径 */
  input: string;
  /** 排版模板 */
  template?: TemplateName;
  /** 目标平台 (不指定则输出通用 HTML) */
  platform?: PlatformName;
  /** 输出所有平台格式 */
  all?: boolean;
  /** 输出目录 */
  outputDir?: string;
  /** 文章标题 (覆盖 Markdown 第一个 h1) */
  title?: string;
}

export interface ConvertResult {
  platform: PlatformName | 'generic';
  format: 'html' | 'markdown' | 'text';
  content: string;
  title: string;
  outputPath?: string;
}

// ─── Markdown Parser ─────────────────────────────────────────────────

function createMarkdownParser(): MarkdownIt {
  const md = new MarkdownIt({
    html: true,
    linkify: true,
    typographer: true,
    breaks: false,
  });

  // 简单代码高亮 (无需 hljs 依赖, 用 class 标注语言)
  md.options.highlight = (str: string, lang: string) => {
    const escapedStr = md.utils.escapeHtml(str);
    if (lang) {
      return `<pre class="hljs"><code class="language-${lang}">${escapedStr}</code></pre>`;
    }
    return `<pre class="hljs"><code>${escapedStr}</code></pre>`;
  };

  return md;
}

// ─── Template Loader ─────────────────────────────────────────────────

function loadTemplate(name: TemplateName): string {
  const cssPath = path.join(TEMPLATES_DIR, `${name}.css`);
  if (!fs.existsSync(cssPath)) {
    console.warn(`⚠️ Template "${name}" not found, falling back to "tech"`);
    return fs.readFileSync(path.join(TEMPLATES_DIR, 'tech.css'), 'utf-8');
  }
  return fs.readFileSync(cssPath, 'utf-8');
}

// ─── Title Extractor ─────────────────────────────────────────────────

function extractTitle(markdown: string): string {
  const match = markdown.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : '未命名文章';
}

// ─── Platform Adapters ───────────────────────────────────────────────

/**
 * 微信公众号: CSS 必须内联, 不支持外部样式/class
 * - 所有 CSS 内联到 style 属性
 * - 不能用 <style> 标签
 * - 图片必须上传到公众号素材库
 */
function convertForWechat(html: string, css: string): string {
  const wrappedHtml = `<div class="cd-article">${html}</div>`;
  const fullHtml = `<style>${css}</style>${wrappedHtml}`;

  // juice 将 CSS 内联到每个元素的 style 属性
  const inlined = juice(fullHtml, {
    removeStyleTags: true,
    preserveImportant: true,
    applyStyleTags: true,
    applyAttributeSelectors: false,
    applyWidthAttributes: false,
    applyHeightAttributes: false,
    insertPreservedExtraCss: false,
    extraCss: '',
  });

  return inlined;
}

/**
 * 知乎: 支持 Markdown 直接粘贴, 但富文本编辑器更稳定
 * 返回 Markdown (知乎编辑器原生支持)
 */
function convertForZhihu(markdown: string): string {
  // 知乎支持大部分标准 Markdown, 做少量适配
  let content = markdown;

  // 知乎不支持 HTML 标签, 移除
  content = content.replace(/<[^>]+>/g, '');

  // 知乎支持 $LaTeX$ 公式
  // 保留原样

  return content;
}

/**
 * CSDN / 掘金: 标准 Markdown
 */
function convertForMarkdownPlatform(markdown: string): string {
  return markdown;
}

/**
 * 小红书: 纯文本 + emoji 排版
 * - 无 Markdown 支持
 * - 标题用 emoji 装饰
 * - 段落间空行
 * - 标签 # 放末尾
 */
function convertForXHS(markdown: string, title: string): string {
  const lines: string[] = [];

  // 标题
  lines.push(`📌 ${title}`);
  lines.push('');

  const mdLines = markdown.split('\n');
  let inCodeBlock = false;

  for (const line of mdLines) {
    // 跳过代码块
    if (line.startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      if (inCodeBlock) lines.push('💻 代码片段:');
      else lines.push('');
      continue;
    }
    if (inCodeBlock) {
      lines.push(`  ${line}`);
      continue;
    }

    // h1 标题 (跳过, 已在开头)
    if (line.match(/^#\s+/)) continue;

    // h2 标题
    if (line.match(/^##\s+/)) {
      const text = line.replace(/^##\s+/, '');
      lines.push('');
      lines.push(`✨ ${text}`);
      lines.push('');
      continue;
    }

    // h3 标题
    if (line.match(/^###\s+/)) {
      const text = line.replace(/^###\s+/, '');
      lines.push(`▪️ ${text}`);
      continue;
    }

    // 引用
    if (line.match(/^>\s*/)) {
      const text = line.replace(/^>\s*/, '');
      lines.push(`💡 ${text}`);
      continue;
    }

    // 列表
    if (line.match(/^[-*]\s+/)) {
      const text = line.replace(/^[-*]\s+/, '');
      lines.push(`  ✅ ${text}`);
      continue;
    }

    // 有序列表
    if (line.match(/^\d+\.\s+/)) {
      lines.push(line);
      continue;
    }

    // 分隔线
    if (line.match(/^---+$/)) {
      lines.push('➖➖➖➖➖');
      continue;
    }

    // 图片
    if (line.match(/^!\[/)) {
      lines.push('📷 [图片]');
      continue;
    }

    // 链接 → 纯文本
    let text = line.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
    // 粗体
    text = text.replace(/\*\*([^*]+)\*\*/g, '「$1」');
    // 斜体
    text = text.replace(/\*([^*]+)\*/g, '$1');
    // 行内代码
    text = text.replace(/`([^`]+)`/g, '[$1]');

    lines.push(text);
  }

  // 添加默认标签
  lines.push('');
  lines.push('➖➖➖➖➖');
  lines.push('#AI #科技 #干货分享');

  return lines.join('\n');
}

/**
 * 今日头条 / 百家号: 富文本 HTML
 * 类似公众号但限制更少
 */
function convertForRichText(html: string, css: string): string {
  const wrappedHtml = `<div class="cd-article">${html}</div>`;
  const fullHtml = `<style>${css}</style>${wrappedHtml}`;
  return juice(fullHtml, { removeStyleTags: true, preserveImportant: true });
}

/**
 * Twitter/X: 280 字符摘要 + thread 拆分
 */
function convertForTwitter(markdown: string, title: string): string {
  const lines: string[] = [];

  // 提取纯文本
  let plainText = markdown
    .replace(/^#+\s+/gm, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/```[\s\S]*?```/g, '[code]')
    .replace(/^>\s*/gm, '')
    .replace(/^[-*]\s+/gm, '• ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  // 拆分为 ~260 字符的 tweets (留 20 字符给 thread 编号)
  const sentences = plainText.split(/(?<=[。！？.!?\n])\s*/);
  let currentTweet = `🧵 ${title}\n\n`;
  let tweetNum = 1;

  for (const sentence of sentences) {
    if ((currentTweet + sentence).length > 260 && currentTweet.length > 20) {
      lines.push(`[${tweetNum}/${Math.ceil(sentences.length / 3)}] ${currentTweet.trim()}`);
      tweetNum++;
      currentTweet = '';
    }
    currentTweet += sentence + ' ';
  }

  if (currentTweet.trim()) {
    lines.push(`[${tweetNum}] ${currentTweet.trim()}`);
  }

  return lines.join('\n\n---\n\n');
}

// ─── Main Converter ──────────────────────────────────────────────────

export function convert(options: ConvertOptions): ConvertResult[] {
  const markdown = fs.readFileSync(options.input, 'utf-8');
  const title = options.title || extractTitle(markdown);
  const templateName = options.template || 'tech';
  const css = loadTemplate(templateName);
  const md = createMarkdownParser();
  const html = md.render(markdown);

  const results: ConvertResult[] = [];

  const platforms: PlatformName[] = options.all
    ? ['wechat', 'zhihu', 'csdn', 'juejin', 'jianshu', 'xhs', 'toutiao', 'baijiahao', 'twitter']
    : options.platform
      ? [options.platform]
      : [];

  // 无指定平台则输出通用 HTML
  if (platforms.length === 0) {
    const genericHtml = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${title}</title>
<style>${css}</style></head>
<body><div class="cd-article">${html}</div></body></html>`;

    results.push({
      platform: 'generic',
      format: 'html',
      content: genericHtml,
      title,
    });
    return results;
  }

  for (const platform of platforms) {
    let content: string;
    let format: 'html' | 'markdown' | 'text';

    switch (platform) {
      case 'wechat':
        content = convertForWechat(html, css);
        format = 'html';
        break;
      case 'zhihu':
        content = convertForZhihu(markdown);
        format = 'markdown';
        break;
      case 'csdn':
      case 'juejin':
      case 'jianshu':
      case 'bilibili':
        content = convertForMarkdownPlatform(markdown);
        format = 'markdown';
        break;
      case 'xhs':
        content = convertForXHS(markdown, title);
        format = 'text';
        break;
      case 'toutiao':
      case 'baijiahao':
        content = convertForRichText(html, css);
        format = 'html';
        break;
      case 'twitter':
        content = convertForTwitter(markdown, title);
        format = 'text';
        break;
      default:
        content = convertForRichText(html, css);
        format = 'html';
    }

    results.push({ platform, format, content, title });
  }

  return results;
}

// ─── File Output ─────────────────────────────────────────────────────

function writeResults(results: ConvertResult[], outputDir: string): void {
  fs.mkdirSync(outputDir, { recursive: true });

  for (const result of results) {
    const ext = result.format === 'html' ? 'html' : result.format === 'markdown' ? 'md' : 'txt';
    const filename = `${result.platform}.${ext}`;
    const outputPath = path.join(outputDir, filename);
    fs.writeFileSync(outputPath, result.content, 'utf-8');
    result.outputPath = outputPath;
    console.log(`  ✅ ${result.platform} → ${filename} (${(result.content.length / 1024).toFixed(1)}KB)`);
  }
}

// ─── CLI ─────────────────────────────────────────────────────────────

function main(): void {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    console.log(`
📦 content-distributor / convert

用法:
  tsx convert.ts <markdown-file> [options]

选项:
  --template <name>    排版模板: tech | minimal | business | dark-tech (默认: tech)
  --platform <name>    目标平台: wechat | zhihu | csdn | juejin | jianshu | xhs | toutiao | baijiahao | twitter
  --all                输出所有平台格式
  --output <dir>       输出目录 (默认: ./output)
  --title <title>      文章标题 (覆盖 Markdown h1)

示例:
  tsx convert.ts article.md --template tech --platform wechat
  tsx convert.ts article.md --all --output ./dist
  tsx convert.ts article.md --platform xhs --template minimal
`);
    process.exit(0);
  }

  const input = args[0];
  if (!fs.existsSync(input)) {
    console.error(`❌ 文件不存在: ${input}`);
    process.exit(1);
  }

  const templateIdx = args.indexOf('--template');
  const platformIdx = args.indexOf('--platform');
  const outputIdx = args.indexOf('--output');
  const titleIdx = args.indexOf('--title');

  const template = templateIdx >= 0 ? args[templateIdx + 1] as TemplateName : 'tech';
  const platform = platformIdx >= 0 ? args[platformIdx + 1] as PlatformName : undefined;
  const outputDir = outputIdx >= 0 ? args[outputIdx + 1] : path.join(__dirname, '..', 'output');
  const title = titleIdx >= 0 ? args[titleIdx + 1] : undefined;
  const all = args.includes('--all');

  console.log(`\n📝 转换: ${path.basename(input)}`);
  console.log(`🎨 模板: ${template}`);
  console.log(`🎯 平台: ${all ? '全部' : platform || '通用 HTML'}\n`);

  const results = convert({ input, template, platform, all, outputDir, title });
  writeResults(results, outputDir);

  console.log(`\n✅ 完成! 输出到 ${outputDir}\n`);
}

// Only run CLI when executed directly
const isMainModule = process.argv[1]?.endsWith('convert.ts') || process.argv[1]?.endsWith('convert.js');
if (isMainModule) {
  main();
}
