// 从 SSR HTML 提取 window.__NUXT__ 对象（Nuxt 压缩 IIFE 形式），输出 JSON
// 用法: node extract_nuxt.js <input.html> <output.json>
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf-8');
const i = html.indexOf('window.__NUXT__=');
if (i < 0) { console.error('NO NUXT'); process.exit(1); }
let s = html.slice(i + 'window.__NUXT__='.length);
const end = s.indexOf('</script>');
if (end < 0) { console.error('NO END SCRIPT'); process.exit(1); }
s = s.slice(0, end).trim();
try {
  const data = eval(s);
  fs.writeFileSync(process.argv[3], JSON.stringify(data));
  console.log('OK');
} catch (e) {
  console.error('EVAL FAIL:', e.message);
  process.exit(1);
}
