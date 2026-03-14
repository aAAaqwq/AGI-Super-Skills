#!/usr/bin/env node

/**
 * 微信公众号文章下载器 — OpenClaw Skill Script
 *
 * 用法:
 *   node download.js "<文章URL>" [--output <输出目录>] [--no-image] [--no-video]
 */

import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import { pipeline } from 'stream/promises';
import { Readable } from 'stream';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ─── CLI 参数解析 ─────────────────────────────────────────────
const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log(`
  微信公众号文章下载器 🐱

  用法:
    node download.js <文章URL> [选项]

  选项:
    --output, -o <目录>   输出目录（默认: ./output）
    --no-video            跳过视频下载
    --no-image            跳过图片下载
    --help                显示帮助
  `);
    process.exit(0);
}

const articleUrl = args.find(a => a.startsWith('http'));
if (!articleUrl) {
    console.error('❌ 请提供文章 URL（以 http 开头）');
    process.exit(1);
}

const outputIdx = args.findIndex(a => a === '--output' || a === '-o');
const outputBase = outputIdx !== -1 ? args[outputIdx + 1] : path.join(__dirname, 'output');
const skipVideo = args.includes('--no-video');
const skipImage = args.includes('--no-image');

// ─── 工具函数 ─────────────────────────────────────────────────

function sanitizeFileName(name) {
    return name.replace(/[\\/:*?"<>|]/g, '_').replace(/\s+/g, ' ').trim().substring(0, 100);
}

async function downloadFile(url, filePath, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const resp = await fetch(url, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Referer': 'https://mp.weixin.qq.com/',
                },
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const dir = path.dirname(filePath);
            if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
            const fileStream = fs.createWriteStream(filePath);
            await pipeline(Readable.fromWeb(resp.body), fileStream);
            return true;
        } catch (e) {
            if (i === retries - 1) {
                console.error(`  ⚠️  下载失败: ${url.substring(0, 80)} → ${e.message}`);
                return false;
            }
            await new Promise(r => setTimeout(r, 1000 * (i + 1)));
        }
    }
}

function getExtFromUrl(url) {
    try {
        const u = new URL(url);
        const wxFmt = u.searchParams.get('wx_fmt');
        if (wxFmt) return '.' + wxFmt;
        const ext = path.extname(u.pathname);
        if (ext && ext.length <= 5) return ext;
        return '.jpg';
    } catch {
        return '.jpg';
    }
}

function htmlToMarkdown(html) {
    let md = html;
    md = md.replace(/<script[\s\S]*?<\/script>/gi, '');
    md = md.replace(/<style[\s\S]*?<\/style>/gi, '');
    md = md.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, '# $1\n\n');
    md = md.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, '## $1\n\n');
    md = md.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, '### $1\n\n');
    md = md.replace(/<h4[^>]*>([\s\S]*?)<\/h4>/gi, '#### $1\n\n');
    md = md.replace(/<strong[^>]*>([\s\S]*?)<\/strong>/gi, '**$1**');
    md = md.replace(/<b[^>]*>([\s\S]*?)<\/b>/gi, '**$1**');
    md = md.replace(/<em[^>]*>([\s\S]*?)<\/em>/gi, '*$1*');
    md = md.replace(/<i[^>]*>([\s\S]*?)<\/i>/gi, '*$1*');
    md = md.replace(/<img[^>]*?(?:data-src|src)="([^"]*)"[^>]*>/gi, '\n![image]($1)\n');
    md = md.replace(/<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, '[$2]($1)');
    md = md.replace(/<br\s*\/?>/gi, '\n');
    md = md.replace(/<\/p>/gi, '\n\n');
    md = md.replace(/<p[^>]*>/gi, '');
    md = md.replace(/<\/div>/gi, '\n');
    md = md.replace(/<div[^>]*>/gi, '');
    md = md.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, '- $1\n');
    md = md.replace(/<\/?[uo]l[^>]*>/gi, '\n');
    md = md.replace(/<blockquote[^>]*>([\s\S]*?)<\/blockquote>/gi, (_, c) =>
        c.split('\n').map(l => '> ' + l).join('\n') + '\n\n');
    md = md.replace(/<code[^>]*>([\s\S]*?)<\/code>/gi, '`$1`');
    md = md.replace(/<pre[^>]*>([\s\S]*?)<\/pre>/gi, '```\n$1\n```\n\n');
    md = md.replace(/<hr[^>]*>/gi, '\n---\n\n');
    md = md.replace(/<[^>]+>/g, '');
    md = md.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
    md = md.replace(/\n{3,}/g, '\n\n');
    return md.trim();
}

