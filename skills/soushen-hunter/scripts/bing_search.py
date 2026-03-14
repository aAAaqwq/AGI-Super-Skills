#!/usr/bin/env python3
"""
搜神猎手 (SouShen Hunter) - 高性能 Bing 搜索引擎
使用 Playwright 底层 API，最大化过滤有效信息
输出格式：JSON（便于 LLM 处理）
"""

import asyncio
import json
import sys
import os
import shutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print(json.dumps({"error": "playwright not installed. Run: pip install playwright"}, ensure_ascii=False))
    sys.exit(1)


def find_chrome_executable() -> Optional[str]:
    """自动查找 Chrome 可执行文件路径"""
    possible_paths = [
        os.environ.get('CHROME_PATH'),
        os.environ.get('CHROME_BIN'),
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expanduser('~/.local/bin/chrome-for-testing-dir/chrome'),
        os.path.expanduser('~/.local/bin/chrome-for-testing/chrome'),
        os.path.expanduser('~/chrome-linux64/chrome'),
    ]
    
    for path in possible_paths:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    chrome_names = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']
    for name in chrome_names:
        path = shutil.which(name)
        if path:
            return path
    
    return None


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    snippet: str
    source: str
    result_type: str = "organic"


@dataclass
class PageElements:
    """页面元素提取结果"""
    title: str
    url: str
    text_content: str
    headings: List[Dict]
    paragraphs: List[str]
    lists: List[Dict]
    tables: List[Dict]
    code_blocks: List[str]
    links: List[Dict[str, str]]
    forms: List[Dict[str, Any]]
    buttons: List[Dict[str, str]]
    scripts: List[str]
    meta: Dict[str, str]
    cookies: List[Dict]


