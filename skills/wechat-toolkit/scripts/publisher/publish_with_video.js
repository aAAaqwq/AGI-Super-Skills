#!/usr/bin/env node

/**
 * publish_with_video.js - 发布含视频的 Markdown 文章到微信公众号草稿箱
 *
 * 流程：
 * 1. 扫描 Markdown 中的 mp4 引用
 * 2. 上传每个 mp4 到微信永久素材库，获取 media_id
 * 3. 把 mp4 引用替换为 VIDEO_PLACEHOLDER_<n> 占位符
 * 4. 用 wenyan 发布（获取草稿 media_id）
 * 5. 用微信 API 拉取草稿内容
 * 6. 将占位符替换为 <mp-video> 标签
 * 7. 更新草稿
 *
 * 用法：
 *   node publish_with_video.js <markdown-file> [theme] [highlight]
 *
 * 跨平台支持: macOS / Linux / Windows
 *
 * 环境变量（或从 TOOLS.md 自动读取）：
 *   WECHAT_APP_ID
 *   WECHAT_APP_SECRET
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const https = require('https');
const http = require('http');
const { execFileSync } = require('child_process');

// ─── 配置 ─────────────────────────────────────────────────────
const TOOLS_MD_PATHS = [
    path.join(os.homedir(), '.openclaw', 'workspace-xina-gongzhonghao', 'TOOLS.md'),
    path.join(os.homedir(), '.openclaw', 'workspace', 'TOOLS.md'),
];
const WENYAN_TOKEN_CACHE = path.join(os.homedir(), '.config', 'wenyan-md', 'token.json');
const DEFAULT_THEME = 'lapis';
const DEFAULT_HIGHLIGHT = 'solarized-light';

// ─── 工具函数 ─────────────────────────────────────────────────

function loadCredentials() {
    let appId = process.env.WECHAT_APP_ID || '';
    let secret = process.env.WECHAT_APP_SECRET || '';
    if (appId && secret) return { appId, secret };

    for (const toolsPath of TOOLS_MD_PATHS) {
        if (!fs.existsSync(toolsPath)) continue;
        const content = fs.readFileSync(toolsPath, 'utf-8');
        for (const line of content.split('\n')) {
            const idMatch = line.match(/export\s+WECHAT_APP_ID=(\S+)/);
            if (idMatch) appId = idMatch[1];
            const secretMatch = line.match(/export\s+WECHAT_APP_SECRET=(\S+)/);
            if (secretMatch) secret = secretMatch[1];
        }
        if (appId && secret) {
            console.log(`📖 凭证从 ${toolsPath} 读取`);
            return { appId, secret };
        }
    }

    throw new Error('❌ 未找到 WECHAT_APP_ID / WECHAT_APP_SECRET，请设置环境变量或在 TOOLS.md 中配置');
}

/**
 * 发起 HTTPS JSON 请求
 */
function httpsRequest(url, options = {}) {
    return new Promise((resolve, reject) => {
        const parsedUrl = new URL(url);
        const reqModule = parsedUrl.protocol === 'https:' ? https : http;
        const reqOptions = {
            hostname: parsedUrl.hostname,
            port: parsedUrl.port,
            path: parsedUrl.pathname + parsedUrl.search,
            method: options.method || 'GET',
            headers: options.headers || {},
            timeout: options.timeout || 15000,
        };

        const req = reqModule.request(reqOptions, (res) => {
            const chunks = [];
            res.on('data', (chunk) => chunks.push(chunk));
            res.on('end', () => {
                const body = Buffer.concat(chunks).toString('utf-8');
                try {
                    resolve(JSON.parse(body));
                } catch {
                    resolve(body);
                }
            });
        });

        req.on('error', reject);
        req.on('timeout', () => { req.destroy(); reject(new Error('Request timeout')); });

        if (options.body) {
            req.write(typeof options.body === 'string' ? options.body : JSON.stringify(options.body));
        }
        req.end();
    });
}

/**
 * Multipart 上传文件（替代 curl）
 */
