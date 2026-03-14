#!/usr/bin/env node
/**
 * 微博热搜榜抓取脚本
 * 数据来源：微博热搜公开接口
 */

const https = require('https');

const limit = parseInt(process.argv[2]) || 50;

const options = {
  hostname: 'weibo.com',
  path: '/ajax/side/hotSearch',
  method: 'GET',
  headers: {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://weibo.com/hot/search',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
  }
};

function fetchHotSearch() {
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json);
        } catch (e) {
          reject(new Error('解析响应失败: ' + e.message));
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error('请求超时'));
    });
    req.end();
  });
}

async function main() {
  console.log('正在获取微博热搜榜...\n');

  const data = await fetchHotSearch();

  if (!data || !data.data || !data.data.realtime) {
    throw new Error('接口返回数据异常: ' + JSON.stringify(data).slice(0, 200));
  }

  const items = data.data.realtime.slice(0, limit);

  const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  console.log(`🔥 微博热搜 TOP ${items.length}`);
  console.log('='.repeat(70));
  console.log(`📅 更新时间: ${now}\n`);

  items.forEach((item, i) => {
    const rank = String(i + 1).padStart(2, ' ');
    const title = item.word || item.note || '未知';
    const hot = item.num ? `${Math.round(item.num / 10000)}万` : (item.raw_hot || '');
    const label = item.label_name ? ` [${item.label_name}]` : '';
    const url = `https://s.weibo.com/weibo?q=%23${encodeURIComponent(title)}%23`;

    console.log(`${rank}. ${title}${label}`);
    if (hot) console.log(`    🔥 热度: ${hot}`);
    console.log(`    🔗 ${url}`);
    console.log();
  });
}

main().catch(err => {
  console.error('❌ 获取失败:', err.message);
  process.exit(1);
});
