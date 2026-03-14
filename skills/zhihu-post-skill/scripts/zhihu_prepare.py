#!/usr/bin/env python3
"""
zhihu_prepare.py - 知乎发帖内容预处理

用法：
  python3 zhihu_prepare.py --title "标题" --content "正文内容（支持markdown）" [--type article|thought]

输出：JSON 格式，包含处理后的标题、HTML 正文、字数统计

支持简单 Markdown 转换为知乎友好 HTML
"""

import argparse
import json
import sys
import re


def markdown_to_html(text: str) -> str:
    """简单 Markdown → HTML 转换（仅处理常见格式）"""
    lines = text.split('\n')
    html_lines = []
    
    for line in lines:
        line = line.rstrip()
        
        # 标题
        if line.startswith('### '):
            html_lines.append(f'<h3>{line[4:]}</h3>')
        elif line.startswith('## '):
            html_lines.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('# '):
            html_lines.append(f'<h1>{line[2:]}</h1>')
        # 分隔线
        elif re.match(r'^---+$', line):
            html_lines.append('<hr/>')
        # 空行
        elif line == '':
            html_lines.append('')
        else:
            # 行内格式
            line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
            line = re.sub(r'\*(.+?)\*', r'<i>\1</i>', line)
            line = re.sub(r'`(.+?)`', r'<code>\1</code>', line)
            line = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', line)
            html_lines.append(f'<p>{line}</p>')
    
    # 合并连续空行
    result = '\n'.join(html_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def count_chars(text: str) -> int:
    """统计字符数（中文算1，英文算0.5，取整）"""
    zh = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    en = len(text) - zh
    return zh + (en // 2)


def main():
    parser = argparse.ArgumentParser(description='知乎发帖内容预处理')
    parser.add_argument('--title', required=True, help='文章标题')
    parser.add_argument('--content', required=True, help='正文内容（Markdown 格式）')
    parser.add_argument('--type', choices=['article', 'thought'], default='article',
                        help='内容类型：article=专栏文章，thought=想法')
    args = parser.parse_args()

    title = args.title.strip()
    content = args.content.strip()
    content_type = args.type

    # 验证
    errors = []
    if not title:
        errors.append('标题不能为空')
    if len(title) > 100:
        errors.append(f'标题过长（{len(title)}字），知乎限制100字以内')
    if not content:
        errors.append('正文不能为空')
    
    char_count = count_chars(content)
    if content_type == 'thought' and char_count > 1000:
        errors.append(f'想法内容过长（约{char_count}字），知乎想法限制1000字')

    if errors:
        print(json.dumps({'ok': False, 'errors': errors}, ensure_ascii=False, indent=2))
        sys.exit(1)

    # 转换
    html_content = markdown_to_html(content)

    result = {
        'ok': True,
        'type': content_type,
        'title': title,
        'html': html_content,
        'plain': content,
        'stats': {
            'title_len': len(title),
            'content_chars': char_count,
        }
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
