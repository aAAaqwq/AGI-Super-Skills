#!/usr/bin/env python3
"""
企业微信客服知识库导入工具
支持 Markdown 文件导入，自动切片并向量化
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
import re
from typing import List, Dict
import argparse

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from openai import OpenAI
except ImportError:
    print("❌ 缺少依赖: pip install openai psycopg2-binary")
    sys.exit(1)


def read_markdown(file_path: str) -> str:
    """读取 Markdown 文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def split_text(text: str, max_length: int = 500, overlap: int = 50) -> List[str]:
    """
    智能切分文本
    - 按段落切分
    - 保持语义完整
    - 添加重叠区域
    """
    # 按标题和段落分割
    sections = re.split(r'\n(#{1,3}\s.+)\n', text)

    chunks = []
    current_chunk = ""
    current_title = ""

    for section in sections:
        if section.startswith('#'):
            # 这是标题
            if current_chunk:
                chunks.append(current_title + "\n" + current_chunk.strip())
            current_title = section
            current_chunk = ""
        else:
            # 这是内容
            paragraphs = section.split('\n\n')
            for para in paragraphs:
                if len(current_chunk) + len(para) > max_length:
                    if current_chunk:
                        chunks.append((current_title + "\n" + current_chunk.strip()) if current_title else current_chunk.strip())
                    current_chunk = para + "\n\n"
                    current_title = ""
                else:
                    current_chunk += para + "\n\n"

    if current_chunk:
        chunks.append((current_title + "\n" + current_chunk.strip()) if current_title else current_chunk.strip())

    return chunks


def get_embedding(text: str, api_key: str, api_base: str = "https://api.moonshot.cn/v1") -> List[float]:
    """
    获取文本向量嵌入
    使用 Kimi API
    """
    client = OpenAI(
        api_key=api_key,
        base_url=api_base
    )

    try:
        response = client.embeddings.create(
            model="embedding-v1",  # Kimi 嵌入模型
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"⚠️  嵌入失败: {e}")
        return None


def import_to_db(
    chunks: List[str],
    category: str = "default",
    tags: List[str] = None,
    db_url: str = "postgresql://postgres@localhost/wecom_kb",
    api_key: str = None,
    refresh: bool = False
):
    """导入到数据库"""

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # 如果是刷新模式，先清空该分类
    if refresh:
        cur.execute("DELETE FROM knowledge_chunks WHERE category = %s", (category,))
        print(f"🗑️  已清空分类: {category}")

    # 批量插入
    inserted = 0
    skipped = 0

    for i, chunk in enumerate(chunks):
        print(f"📝 处理 {i+1}/{len(chunks)}... ", end='')

        # 检查是否已存在
        cur.execute("SELECT id FROM knowledge_chunks WHERE content = %s LIMIT 1", (chunk,))
        if cur.fetchone():
            print("✓ (已存在)")
            skipped += 1
            continue

        # 获取嵌入向量
        embedding = get_embedding(chunk, api_key)
        if not embedding:
            print("✗ (嵌入失败)")
            skipped += 1
            continue

        # 插入数据库
        cur.execute("""
            INSERT INTO knowledge_chunks (content, embedding, category, tags, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            chunk,
            embedding,
            category,
            tags or [],
            json.dumps({"source": "import_script"})
        ))

        inserted += 1
        print("✓")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ 导入完成！")
    print(f"   新增: {inserted}")
    print(f"   跳过: {skipped}")


def main():
    parser = argparse.ArgumentParser(description="导入知识库到 PostgreSQL")
    parser.add_argument("--input", "-i", required=True, help="Markdown 文件路径")
    parser.add_argument("--category", "-c", default="default", help="分类名称")
    parser.add_argument("--tags", "-t", nargs="*", default=[], help="标签列表")
    parser.add_argument("--db", default="postgresql://postgres@localhost/wecom_kb", help="数据库连接")
    parser.add_argument("--key", help="Kimi API Key (默认从环境变量读取)")
    parser.add_argument("--refresh", action="store_true", help="刷新模式（清空该分类后重新导入）")
    parser.add_argument("--rebuild", action="store_true", help="重建所有嵌入")

    args = parser.parse_args()

    # 获取 API Key
    api_key = args.key or os.environ.get("KIMI_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        print("❌ 请提供 API Key (--key 或环境变量)")
        sys.exit(1)

    # 读取文件
    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    print(f"📖 读取文件: {args.input}")
    text = read_markdown(args.input)

    # 切分文本
    print(f"✂️  切分文本...")
    chunks = split_text(text)
    print(f"   共 {len(chunks)} 个片段")

    # 导入数据库
    print(f"💾 导入数据库...")
    import_to_db(
        chunks=chunks,
        category=args.category,
        tags=args.tags,
        db_url=args.db,
        api_key=api_key,
        refresh=args.refresh
    )


if __name__ == "__main__":
    main()
