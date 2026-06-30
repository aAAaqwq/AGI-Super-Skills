#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat_radar_briefing.py
微信朋友圈AI雷达 - 一键生成日报简报

用法:
    python wechat_radar_briefing.py              # 使用最新的extracted JSON
    python wechat_radar_briefing.py <json_path>  # 使用指定JSON文件
"""

import json
import re
import sys
import httpx
import subprocess
from collections import Counter
from pathlib import Path
from datetime import datetime

# ===== 项目路径 =====
PROJECT_ROOT = Path.home() / "wechat_ai_radar"
sys.path.insert(0, str(PROJECT_ROOT))
import config as cfg

# ===== 报告框架 =====
REPORT_FRAMEWORK = """# 今日朋友圈热点

## 🔥 热门关键词
统计今日最高频词汇

## 📈 热门分类
统计：AI / 活动 / 创业 / SaaS / 出海 / 促销

## 💼 商机发现
自动汇总：AI合作需求 / 合作需求 / 创业动态 / 投资动态

## 👥 高频人物
统计出现最多的人名

## 🧠 AI总结
自动生成今日朋友圈趋势分析
"""

# ===== 分类关键词 =====
CATEGORIES = {
    'AI': ['AI', '人工智能', '大模型', 'ChatGPT', 'LLM', 'AIGC', 'AGI', '智能', '机器学习', '深度学习'],
    '活动': ['活动', '峰会', '论坛', '会议', '沙龙', '分享', '演讲', '发布会', '年会', '路演', '培训', '课程'],
    '创业': ['创业', '创始人', '创业中', '创业日记', '创业分享', '创业记录', '创业历程', '新公司', '开业', '上线', '产品发布'],
    'SaaS': ['SaaS', 'saas', '软件', '工具', '平台', '系统', '管理系统', 'ERP', 'CRM', 'OA', '数字化', '信息化'],
    '出海': ['出海', '跨境', '海外', '全球', '国际', '外贸', '出口', '全球化', '海外市场', 'TikTok', '独立站'],
    '促销': ['促销', '优惠', '打折', '福利', '赠送', '免费', '折扣', '活动价', '特价', '限时', '秒杀', '优惠券', '礼包']
}

# ===== 商机关键词 =====
BUSINESS_KEYWORDS = {
    'AI合作需求': ['AI合作', 'AI伙伴', 'AI联创', '寻求AI', 'AI Partner', 'AI赋能'],
    '合作需求': ['合作', '合伙人', '找合作', '寻求合作', '商务合作', '品牌合作', '渠道合作', '资源合作', '互推', '置换'],
    '创业动态': ['创业中', '新公司', '开业', '上线', '发布', '产品发布', '项目启动', '创业日记', '创业分享'],
    '投资动态': ['融资', '投资', '估值', '天使轮', 'A轮', 'B轮', 'C轮', '上市', 'IPO', '获得投资', '拿到投资']
}

# ===== 停用词 =====
STOPWORDS = {
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '那', '他', '她', '它', '们', '这个', '那个', '什么', '怎么',
    '可以', '没', '因为', '所以', '但是', '如果', '还是', '或者', '而且', '虽然',
    '我们', '你们', '他们', '大家', '被', '把', '让', '给', '向', '从', '能',
    '做', '进行', '使用', '通过', '已经', '正在', '还', '又', '再', '已', '曾',
    '来', '过', '起', '一下', '一点', '有些', '关于', '对于', '以及', '等',
    '哈哈', '哈哈哈', '哈哈哈哈哈', '笑', '转发', '分享', '收藏', '来自', '相册',
    '刚刚', '今天', '昨天', '现在', '刚才', '时候', '终于', '感觉', '觉得',
    '🇨🇳', '🇺🇸', '🇭🇰', '👏', '👍', '❤️', '🙏', '😊', '😂', '😍', '🎉'
}


def find_latest_json():
    """找到最新的extracted JSON文件"""
    data_dir = PROJECT_ROOT / "data"
    json_files = list(data_dir.glob("extracted_*.json"))
    if not json_files:
        return None
    return max(json_files, key=lambda p: p.stat().st_mtime)


def load_moments(json_path):
    """加载朋友圈数据"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_keywords(moments, top_n=20):
    """提取热门关键词"""
    chinese_segs = []
    for m in moments:
        segs = re.findall(r'[\u4e00-\u9fff]{2,6}', m.get('content', ''))
        chinese_segs.extend([s for s in segs if s not in STOPWORDS and len(s) > 1])

    # 特殊词组合并
    word_counts = Counter()
    for w in chinese_segs:
        w_lower = w.lower()
        if w_lower.startswith('ai') and len(w) <= 6:
            word_counts['AI'] += 1
        elif '创业' in w: word_counts['创业'] += 1
        elif '出海' in w or '跨境' in w: word_counts['出海'] += 1
        elif '合作' in w: word_counts['合作'] += 1
        elif '招聘' in w or '求职' in w: word_counts['招聘'] += 1
        elif '投资' in w or '融资' in w: word_counts['投资'] += 1
        elif 'SaaS' in w.upper(): word_counts['SaaS'] += 1
        elif '活动' in w or '峰会' in w or '论坛' in w: word_counts['活动'] += 1
        elif '促销' in w or '优惠' in w or '打折' in w or '福利' in w: word_counts['促销'] += 1
        else: word_counts[w] += 1

    return word_counts.most_common(top_n * 2)