function uploadMultipart(url, fields) {
    return new Promise((resolve, reject) => {
        const boundary = '----FormBoundary' + Math.random().toString(36).slice(2);
        const parts = [];

        for (const { name, value, filename, contentType } of fields) {
            if (filename) {
                // 文件字段
                parts.push(Buffer.from(
                    `--${boundary}\r\n` +
                    `Content-Disposition: form-data; name="${name}"; filename="${filename}"\r\n` +
                    `Content-Type: ${contentType || 'application/octet-stream'}\r\n\r\n`
                ));
                parts.push(fs.readFileSync(value)); // value = file path
                parts.push(Buffer.from('\r\n'));
            } else {
                // 普通字段
                parts.push(Buffer.from(
                    `--${boundary}\r\n` +
                    `Content-Disposition: form-data; name="${name}"\r\n\r\n` +
                    `${value}\r\n`
                ));
            }
        }
        parts.push(Buffer.from(`--${boundary}--\r\n`));

        const body = Buffer.concat(parts);
        const parsedUrl = new URL(url);
        const reqModule = parsedUrl.protocol === 'https:' ? https : http;
        const reqOptions = {
            hostname: parsedUrl.hostname,
            port: parsedUrl.port,
            path: parsedUrl.pathname + parsedUrl.search,
            method: 'POST',
            headers: {
                'Content-Type': `multipart/form-data; boundary=${boundary}`,
                'Content-Length': body.length,
            },
            timeout: 200000,
        };

        const req = reqModule.request(reqOptions, (res) => {
            const chunks = [];
            res.on('data', (chunk) => chunks.push(chunk));
            res.on('end', () => {
                const respBody = Buffer.concat(chunks).toString('utf-8');
                try { resolve(JSON.parse(respBody)); }
                catch { resolve(respBody); }
            });
        });

        req.on('error', reject);
        req.on('timeout', () => { req.destroy(); reject(new Error('Upload timeout')); });
        req.write(body);
        req.end();
    });
}

// ─── 微信 API ─────────────────────────────────────────────────

async function getFreshToken(appId, secret) {
    const url = `https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=${appId}&secret=${secret}`;
    const data = await httpsRequest(url);
    if (!data.access_token) {
        throw new Error(`获取 token 失败: ${JSON.stringify(data)}`);
    }
    const token = data.access_token;
    const expireAt = Math.floor(Date.now() / 1000) + (data.expires_in || 7200);

    // 写入 wenyan 缓存，保持同步
    const cacheDir = path.dirname(WENYAN_TOKEN_CACHE);
    if (!fs.existsSync(cacheDir)) fs.mkdirSync(cacheDir, { recursive: true });
    fs.writeFileSync(WENYAN_TOKEN_CACHE, JSON.stringify({
        appid: appId,
        accessToken: token,
        expireAt,
    }));
    return token;
}

async function uploadVideo(token, videoPath, title = '视频') {
    const url = `https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=${token}&type=video`;
    const description = JSON.stringify({ title, introduction: title });

    const data = await uploadMultipart(url, [
        { name: 'media', value: videoPath, filename: path.basename(videoPath), contentType: 'video/mp4' },
        { name: 'description', value: description },
    ]);

    if (!data.media_id) {
        throw new Error(`视频上传失败 (${videoPath}): ${JSON.stringify(data)}`);
    }
    const mediaId = data.media_id;

    // 获取 vid
    const listUrl = `https://api.weixin.qq.com/cgi-bin/material/batchget_material?access_token=${token}`;
    const listData = await httpsRequest(listUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: { type: 'video', offset: 0, count: 5 },
    });

    let vid = '';
    let coverUrl = '';
    for (const item of (listData.item || [])) {
        if (item.media_id === mediaId) {
            vid = item.vid || '';
            coverUrl = item.cover_url || '';
            break;
        }
    }

    return { mediaId, vid, coverUrl };
}

// ─── 视频处理 ─────────────────────────────────────────────────

function findMp4Refs(content, articleDir) {
    const pattern = /!?\[([^\]]*)\]\(([^)]+\.mp4)\)/gi;
    const refs = [];
    let m;
    while ((m = pattern.exec(content)) !== null) {
        const alt = m[1];
        const rel = m[2];
        const absPath = path.resolve(articleDir, rel);
        refs.push({ alt, rel, absPath });
    }
    return refs;
}

/**
 * 检查文件是否为真实视频（纯 Node.js，不依赖 file 命令）
 * 通过读取文件头部 magic bytes 判断
 */
function isRealVideo(filePath) {
    try {
        const fd = fs.openSync(filePath, 'r');
        const buf = Buffer.alloc(12);
        fs.readSync(fd, buf, 0, 12, 0);
        fs.closeSync(fd);

        // MP4: ftyp signature at offset 4
        if (buf.toString('ascii', 4, 8) === 'ftyp') return true;
        // AVI: RIFF....AVI
        if (buf.toString('ascii', 0, 4) === 'RIFF' && buf.toString('ascii', 8, 11) === 'AVI') return true;
        // WebM/MKV: 0x1A45DFA3
        if (buf[0] === 0x1A && buf[1] === 0x45 && buf[2] === 0xDF && buf[3] === 0xA3) return true;
        // FLV: FLV
        if (buf.toString('ascii', 0, 3) === 'FLV') return true;

        // 检查是否为文本/HTML（非视频）
        const sample = fs.readFileSync(filePath, { encoding: 'utf-8', flag: 'r' }).slice(0, 200);
        if (sample.includes('<html') || sample.includes('<!DOCTYPE') || sample.includes('<HTML')) {
            return false;
        }

        return true; // 给不认识的格式默认通过
    } catch {
        return false;
    }
}