class BingSearchAgent:
    """Bing 搜索代理 - 高性能版本"""
    
    def __init__(self, headless: bool = True, chrome_path: Optional[str] = None):
        self.headless = headless
        self.chrome_path = chrome_path or find_chrome_executable()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        
        launch_options = {
            'headless': self.headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-extensions',
                '--disable-logging',
                '--log-level=3',
                '--remote-debugging-port=0',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-first-run',
                '--safebrowsing-disable-auto-update',
            ]
        }
        
        if self.chrome_path:
            launch_options['executable_path'] = self.chrome_path
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )
        self.page = await context.new_page()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """执行 Bing 搜索并返回结构化结果"""
        results = []
        
        try:
            await self.page.goto('https://www.bing.com', wait_until='domcontentloaded')
            search_box = await self.page.wait_for_selector('[name="q"]')
            await search_box.fill(query)
            await search_box.press('Enter')
            await self.page.wait_for_load_state('networkidle')
            
            result_selectors = ['li.b_algo', '.b_ad li', '.news-card']
            
            for selector in result_selectors:
                elements = await self.page.query_selector_all(selector)
                for elem in elements[:num_results]:
                    try:
                        result = await self._extract_result(elem)
                        if result and result.url:
                            results.append(result)
                    except Exception:
                        continue
                        
        except Exception as e:
            pass
            
        return results[:num_results]
    
    async def _extract_result(self, element) -> Optional[SearchResult]:
        """从单个元素提取搜索结果 - 修复版（过滤图片/视频结果）"""
        try:
            # 优先找 h2 a 或 .b_title a（文字结果），避免匹配到图片的 <a>
            title_elem = await element.query_selector('h2 a, .b_title a')
            
            # 如果没找到，再尝试找第一个有文字的 <a>
            if not title_elem:
                all_links = await element.query_selector_all('a[href]')
                for link in all_links:
                    text = await link.inner_text()
                    href = await link.get_attribute('href')
                    # 过滤图片链接和空标题
                    if text and text.strip() and href and not href.startswith('/images/'):
                        title_elem = link
                        break
            
            if not title_elem:
                return None
                
            title = await title_elem.inner_text()
            url = await title_elem.get_attribute('href')
            
            # 过滤掉 Bing 内部图片/视频链接
            if not url or url.startswith('/images/') or url.startswith('/videos/'):
                return None
                
            # 过滤空标题
            if not title or not title.strip():
                return None
            
            snippet_elem = await element.query_selector('.b_caption p, .b_snippet, p')
            snippet = await snippet_elem.inner_text() if snippet_elem else ''
            
            source_elem = await element.query_selector('.b_attribution cite, cite')
            source = await source_elem.inner_text() if source_elem else urlparse(url).netloc
            
            return SearchResult(
                title=title.strip(),
                url=url,
                snippet=snippet.strip(),
                source=source.strip(),
                result_type='organic'
            )
        except:
            return None
    
    async def extract_page_elements(self, url: str) -> Optional[PageElements]:
        """深度提取页面所有关键元素"""
        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(1)
            
            title = await self.page.title()
            current_url = self.page.url
            cookies = await self.page.context.cookies()
            
            page_data = await self.page.evaluate('''() => {
                const cleanText = (el) => {
                    const clone = el.cloneNode(true);
                    clone.querySelectorAll('script, style, nav, header, footer, aside, .advertisement, .ads, [class*="ad-"], [class*="banner"]').forEach(e => e.remove());
                    return clone.innerText || '';
                };
                
                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
                    level: parseInt(h.tagName[1]),
                    text: h.innerText.trim()
                })).filter(h => h.text.length > 0);
                
                const paragraphs = Array.from(document.querySelectorAll('p, article p, .content p, main p'))
                    .map(p => p.innerText.trim())
                    .filter(t => t.length > 20);
                
                const lists = Array.from(document.querySelectorAll('ul, ol')).map(list => ({
                    type: list.tagName.toLowerCase(),
                    items: Array.from(list.querySelectorAll('li')).map(li => li.innerText.trim()).filter(t => t.length > 0)
                })).filter(l => l.items.length > 0);
                
                const tables = Array.from(document.querySelectorAll('table')).map(table => {
                    const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
                    const rows = Array.from(table.querySelectorAll('tr')).slice(1).map(tr => 
                        Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
                    ).filter(row => row.length > 0);
                    return { headers, rows };
                }).filter(t => t.rows.length > 0);
                
                const codeBlocks = Array.from(document.querySelectorAll('pre, code, .code, .highlight'))
                    .map(c => c.innerText.trim())
                    .filter(t => t.length > 10);
                
                const mainContent = document.querySelector('main, article, .content, .post, #content, [role="main"]');
                const bodyText = mainContent ? cleanText(mainContent) : cleanText(document.body);
                
                const links = Array.from(document.querySelectorAll('a[href]')).map(a => ({
                    text: a.textContent.trim(),
                    href: a.href,
                    type: a.getAttribute('data-type') || 'link'
                })).filter(l => l.href && !l.href.startsWith('javascript:') && l.text.length > 0);
                
                const forms = Array.from(document.querySelectorAll('form')).map(form => {
                    const inputs = Array.from(form.querySelectorAll('input, select, textarea')).map(i => ({
                        name: i.name,
                        type: i.type || i.tagName.toLowerCase(),
                        placeholder: i.placeholder || '',
                        required: i.required,
                        value: i.value || ''
                    }));
                    return {
                        action: form.action,
                        method: form.method || 'GET',
                        name: form.name || form.id || '',
                        inputs: inputs
                    };
                });
                
                const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], .btn, [role="button"]')).map(b => ({
                    text: (b.textContent || b.value || '').trim(),
                    type: b.type || 'button',
                    id: b.id || '',
                    action: b.getAttribute('onclick') || b.getAttribute('data-action') || ''
                })).filter(b => b.text.length > 0);
                
                const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
                
                const meta = {};
                document.querySelectorAll('meta[name], meta[property]').forEach(m => {
                    const key = m.getAttribute('name') || m.getAttribute('property');
                    if (key) meta[key] = m.content;
                });
                
                return {
                    text_content: bodyText,
                    headings: headings,
                    paragraphs: paragraphs,
                    lists: lists,
                    tables: tables,
                    code_blocks: codeBlocks,
                    links: links,
                    forms: forms,
                    buttons: buttons,
                    scripts: scripts,
                    meta: meta
                };
            }''')
            
            return PageElements(
                title=title,
                url=current_url,
                text_content=page_data.get('text_content', ''),
                headings=page_data.get('headings', []),
                paragraphs=page_data.get('paragraphs', []),
                lists=page_data.get('lists', []),
                tables=page_data.get('tables', []),
                code_blocks=page_data.get('code_blocks', []),
                links=page_data.get('links', []),
                forms=page_data.get('forms', []),
                buttons=page_data.get('buttons', []),
                scripts=page_data.get('scripts', []),
                meta=page_data.get('meta', {}),
                cookies=cookies
            )
            
        except Exception as e:
            return None