def categorize(moments):
    """分类统计"""
    counts = {}
    for cat, keywords in CATEGORIES.items():
        count = sum(1 for m in moments if any(kw in m.get('content', '') for kw in keywords))
        counts[cat] = count
    return counts


def discover_opportunities(moments):
    """商机发现"""
    results = {k: [] for k in BUSINESS_KEYWORDS}
    for m in moments:
        content = m.get('content', '')
        author = m.get('author_name', '未知')
        for opp_cat, keywords in BUSINESS_KEYWORDS.items():
            for kw in keywords:
                if kw in content:
                    results[opp_cat].append(f"[{author}] {content[:80]}")
                    break
    # 每类最多保留5条
    return {k: v[:5] for k, v in results.items()}


def extract_persons(moments, top_n=10):
    """高频人物"""
    authors = [m.get('author_name', '') for m in moments
               if m.get('author_name') and m.get('author_name') != 'Unknown']
    return Counter(authors).most_common(top_n)


def call_ai_analysis(moments, keywords, categories, persons, opportunities):
    """调用AI生成趋势分析"""
    # 准备摘要内容
    sample = [m['content'] for m in moments[:80] if m['content'].strip()]
    content_text = "\n".join([f"[{i+1}] {c[:100]}" for i, c in enumerate(sample)])

    top_kw = ', '.join([f"{w}({c}次)" for w, c in keywords[:10]])
    top_persons = ', '.join([f"{n}({c}次)" for n, c in persons[:5]])

    prompt = f"""你是一个专业的社交媒体内容分析师。请分析以下微信朋友圈内容，生成今日热点趋势报告。

## 今日朋友圈内容摘要
共{len(moments)}条，代表内容：
{content_text[:6000]}

## 分类统计
AI相关: {categories.get('AI',0)}条 / 活动: {categories.get('活动',0)}条 / 创业: {categories.get('创业',0)}条 / SaaS: {categories.get('SaaS',0)}条 / 出海: {categories.get('出海',0)}条 / 促销: {categories.get('促销',0)}条

## 热门关键词
{top_kw}

## 高频人物 TOP5
{top_persons}

请以JSON格式输出（所有字段必填，中文输出）：
{{
  "trend_summary": "今日朋友圈整体趋势总结（150字以内）",
  "key_findings": ["关键发现1", "关键发现2", "关键发现3", "关键发现4"],
  "market_insights": ["市场洞察1", "市场洞察2", "市场洞察3"],
  "action_recommendations": ["行动建议1", "行动建议2"]
}}
直接输出JSON，不要有其他文字。"""

    headers = {
        "Authorization": f"Bearer {cfg.AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": cfg.AI_MODEL,
        "messages": [
            {"role": "system", "content": "你是专业的社交媒体内容分析师。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 3000
    }

    try:
        resp = httpx.post(f"{cfg.AI_API_URL}/chat/completions", headers=headers, json=payload, timeout=120.0)
        resp.raise_for_status()
        raw = resp.json()['choices'][0]['message']['content']
        # 提取JSON
        start, end = raw.find('{'), raw.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
    except Exception as e:
        print(f"⚠️ AI分析失败: {e}")
    return {}


def generate_report(moments, keywords, categories, persons, opportunities, ai_result):
    """生成Markdown日报"""
    lines = ["# 今日朋友圈热点\n"]
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**数据来源**: 微信朋友圈 ({len(moments)} 条朋友圈)\n---\n")

    # 热门关键词
    lines.append("## 🔥 热门关键词\n")
    lines.append("| 排名 | 关键词 | 出现次数 |")
    lines.append("|------|--------|----------|")
    for i, (kw, c) in enumerate(keywords[:15], 1):
        lines.append(f"| {i} | {kw} | {c}次 |")
    lines.append("")

    # 热门分类
    lines.append("## 📈 热门分类\n")
    cats_sorted = sorted(categories.items(), key=lambda x: -x[1])
    for cat, count in cats_sorted:
        pct = round(count / len(moments) * 100, 1) if moments else 0
        lines.append(f"- **{cat}**: {count}条 ({pct}%)")
    lines.append("")

    # 商机发现
    lines.append("## 💼 商机发现\n")
    for opp_cat, items in opportunities.items():
        emoji = {"AI合作需求": "🤖", "合作需求": "🤝", "创业动态": "🚀", "投资动态": "💰"}[opp_cat]
        lines.append(f"### {emoji} {opp_cat}")
        if items:
            for item in items[:5]:
                lines.append(f"- {item}")
        else:
            lines.append("- 暂无明确信息")
        lines.append("")
    lines.append("")

    # 高频人物
    lines.append("## 👥 高频人物\n")
    lines.append("| 排名 | 人物 | 出现次数 |")
    lines.append("|------|------|----------|")
    for i, (name, c) in enumerate(persons[:10], 1):
        lines.append(f"| {i} | {name} | {c}次 |")
    lines.append("")

    # AI总结
    lines.append("## 🧠 AI总结\n")
    if ai_result:
        lines.append(f"### 📊 今日趋势总结\n{ai_result.get('trend_summary', '（暂无）')}\n")
        lines.append("### 🔍 关键发现\n")
        for f in ai_result.get('key_findings', [])[:4]:
            lines.append(f"- {f}")
        lines.append("\n### 💹 市场洞察\n")
        for ins in ai_result.get('market_insights', [])[:3]:
            lines.append(f"- {ins}")
        lines.append("\n### 🎯 行动建议\n")
        for rec in ai_result.get('action_recommendations', [])[:3]:
            lines.append(f"- {rec}")
    else:
        lines.append("（AI分析暂不可用）")

    lines.append(f"\n---\n*由 WeChat AI Radar 自动生成*")
    return '\n'.join(lines)


def main():
    # 找到JSON文件
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
    else:
        json_path = find_latest_json()

    if not json_path or not json_path.exists():
        print(f"❌ 未找到extracted JSON文件: {json_path}")
        sys.exit(1)

    print(f"📂 使用数据文件: {json_path}")
    moments = load_moments(json_path)
    print(f"📊 共 {len(moments)} 条朋友圈数据\n")

    # 分析
    print("🔍 提取关键词...")
    keywords = extract_keywords(moments)

    print("📈 分类统计...")
    categories = categorize(moments)

    print("💼 商机发现...")
    opportunities = discover_opportunities(moments)

    print("👥 提取高频人物...")
    persons = extract_persons(moments)

    print("🤖 AI趋势分析...")
    ai_result = call_ai_analysis(moments, keywords, categories, persons, opportunities)

    # 生成报告
    print("📝 生成日报...")
    report = generate_report(moments, keywords, categories, persons, opportunities, ai_result)

    # 保存
    output_path = PROJECT_ROOT / "reports" / f"今日朋友圈热点_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n✅ 报告已保存: {output_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("📋 今日朋友圈热点报告 摘要")
    print("=" * 60)
    print(f"总朋友圈数: {len(moments)}条")
    print(f"🔥 热门关键词 TOP5: {' / '.join([f'{w}({c}次)' for w,c in keywords[:5]])}")
    print(f"📈 热门分类: {' / '.join([f'{cat}({count}条)' for cat,count in sorted(categories.items(), key=lambda x:-x[1])[:5]])}")
    print(f"👥 高频人物 TOP3: {' / '.join([f'{n}({c}次)' for n,c in persons[:3]])}")
    if ai_result:
        print(f"\n🧠 AI总结: {ai_result.get('trend_summary', '')[:100]}")
    print(f"\n📁 完整报告: {output_path}")

    return output_path


if __name__ == "__main__":
    output_path = main()

    # 自动生成Word文档
    try:
        from reports.daily_report_to_docx import *
        print("\n📄 生成Word文档...")
    except Exception as e:
        print(f"\n⚠️ Word文档生成失败: {e}")