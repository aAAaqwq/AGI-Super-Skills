#!/usr/bin/env python3
"""
企业微信 - 问答处理流程
基于知识库搜索 + LLM 生成答案
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import logging
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from openai import OpenAI
    from psycopg2 import extensions
    import numpy as np
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    print("请安装: pip install openai psycopg2-binary numpy")
    sys.exit(1)


# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KnowledgeBase:
    """知识库搜索"""

    def __init__(self):
        self.db_url = os.environ.get("KB_DB_URL", "postgresql://postgres@localhost/wecom_kb")
        self.top_k = int(os.environ.get("KB_TOP_K", "3"))
        self.similarity_threshold = float(os.environ.get("KB_SIMILARITY_THRESHOLD", "0.7"))

    def get_embedding(self, text: str, api_key: str, api_base: str = "https://api.moonshot.cn/v1"):
        """获取文本向量嵌入"""
        client = OpenAI(api_key=api_key, base_url=api_base)

        try:
            response = client.embeddings.create(
                model="embedding-v1",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"获取嵌入失败: {e}")
            return None

    def search(self, query: str, api_key: str = None, api_base: str = None) -> list:
        """
        搜索知识库

        Returns:
            List[dict]: [{
                "content": str,
                "similarity": float,
                "category": str,
                "metadata": dict
            }]
        """
        # 获取查询向量
        query_embedding = self.get_embedding(query, api_key, api_base)
        if not query_embedding:
            return []

        # 查询数据库
        conn = extensions.connect(self.db_url)
        cur = conn.cursor()

        try:
            # 向量相似度搜索
            cur.execute("""
                SELECT
                    content,
                    1 - (embedding <=> %s::vector) as similarity,
                    category,
                    metadata
                FROM knowledge_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, query_embedding, self.top_k))

            results = []
            for content, similarity, category, metadata in cur.fetchall():
                results.append({
                    "content": content,
                    "similarity": float(similarity),
                    "category": category,
                    "metadata": json.loads(metadata) if metadata else {}
                })

            logger.info(f"搜索到 {len(results)} 个结果，最高相似度: {results[0]['similarity'] if results else 0:.2f}")
            return results

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
        finally:
            cur.close()
            conn.close()


class AnswerGenerator:
    """答案生成器"""

    def __init__(self):
        self.api_key = os.environ.get("LLM_API_KEY") or os.environ.get("KIMI_API_KEY")
        self.api_base = os.environ.get("LLM_API_BASE", "https://api.moonshot.cn/v1")
        self.model = os.environ.get("LLM_MODEL", "moonshot-v1-8k")
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_base)

    def generate(self, query: str, kb_results: list) -> dict:
        """
        基于知识库生成答案

        Returns:
            dict: {
                "answer": str,
                "confidence": float,
                "sources": list,
                "need_escalation": bool
            }
        """
        if not kb_results:
            return {
                "answer": "抱歉，这个问题我暂时无法回答，已为您转接人工客服。",
                "confidence": 0.0,
                "sources": [],
                "need_escalation": True
            }

        # 构建上下文
        context_parts = []
        for i, result in enumerate(kb_results, 1):
            context_parts.append(f"[来源 {i}] {result['content'].strip()}")

        context = "\n\n".join(context_parts)

        # 最高相似度
        max_similarity = kb_results[0]["similarity"]

        # 构建提示词
        system_prompt = """你是一个专业的客服助手。请基于提供的知识库内容回答用户问题。

**重要规则**：
1. 优先使用知识库中的信息
2. 保持语言自然、专业、友好
3. 如果知识库中没有直接答案，诚实地说明无法回答
4. 可以适当引用多个来源
5. 保持回答简洁明了，通常不超过200字

**回答格式**：
- 直接给出答案
- 如有多个要点，用序号列出
- 必要时提供额外建议"""

        user_prompt = f"""知识库内容：
{context}

用户问题：{query}

请给出专业的回答。"""

        # 调用 LLM
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            answer = response.choices[0].message.content.strip()

            # 判断是否需要人工介入
            need_escalation = max_similarity < float(os.environ.get("KB_SIMILARITY_THRESHOLD", "0.7"))

            return {
                "answer": answer,
                "confidence": max_similarity,
                "sources": [r["category"] for r in kb_results],
                "need_escalation": need_escalation
            }

        except Exception as e:
            logger.error(f"生成答案失败: {e}")
            return {
                "answer": "抱歉，我遇到了一些技术问题，已为您转接人工客服。",
                "confidence": 0.0,
                "sources": [],
                "need_escalation": True
            }


class WecomClient:
    """企业微信客户端（简化版）"""

    def __init__(self):
        self.corp_id = os.environ.get("WECOM_CORP_ID")
        self.agent_id = os.environ.get("WECOM_AGENT_ID", "1000002")
        self.secret = os.environ.get("WECOM_AGENT_SECRET")
        self.access_token = None
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"

    def send_text(self, external_userid: str, text: str) -> bool:
        """发送文本消息"""
        # 简化实现：只记录日志
        logger.info(f"📤 发送消息给 {external_userid}: {text[:50]}...")
        return True


def handle_question(
    external_userid: str,
    question: str,
    user_name: str = "客户"
) -> dict:
    """
    处理用户问题

    Returns:
        dict: {
            "success": bool,
            "answer": str,
            "escalated": bool,
            "confidence": float
        }
    """

    logger.info(f"❓ 收到问题: {question[:50]}... from {user_name} ({external_userid})")

    # 初始化组件
    kb = KnowledgeBase()
    generator = AnswerGenerator()
    wecom = WecomClient()

    # 1. 搜索知识库
    kb_results = kb.search(question, api_key=generator.api_key, api_base=generator.api_base)

    # 2. 生成答案
    result = generator.generate(question, kb_results)

    logger.info(f"✓ 生成答案 (置信度: {result['confidence']:.2f})")

    # 3. 发送回复
    if result["need_escalation"]:
        # 需要人工介入
        escalation_msg = f"""⏳ {result['answer']}

请您稍候，我立即为您联系人工客服。如有急事，可直接致电：400-XXX-XXXX"""

        wecom.send_text(external_userid, escalation_msg)

        logger.warning(f"⚠️  转人工: {user_name} - {question}")

        return {
            "success": True,
            "answer": escalation_msg,
            "escalated": True,
            "confidence": result["confidence"]
        }
    else:
        # 自动回复
        wecom.send_text(external_userid, result["answer"])

        logger.info(f"✅ 自动回复: {result['answer'][:50]}...")

        return {
            "success": True,
            "answer": result["answer"],
            "escalated": False,
            "confidence": result["confidence"]
        }


# 测试入口
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试问答流程")
    parser.add_argument("--user-id", required=True, help="外部用户 ID")
    parser.add_argument("--question", required=True, help="用户问题")
    parser.add_argument("--name", default="测试用户", help="用户姓名")

    args = parser.parse_args()

    # 检查环境变量
    required_vars = ["KB_DB_URL", "LLM_API_KEY"]
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing:
        print(f"❌ 缺少环境变量: {', '.join(missing)}")
        sys.exit(1)

    # 执行
    result = handle_question(
        external_userid=args.user_id,
        question=args.question,
        user_name=args.name
    )

    print(f"\n📊 结果:")
    print(f"   成功: {result['success']}")
    print(f"   转人工: {result['escalated']}")
    print(f"   置信度: {result['confidence']:.2f}")
    print(f"   回复: {result['answer']}")

    sys.exit(0 if result["success"] else 1)