async function processVideos(content, articleDir, token) {
    const refs = findMp4Refs(content, articleDir);
    if (refs.length === 0) {
        console.log('✅ 文章中没有视频引用');
        return { content, placeholderMap: {} };
    }

    const placeholderMap = {};

    for (const { alt, rel, absPath } of refs) {
        if (!fs.existsSync(absPath)) {
            console.log(`⚠️  视频文件不存在: ${absPath}，跳过`);
            content = content.replace(`![${alt}](${rel})`, `[视频: ${alt}（文件不存在）]`);
            content = content.replace(`[${alt}](${rel})`, `[视频: ${alt}（文件不存在）]`);
            continue;
        }

        if (!isRealVideo(absPath)) {
            console.log(`⚠️  ${rel} 不是真实视频文件（可能是 HTML 预览页），替换为文字`);
            content = content.replace(`![${alt}](${rel})`, `[视频预览: ${alt}]`);
            content = content.replace(`[${alt}](${rel})`, `[视频预览: ${alt}]`);
            continue;
        }

        const fileSizeMB = (fs.statSync(absPath).size / 1024 / 1024).toFixed(1);
        console.log(`🎬 上传视频: ${rel} (${fileSizeMB} MB)...`);

        try {
            const { mediaId, vid, coverUrl } = await uploadVideo(token, absPath, alt || path.basename(absPath, '.mp4'));
            const placeholder = `VIDEO_PLACEHOLDER_${mediaId}`;
            placeholderMap[placeholder] = { mediaId, vid, coverUrl };
            content = content.replace(`![${alt}](${rel})`, placeholder);
            content = content.replace(`[${alt}](${rel})`, placeholder);
            console.log(`   ✅ 上传成功: media_id=${mediaId.substring(0, 30)}... vid=${vid}`);
        } catch (e) {
            console.log(`   ❌ 上传失败: ${e.message}，替换为截图名称`);
            const pngRef = rel.replace('.mp4', '.png');
            content = content.replace(`![${alt}](${rel})`, `![${alt}](${pngRef})`);
            content = content.replace(`[${alt}](${rel})`, `[${alt}](${pngRef})`);
        }
    }

    return { content, placeholderMap };
}

// ─── Wenyan 发布 ──────────────────────────────────────────────

function publishWithWenyan(mdPath, theme, highlight, appId, secret) {
    const env = { ...process.env, WECHAT_APP_ID: appId, WECHAT_APP_SECRET: secret };

    let stdout;
    try {
        stdout = execFileSync('wenyan', ['publish', '-f', mdPath, '-t', theme, '-h', highlight], {
            env,
            encoding: 'utf-8',
            timeout: 120000,
        });
    } catch (e) {
        throw new Error(`wenyan 发布失败: ${e.stderr || e.stdout || e.message}`);
    }

    console.log('wenyan stdout:', stdout);

    const m = stdout.match(/Media ID[:\s]+(\S+)/);
    return m ? m[1] : null;
}

// ─── 视频 iframe 构建 ────────────────────────────────────────
function buildVideoIframe(vid, coverUrl = '') {
    const src = `https://mp.weixin.qq.com/mp/readtemplate?t=pages/video_player_tmpl&action=mpvideo&scene=0&vid=${vid}`;
    const coverAttr = coverUrl ? ` data-cover="${coverUrl}"` : '';
    return (
        `<iframe class="video_iframe rich_pages wxw-img" ` +
        `data-src="${src}" ` +
        `data-vidtype="2" ` +
        `data-mpvid="${vid}"${coverAttr} ` +
        `allowfullscreen="" frameborder="0" scrolling="no" ` +
        `style="width: 677px; height: 508px;" ` +
        `src="${src}"></iframe>`
    );
}

