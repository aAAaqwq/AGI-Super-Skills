#!/usr/bin/env node

/**
 * wechat-publisher: 发布 Markdown 到微信公众号草稿箱
 *
 * 用法:
 *   node publish.js <markdown-file> [theme] [highlight]
 *
 * 跨平台支持: macOS / Linux / Windows
 */

const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ─── 默认配置 ─────────────────────────────────────────────────
const DEFAULT_THEME = 'lapis';
const DEFAULT_HIGHLIGHT = 'solarized-light';
const TOOLS_MD_PATHS = [
    path.join(os.homedir(), '.openclaw', 'workspace-xina-gongzhonghao', 'TOOLS.md'),
    path.join(os.homedir(), '.openclaw', 'workspace', 'TOOLS.md'),
];

// ─── 颜色输出（跨平台） ──────────────────────────────────────
const supportsColor = process.stdout.isTTY;
const color = {
    red:    (s) => supportsColor ? `\x1b[31m${s}\x1b[0m` : s,
    green:  (s) => supportsColor ? `\x1b[32m${s}\x1b[0m` : s,
    yellow: (s) => supportsColor ? `\x1b[33m${s}\x1b[0m` : s,
};

// ─── 检查 wenyan-cli ──────────────────────────────────────────
function checkWenyan() {
    try {
        execFileSync('wenyan', ['--version'], { stdio: 'pipe' });
    } catch {
        console.log(color.yellow('⚠️  wenyan-cli 未安装，正在安装...'));
        try {
            execFileSync('npm', ['install', '-g', '@wenyan-md/cli'], { stdio: 'inherit' });
            console.log(color.green('✅ wenyan-cli 安装成功！'));
        } catch (e) {
            console.error(color.red('❌ 安装失败！请手动运行: npm install -g @wenyan-md/cli'));
            process.exit(1);
        }
    }
}

// ─── 从 TOOLS.md 读取凭证 ────────────────────────────────────
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
            console.log(color.yellow(`📖 凭证从 ${toolsPath} 读取`));
            return { appId, secret };
        }
    }

    return { appId, secret };
}

// ─── 检查环境变量 ────────────────────────────────────────────
function checkEnv() {
    const { appId, secret } = loadCredentials();
    if (!appId || !secret) {
        console.error(color.red('❌ 环境变量未设置！'));
        console.log(color.yellow('请在 TOOLS.md 中添加微信公众号凭证：'));
        console.log('');
        console.log('  ## 🔐 WeChat Official Account (微信公众号)');
        console.log('  ');
        console.log('  export WECHAT_APP_ID=your_app_id');
        console.log('  export WECHAT_APP_SECRET=your_app_secret');
        console.log('');
        console.log(color.yellow('或者手动设置环境变量：'));
        console.log('  export WECHAT_APP_ID=your_app_id');
        console.log('  export WECHAT_APP_SECRET=your_app_secret');
        process.exit(1);
    }
    return { appId, secret };
}

// ─── 发布函数 ────────────────────────────────────────────────
function publish(file, theme, highlight, appId, secret) {
    console.log(color.green('📝 准备发布文章...'));
    console.log(`  文件: ${file}`);
    console.log(`  主题: ${theme}`);
    console.log(`  代码高亮: ${highlight}`);
    console.log('');

    const env = { ...process.env, WECHAT_APP_ID: appId, WECHAT_APP_SECRET: secret };

    try {
        execFileSync('wenyan', ['publish', '-f', file, '-t', theme, '-h', highlight], {
            env,
            stdio: 'inherit',
        });
        console.log('');
        console.log(color.green('✅ 发布成功！'));
        console.log(color.yellow('📱 请前往微信公众号后台草稿箱查看：'));
        console.log('  https://mp.weixin.qq.com/');
    } catch {
        console.log('');
        console.error(color.red('❌ 发布失败！'));
        console.log(color.yellow('💡 常见问题：'));
        console.log('  1. IP 未在白名单 → 添加到公众号后台');
        console.log('  2. Frontmatter 缺失 → 文件顶部添加 title + cover');
        console.log('  3. API 凭证错误 → 检查 TOOLS.md 中的凭证');
        console.log('  4. 封面尺寸错误 → 需要 1080×864 像素');
        process.exit(1);
    }
}

// ─── 帮助 ────────────────────────────────────────────────────
function showHelp() {
    console.log(`Usage: node publish.js <markdown-file> [theme] [highlight]

Examples:
  node publish.js article.md
  node publish.js article.md lapis
  node publish.js article.md lapis solarized-light

Available themes:
  default, lapis, phycat, ...
  Run 'wenyan theme -l' to see all themes

Available highlights:
  atom-one-dark, atom-one-light, dracula, github-dark, github,
  monokai, solarized-dark, solarized-light, xcode`);
}

// ─── 主函数 ──────────────────────────────────────────────────
function main() {
    const args = process.argv.slice(2);

    if (args.length === 0 || args[0] === '-h' || args[0] === '--help') {
        showHelp();
        process.exit(0);
    }

    const file = args[0];
    const theme = args[1] || DEFAULT_THEME;
    const highlight = args[2] || DEFAULT_HIGHLIGHT;

    // 检查文件
    if (!fs.existsSync(file)) {
        console.error(color.red(`❌ 文件不存在: ${file}`));
        process.exit(1);
    }

    checkWenyan();
    const { appId, secret } = checkEnv();
    publish(file, theme, highlight, appId, secret);
}

main();
