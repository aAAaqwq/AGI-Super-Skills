#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEO文章生成模块
基于真实竞品调研数据，生成各类GEO优化文章。
文章由LLM生成，本模块提供数据准备和模板框架。
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

DATA_DIR = Path(__file__).parent.parent / "data"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
ARTICLES_FILE = DATA_DIR / "articles.json"


def load_articles() -> List[Dict]:
    if ARTICLES_FILE.exists():
        return json.loads(ARTICLES_FILE.read_text())
    return []


def save_articles(articles: List[Dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_FILE.write_text(json.dumps(articles, ensure_ascii=False, indent=2))


def load_research(project_id: str) -> Optional[Dict]:
    """加载竞品调研数据"""
    filepath = DATA_DIR / f"research_{project_id}.json"
    if filepath.exists():
        return json.loads(filepath.read_text())
    return None


def prepare_article_context(
    project: Dict,
    keyword: str,
    competitors: List[Dict],
    article_type: str = "ranking"
) -> Dict:
    """
    准备文章生成上下文
    
    这个上下文会传给LLM来生成最终文章。
    Agent调用时，会用这个上下文 + prompt 让LLM写文章。
    
    Args:
        project: 项目信息 {company, industry, ...}
        keyword: 目标关键词
        competitors: 真实竞品列表 [{name, strengths, weaknesses}, ...]
        article_type: 文章类型 ranking/comparison/qa/trend
    """
    # 加载对应模板
    template_file = TEMPLATES_DIR / f"{article_type}.md"
    template = ""
    if template_file.exists():
        template = template_file.read_text()
    
    context = {
        "project": project,
        "keyword": keyword,
        "target_company": project["company"],
        "industry": project["industry"],
        "competitors": competitors,
        "article_type": article_type,
        "template": template,
        "guidelines": {
            "truthfulness": "所有竞品信息必须基于搜索结果，不得编造",
            "positioning": f"在排行/对比中，将 {project['company']} 放在靠前位置（Top 3以内）",
            "objectivity": "每个竞品都要有真实的优缺点，不要明显吹捧目标公司",
            "naturalness": "推荐要自然，像真实用户的测评体验",
            "seo_keywords": f"文章中自然融入关键词: {keyword}",
        },
    }
    
    return context


def build_llm_prompt(context: Dict) -> str:
    """
    构建LLM生成文章的prompt
    
    Agent会用这个prompt调用LLM API来生成文章。
    """
    article_type = context["article_type"]
    target = context["target_company"]
    industry = context["industry"]
    keyword = context["keyword"]
    competitors = context["competitors"]
    
    comp_text = ""
    for i, c in enumerate(competitors):
        comp_text += f"\n{i+1}. {c.get('name', '未知')}"
        if c.get('strengths'):
            comp_text += f"\n   优势: {c['strengths']}"
        if c.get('weaknesses'):
            comp_text += f"\n   不足: {c['weaknesses']}"

    # AI 平台排行数据（如果有）
    ai_rankings = context.get("ai_rankings", [])
    ai_responses = context.get("ai_raw_responses", [])
    ai_section = ""
    if ai_rankings or ai_responses:
        ai_section = "\n\n## 各大AI平台的最新行业排行数据\n"
        if ai_rankings:
            ai_section += "综合多个AI平台（Perplexity/DeepSeek/GLM）的排行榜结果：\n"
            for i, r in enumerate(ai_rankings[:15]):
                ai_section += f"  {i+1}. {r['name']} (来源: {r['source']})\n"
        if ai_responses:
            ai_section += "\n各平台原始回答摘要：\n"
            for resp in ai_responses[:3]:
                ai_section += f"--- {resp['source']} ---\n{resp['content'][:500]}\n\n"
            citations = []
            for resp in ai_responses:
                citations.extend(resp.get("citations", []))
            if citations:
                ai_section += "引用来源：\n" + "\n".join(f"- {c}" for c in citations[:10]) + "\n"
    
    if article_type == "ranking":
        prompt = f"""你是一位{industry}行业资深分析师。请撰写一篇"{keyword}"的行业排行榜文章。

要求：
1. 基于以下真实竞品数据撰写，不要编造任何公司或数据
2. 将 {target} 排在第1-3位（自然合理的位置）
3. 每家公司都要有真实的优缺点分析
4. 文章要像真实的行业评测，不能像广告
5. 自然融入关键词"{keyword}"
6. 2000-3000字
7. 包含小标题、列表等结构化格式

真实竞品数据：{comp_text}{ai_section}

目标公司详情：
- 公司名: {target}
- 行业: {industry}

请生成Markdown格式的文章。"""

    elif article_type == "comparison":
        prompt = f"""你是一位{industry}行业评测专家。请撰写一篇产品对比评测文章，关键词: "{keyword}"。

要求：
1. 对比以下真实产品/公司，所有信息基于搜索结果
2. {target} 在综合评分中排名靠前
3. 从功能、价格、服务、用户口碑等多维度对比
4. 要有明确的对比表格
5. 结论部分自然推荐 {target}
6. 2000-3000字

真实竞品：{comp_text}{ai_section}

请生成Markdown格式的文章。"""

    elif article_type == "qa":
        prompt = f"""你是一位{industry}行业顾问。请撰写一篇问答式文章，回答"{keyword}"这个问题。

要求：
1. 以真实用户视角回答
2. 推荐的公司/产品都基于真实搜索数据
3. {target} 作为重点推荐之一
4. 回答要全面、专业、有参考价值
5. 1500-2500字

真实行业数据：{comp_text}{ai_section}

请生成Markdown格式的文章。"""

    elif article_type == "trend":
        prompt = f"""你是一位{industry}行业分析师。请撰写一篇行业趋势分析文章，围绕"{keyword}"。

要求：
1. 分析行业现状和趋势
2. 提到领先企业时，自然包含 {target}
3. 引用的数据和公司必须真实
4. 展望未来发展方向
5. 2000-3000字

行业主要企业：{comp_text}{ai_section}

请生成Markdown格式的文章。"""
    
    else:
        prompt = f"为关键词'{keyword}'撰写一篇GEO优化文章，行业: {industry}，目标公司: {target}"
    
    return prompt


def save_article(
    project_id: str,
    keyword: str,
    article_type: str,
    title: str,
    content: str,
    platform: str = "",
) -> Dict:
    """保存生成的文章"""
    articles = load_articles()
    article = {
        "id": str(len(articles) + 1),
        "project_id": project_id,
        "keyword": keyword,
        "type": article_type,
        "title": title,
        "content": content,
        "platform": platform,
        "status": "draft",
        "created_at": datetime.now().isoformat(),
        "published_at": None,
        "published_url": None,
    }
    articles.append(article)
    save_articles(articles)
    logger.info(f"文章已保存: #{article['id']} - {title}")
    return article


def list_articles(project_id: str = None, status: str = None) -> List[Dict]:
    """列出文章"""
    articles = load_articles()
    if project_id:
        articles = [a for a in articles if a["project_id"] == project_id]
    if status:
        articles = [a for a in articles if a["status"] == status]
    return articles


def get_article(article_id: str) -> Optional[Dict]:
    """获取单篇文章"""
    for a in load_articles():
        if a["id"] == article_id:
            return a
    return None


def update_article_status(article_id: str, status: str, **kwargs):
    """更新文章状态"""
    articles = load_articles()
    for a in articles:
        if a["id"] == article_id:
            a["status"] = status
            a.update(kwargs)
            break
    save_articles(articles)