def format_output(results: List[SearchResult]) -> str:
    """格式化输出为JSON"""
    return json.dumps({
        "tool": "soushen-hunter",
        "mode": "search",
        "total": len(results),
        "results": [asdict(r) for r in results]
    }, ensure_ascii=False, indent=2)


def format_page_elements(elements: PageElements, text_offset: int = 0, text_limit: int = 10000) -> str:
    """格式化页面元素输出为JSON"""
    full_text = elements.text_content or ""
    text_total = len(full_text)
    text_slice = full_text[text_offset:text_offset + text_limit]
    has_more_text = (text_offset + text_limit) < text_total
    
    result = {
        "tool": "soushen-hunter",
        "mode": "deep",
        "page": {
            "title": elements.title,
            "url": elements.url
        },
        "text_content": {
            "content": text_slice,
            "offset": text_offset,
            "length": len(text_slice),
            "total_length": text_total,
            "has_more": has_more_text,
            "next_offset": text_offset + text_limit if has_more_text else None
        },
        "cookies": elements.cookies,
        "headings": elements.headings,
        "paragraphs": elements.paragraphs,
        "lists": elements.lists,
        "tables": elements.tables,
        "code_blocks": elements.code_blocks,
        "forms": elements.forms,
        "links": {
            "total": len(elements.links),
            "items": elements.links
        },
        "buttons": {
            "total": len(elements.buttons),
            "items": elements.buttons
        },
        "scripts": elements.scripts,
        "meta": elements.meta
    }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


def parse_args():
    """解析命令行参数"""
    args = sys.argv[1:]
    result = {
        'mode': None,
        'query': None,
        'url': None,
        'text_offset': 0,
        'text_limit': 10000
    }
    
    if '--text-offset' in args:
        idx = args.index('--text-offset')
        if idx + 1 < len(args):
            try:
                result['text_offset'] = int(args[idx + 1])
                args.pop(idx + 1)
                args.pop(idx)
            except ValueError:
                pass
    
    if '--text-limit' in args:
        idx = args.index('--text-limit')
        if idx + 1 < len(args):
            try:
                result['text_limit'] = int(args[idx + 1])
                args.pop(idx + 1)
                args.pop(idx)
            except ValueError:
                pass
    
    if '--deep' in args:
        deep_idx = args.index('--deep')
        if deep_idx + 1 >= len(args):
            print(json.dumps({"error": "--deep requires a URL argument"}, ensure_ascii=False))
            sys.exit(1)
        result['mode'] = 'deep'
        result['url'] = args[deep_idx + 1]
        return result
    
    if len(args) < 1:
        return None
    
    result['mode'] = 'search'
    result['query'] = args[0]
    return result


async def main():
    """主函数 - CLI 入口"""
    parsed = parse_args()
    
    if parsed is None:
        help_text = {
            "tool": "soushen-hunter",
            "usage": {
                "search": "python bing_search.py <query>",
                "deep": "python bing_search.py --deep <url> [--text-offset N] [--text-limit N]"
            },
            "options": {
                "--text-offset": "文本起始位置 (默认0)",
                "--text-limit": "文本长度限制 (默认10000)"
            },
            "examples": [
                "python bing_search.py 'OpenClaw AI'",
                "python bing_search.py --deep https://example.com",
                "python bing_search.py --deep https://example.com --text-limit 50000",
                "python bing_search.py --deep https://example.com --text-offset 10000 --text-limit 10000"
            ],
            "env": {
                "CHROME_PATH": "Chrome可执行文件路径 (可选)"
            }
        }
        print(json.dumps(help_text, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    chrome_path = os.environ.get('CHROME_PATH') or os.environ.get('CHROME_BIN')
    
    async with BingSearchAgent(headless=True, chrome_path=chrome_path) as agent:
        if parsed['mode'] == 'deep':
            url = parsed['url']
            text_offset = parsed.get('text_offset', 0)
            text_limit = parsed.get('text_limit', 10000)
            elements = await agent.extract_page_elements(url)
            if elements:
                print(format_page_elements(elements, text_offset=text_offset, text_limit=text_limit))
            else:
                print(json.dumps({"error": "页面分析失败"}, ensure_ascii=False))
        else:
            results = await agent.search(parsed['query'], num_results=10)
            print(format_output(results))


if __name__ == '__main__':
    asyncio.run(main())