// ─── 草稿视频修补 ────────────────────────────────────────────
async function patchDraftWithVideos(token, draftMediaId, placeholderMap) {
    if (Object.keys(placeholderMap).length === 0) return;

    console.log('\n🎬 开始修复草稿中的视频占位符...');

    // 拉取草稿
    const url = `https://api.weixin.qq.com/cgi-bin/draft/get?access_token=${token}`;
    const draftData = await httpsRequest(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: { media_id: draftMediaId },
    });

    if (!draftData.news_item) {
        console.log(`⚠️  拉取草稿失败: ${JSON.stringify(draftData)}`);
        return;
    }

    const articles = draftData.news_item;
    for (const article of articles) {
        let contentHtml = article.content || '';
        for (const [placeholder, { mediaId, vid, coverUrl }] of Object.entries(placeholderMap)) {
            if (contentHtml.includes(placeholder)) {
                let videoTag;
                if (vid) {
                    const iframe = buildVideoIframe(vid, coverUrl);
                    videoTag = `<p>${iframe}</p>`;
                    console.log(`   ✅ ${placeholder.substring(0, 35)}... → iframe(vid=${vid.substring(0, 30)}...)`);
                } else {
                    videoTag = `<mp-video data-pluginname="mpvideo" data-url="${mediaId}"></mp-video>`;
                    console.log(`   ⚠️  vid not found, fallback → mp-video(media_id)`);
                }
                contentHtml = contentHtml.replace(placeholder, videoTag);
            }
        }
        article.content = contentHtml;
    }

    // 更新草稿
    const updateUrl = `https://api.weixin.qq.com/cgi-bin/draft/update?access_token=${token}`;
    const result = await httpsRequest(updateUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: { media_id: draftMediaId, index: 0, articles: articles[0] },
    });

    if (result.errcode === 0 || result.errcode === undefined) {
        console.log('✅ 草稿视频更新成功！');
    } else {
        console.log(`⚠️  草稿更新失败: ${JSON.stringify(result)}`);
    }
}

// ─── 主流程 ──────────────────────────────────────────────────
async function main() {
    const args = process.argv.slice(2);

    if (args.length < 1 || args[0] === '-h' || args[0] === '--help') {
        console.log(`
publish_with_video.js - 发布含视频的 Markdown 文章到微信公众号草稿箱

用法:
    node publish_with_video.js <markdown-file> [theme] [highlight]

环境变量（或从 TOOLS.md 自动读取）:
    WECHAT_APP_ID
    WECHAT_APP_SECRET`);
        process.exit(0);
    }

    const articlePath = path.resolve(args[0]);
    const theme = args[1] || DEFAULT_THEME;
    const highlight = args[2] || DEFAULT_HIGHLIGHT;

    if (!fs.existsSync(articlePath)) {
        console.error(`❌ 文件不存在: ${articlePath}`);
        process.exit(1);
    }

    const articleDir = path.dirname(articlePath);
    console.log(`📄 文章: ${articlePath}`);
    console.log(`🎨 主题: ${theme} / ${highlight}\n`);

    // 1. 读取凭证
    const { appId, secret } = loadCredentials();

    // 2. 获取 token
    console.log('🔑 获取 access_token...');
    let token = await getFreshToken(appId, secret);
    console.log(`   Token: ${token.substring(0, 20)}...\n`);

    // 3. 处理视频
    const originalContent = fs.readFileSync(articlePath, 'utf-8');
    const { content: patchedContent, placeholderMap } = await processVideos(originalContent, articleDir, token);

    // 4. 写入临时文件
    const tmpMd = path.join(articleDir, `_publish_tmp_${path.basename(articlePath, '.md')}.md`);
    fs.writeFileSync(tmpMd, patchedContent, 'utf-8');
    console.log(`\n📝 临时文件: ${tmpMd}`);

    try {
        // 5. 刷新 token
        token = await getFreshToken(appId, secret);

        // 6. wenyan 发布
        console.log('\n🚀 发布草稿中...');
        const draftMediaId = publishWithWenyan(tmpMd, theme, highlight, appId, secret);
        if (draftMediaId) {
            console.log(`✅ 草稿发布成功！Media ID: ${draftMediaId}`);
        } else {
            console.log('⚠️  发布成功但未解析到 Media ID，跳过视频注入');
        }

        // 7. patch 草稿
        if (Object.keys(placeholderMap).length > 0 && draftMediaId) {
            token = await getFreshToken(appId, secret);
            await patchDraftWithVideos(token, draftMediaId, placeholderMap);
        }
    } finally {
        // 清理临时文件
        if (fs.existsSync(tmpMd)) {
            fs.unlinkSync(tmpMd);
            console.log('\n🗑️  临时文件已清理');
        }
    }

    console.log('\n🎉 完成！请前往公众号后台草稿箱审核并发布：');
    console.log('   https://mp.weixin.qq.com/');
}

main().catch(e => {
    console.error(`❌ 错误: ${e.message}`);
    process.exit(1);
});