async function autoScroll(page) {
    await page.evaluate(async () => {
        await new Promise(resolve => {
            let totalHeight = 0;
            const distance = 300;
            const timer = setInterval(() => {
                const scrollHeight = document.body.scrollHeight;
                window.scrollBy(0, distance);
                totalHeight += distance;
                if (totalHeight >= scrollHeight) {
                    clearInterval(timer);
                    window.scrollTo(0, 0);
                    resolve();
                }
            }, 100);
        });
    });
}

// ─── 主流程 ────────────────────────────────────────────────────

async function main() {
    console.log('🐱 微信公众号文章下载器');
    console.log(`📎 URL: ${articleUrl}\n`);

    // 找系统 Chrome（跨平台：macOS / Linux / Windows）
    const chromePathCandidates = [
        // macOS
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        // Linux
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium-browser',
        '/usr/bin/chromium',
        '/snap/bin/chromium',
        // Windows
        path.join(process.env.PROGRAMFILES || 'C:\\Program Files', 'Google', 'Chrome', 'Application', 'chrome.exe'),
        path.join(process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)', 'Google', 'Chrome', 'Application', 'chrome.exe'),
        path.join(process.env.LOCALAPPDATA || '', 'Google', 'Chrome', 'Application', 'chrome.exe'),
        path.join(process.env.PROGRAMFILES || 'C:\\Program Files', 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    ].filter(Boolean);
    const executablePath = chromePathCandidates.find(p => fs.existsSync(p));
    if (!executablePath) {
        console.error('❌ 未找到系统 Chrome，请先安装 Google Chrome');
        process.exit(1);
    }

    console.log('🚀 启动浏览器...');
    const browser = await puppeteer.launch({
        headless: true,
        executablePath,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ],
    });

    const page = await browser.newPage();
    await page.setUserAgent(
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    );
    await page.setViewport({ width: 1280, height: 900 });

    // 网络嗅探：捕获视频/音频 URL
    const capturedVideos = new Set();
    const capturedAudio = new Set();
    page.on('response', response => {
        const url = response.url();
        const ct = response.headers()['content-type'] || '';
        if (ct.includes('video/') || url.includes('.mp4') || url.includes('.m3u8') ||
            url.includes('.flv') || url.includes('mpvideo.qpic.cn')) {
            capturedVideos.add(url);
        }
        if (ct.includes('audio/') || url.includes('.mp3') || url.includes('.m4a')) {
            capturedAudio.add(url);
        }
    });

    console.log('📖 加载文章页面...');
    try {
        await page.goto(articleUrl, { waitUntil: 'networkidle2', timeout: 60000 });
    } catch (e) {
        console.error('❌ 页面加载失败:', e.message);
        await browser.close();
        process.exit(1);
    }

    // 检查是否被拦截
    const isBlocked = await page.evaluate(() =>
        document.body?.innerText?.includes('环境异常')
    );
    if (isBlocked) {
        console.error('❌ 微信检测到环境异常，请确保系统 Chrome 中已登录微信公众号，或稍后重试');
        await browser.close();
        process.exit(1);
    }

    console.log('⏳ 等待文章渲染...');
    try {
        await page.waitForSelector('#js_content', { timeout: 15000 });
    } catch {
        console.error('❌ 未找到文章内容（#js_content），文章可能已删除或需要登录');
        await browser.close();
        process.exit(1);
    }

    console.log('📜 滚动页面触发懒加载...');
    await autoScroll(page);
    await new Promise(r => setTimeout(r, 3000));

    console.log('📋 提取文章信息...');
    const metadata = await page.evaluate(() => ({
        title: document.querySelector('#activity-name')?.innerText?.trim() ||
            document.querySelector('.rich_media_title')?.innerText?.trim() ||
            document.title || '未命名文章',
        author: document.querySelector('#js_name')?.innerText?.trim() ||
            document.querySelector('.rich_media_meta_nickname')?.innerText?.trim() || '',
        publishTime: document.querySelector('#publish_time')?.innerText?.trim() ||
            document.querySelector('.rich_media_meta_date')?.innerText?.trim() || '',
        digest: document.querySelector('.rich_media_meta_text')?.innerText?.trim() || '',
    }));

    console.log(`  📰 标题: ${metadata.title}`);
    console.log(`  ✍️  作者: ${metadata.author}`);
    console.log(`  📅 时间: ${metadata.publishTime}`);

    // 创建输出目录
    const articleDir = path.join(outputBase, sanitizeFileName(metadata.title));
    const imagesDir = path.join(articleDir, 'images');
    const videosDir = path.join(articleDir, 'videos');
    fs.mkdirSync(imagesDir, { recursive: true });
    fs.mkdirSync(videosDir, { recursive: true });

    // ─── 下载图片 ───────────────────────────────────────────────
    if (!skipImage) {
        console.log('\n🖼️  下载配图...');
        const imageUrls = await page.evaluate(() => {
            const urls = [];
            document.querySelectorAll('#js_content img').forEach(img => {
                const src = img.getAttribute('data-src') || img.getAttribute('src') || '';
                if (src && !src.startsWith('data:') && !src.includes('icon') && !src.includes('loading')) {
                    urls.push(src);
                }
            });
            return urls;
        });

        console.log(`  发现 ${imageUrls.length} 张图片`);
        for (let i = 0; i < imageUrls.length; i++) {
            let url = imageUrls[i];
            if (url.startsWith('//')) url = 'https:' + url;
            const ext = getExtFromUrl(url);
            const fileName = `${i + 1}${ext}`;
            const filePath = path.join(imagesDir, fileName);
            process.stdout.write(`  ⬇️  [${i + 1}/${imageUrls.length}] ${fileName}...`);
            const ok = await downloadFile(url, filePath);
            console.log(ok ? ' ✅' : ' ❌');
            if (ok) console.log(`MEDIA:${filePath}`);
        }
    }

    // ─── 下载视频 ───────────────────────────────────────────────
    if (!skipVideo) {
        console.log('\n🎬 查找视频...');
        const domVideos = await page.evaluate(() => {
            const videos = [];
            document.querySelectorAll('video').forEach(v => {
                const src = v.src || v.querySelector('source')?.src || '';
                if (src) videos.push(src);
            });
            document.querySelectorAll(
                'iframe[data-src*="v.qq.com"], iframe[src*="v.qq.com"], iframe[data-src*="mpvideo"], iframe[src*="mpvideo"]'
            ).forEach(iframe => {
                const src = iframe.getAttribute('data-src') || iframe.getAttribute('src') || '';
                if (src) videos.push(src);
            });
            document.querySelectorAll('[data-mpvid], .js_tx_video_container').forEach(el => {
                const src = el.getAttribute('data-src') || el.getAttribute('data-url') || '';
                if (src) videos.push(src);
            });
            return videos;
        });

        const allVideoUrls = [...new Set([...domVideos, ...capturedVideos])]
            .filter(u => u && u.startsWith('http'));

        console.log(`  DOM 中发现: ${domVideos.length} 个视频引用`);
        console.log(`  网络嗅探到: ${capturedVideos.size} 个视频请求`);
        console.log(`  可下载: ${allVideoUrls.length} 个视频`);

        for (let i = 0; i < allVideoUrls.length; i++) {
            const url = allVideoUrls[i];
            const ext = url.includes('.m3u8') ? '.m3u8' : '.mp4';
            const fileName = `${i + 1}${ext}`;
            const filePath = path.join(videosDir, fileName);
            process.stdout.write(`  ⬇️  [${i + 1}/${allVideoUrls.length}] ${fileName}...`);
            const ok = await downloadFile(url, filePath);
            console.log(ok ? ' ✅' : ' ❌');
            if (ok) console.log(`MEDIA:${filePath}`);
        }

        // 音频
        const audioUrls = [...capturedAudio];
        for (let i = 0; i < audioUrls.length; i++) {
            const url = audioUrls[i];
            const ext = url.includes('.mp3') ? '.mp3' : '.m4a';
            const fileName = `audio_${i + 1}${ext}`;
            const filePath = path.join(videosDir, fileName);
            process.stdout.write(`  ⬇️  [audio ${i + 1}] ${fileName}...`);
            const ok = await downloadFile(url, filePath);
            console.log(ok ? ' ✅' : ' ❌');
            if (ok) console.log(`MEDIA:${filePath}`);
        }
    }

    // ─── 保存文章内容 ────────────────────────────────────────────
    console.log('\n📝 保存文章内容...');
    const contentHtml = await page.evaluate(() =>
        document.querySelector('#js_content')?.innerHTML || ''
    );

    // HTML
    const htmlPath = path.join(articleDir, 'article.html');
    fs.writeFileSync(htmlPath, `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>${metadata.title}</title>
<style>
  body { max-width: 800px; margin: 0 auto; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.8; color: #333; }
  img { max-width: 100%; height: auto; }
  .meta { color: #999; margin-bottom: 20px; font-size: 14px; }
</style>
</head>
<body>
<h1>${metadata.title}</h1>
<div class="meta">${metadata.author} · ${metadata.publishTime}</div>
${contentHtml}
</body>
</html>`, 'utf-8');

    // Markdown
    let markdown = `# ${metadata.title}\n\n`;
    markdown += `> **作者**: ${metadata.author}  \n`;
    markdown += `> **时间**: ${metadata.publishTime}  \n`;
    if (metadata.digest) markdown += `> **摘要**: ${metadata.digest}  \n`;
    markdown += `> **原文**: [链接](${articleUrl})\n\n---\n\n`;
    markdown += htmlToMarkdown(contentHtml);

    const mdPath = path.join(articleDir, 'article.md');
    fs.writeFileSync(mdPath, markdown, 'utf-8');

    // metadata.json
    const metaPath = path.join(articleDir, 'metadata.json');
    fs.writeFileSync(metaPath, JSON.stringify({
        ...metadata,
        url: articleUrl,
        downloadedAt: new Date().toISOString(),
        capturedVideos: [...capturedVideos],
        capturedAudio: [...capturedAudio],
    }, null, 2), 'utf-8');

    await browser.close();

    // ─── 结果汇报 ────────────────────────────────────────────────
    const imageFiles = fs.existsSync(imagesDir) ? fs.readdirSync(imagesDir) : [];
    const videoFiles = fs.existsSync(videosDir) ? fs.readdirSync(videosDir) : [];

    console.log('\n✅ 下载完成！');
    console.log(`📂 输出目录: ${articleDir}`);
    console.log(`  📄 article.md     (${Math.round(fs.statSync(mdPath).size / 1024)} KB)`);
    console.log(`  📄 article.html   (${Math.round(fs.statSync(htmlPath).size / 1024)} KB)`);
    console.log(`  🖼️  ${imageFiles.length} 张图片`);
    console.log(`  🎬 ${videoFiles.length} 个视频/音频`);

    // OpenClaw 自动附件
    console.log(`MEDIA:${mdPath}`);
    console.log(`MEDIA:${htmlPath}`);
}

main().catch(e => {
    console.error('❌ 发生错误:', e.message);
    process.exit(1);
});
