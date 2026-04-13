#!/usr/bin/env python3
"""
知识库构建器 - Knowledge Base Builder
功能：
1. 自动整理聊天记录，提取有价值信息
2. 生成 FAQ 问答对
3. 构建个人 wiki/知识库
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import hashlib

class KnowledgeBase:
    """知识库构建器"""
    
    def __init__(self):
        self.home = Path.home()
        self.kb_dir = Path.home() / ".openclaw" / "workspace" / "knowledge-base"
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        
        # 子目录
        self.faqs_dir = self.kb_dir / "faqs"
        self.wiki_dir = self.kb_dir / "wiki"
        self.raw_dir = self.kb_dir / "raw"
        self.index_file = self.kb_dir / "index.json"
        
        for d in [self.faqs_dir, self.wiki_dir, self.raw_dir]:
            d.mkdir(exist_ok=True)
        
        self.load_index()
    
    def load_index(self):
        """加载知识库索引"""
        if self.index_file.exists():
            with open(self.index_file) as f:
                self.index = json.load(f)
        else:
            self.index = {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_entries": 0,
                "categories": {},
                "faqs": [],
                "wiki_pages": []
            }
            self.save_index()
    
    def save_index(self):
        """保存知识库索引"""
        self.index["last_updated"] = datetime.now().isoformat()
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)
    
    def extract_from_chat(self, chat_content: str, source: str = "unknown") -> List[Dict]:
        """
        从聊天记录中提取知识条目
        
        Args:
            chat_content: 聊天内容
            source: 来源标识
            
        Returns:
            提取的知识条目列表
        """
        entries = []
        
        # 提取问答对（Q: ... A: ... 格式）
        qa_pattern = r'(?:Q|问|问题)[：:]\s*(.+?)\n(?:A|答|回答)[：:]\s*(.+?)(?=\n(?:Q|问|问题)[：:]|$)'
        for match in re.finditer(qa_pattern, chat_content, re.DOTALL | re.IGNORECASE):
            entries.append({
                "type": "qa",
                "question": match.group(1).strip(),
                "answer": match.group(2).strip(),
                "source": source,
                "extracted_at": datetime.now().isoformat()
            })
        
        # 提取重要指令（"记住...", "以后..." 等）
        instruction_patterns = [
            r'(?:记住|记住这个|请记住)[：:]\s*(.+?)(?=\n|$)',
            r'(?:以后|下次|以后每次)[：:]\s*(.+?)(?=\n|$)',
            r'(?:重要|注意)[：:]\s*(.+?)(?=\n|$)',
        ]
        for pattern in instruction_patterns:
            for match in re.finditer(pattern, chat_content, re.IGNORECASE):
                entries.append({
                    "type": "instruction",
                    "content": match.group(1).strip(),
                    "source": source,
                    "extracted_at": datetime.now().isoformat()
                })
        
        # 提取技术方案/解决方案
        solution_pattern = r'(?:方案|解决方案|步骤)[：:]\s*\n?(.+?)(?=\n\n|\Z)'
        for match in re.finditer(solution_pattern, chat_content, re.DOTALL | re.IGNORECASE):
            content = match.group(1).strip()
            if len(content) > 50:  # 过滤太短的
                entries.append({
                    "type": "solution",
                    "content": content[:500],  # 限制长度
                    "source": source,
                    "extracted_at": datetime.now().isoformat()
                })
        
        return entries
    
    def add_to_faq(self, question: str, answer: str, category: str = "general") -> str:
        """
        添加 FAQ 条目
        
        Returns:
            entry_id: 条目ID
        """
        entry_id = hashlib.md5(f"{question}{datetime.now()}".encode()).hexdigest()[:12]
        
        faq_entry = {
            "id": entry_id,
            "question": question,
            "answer": answer,
            "category": category,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "usage_count": 0
        }
        
        # 保存到文件
        faq_file = self.faqs_dir / f"{category}_{entry_id}.json"
        with open(faq_file, "w", encoding="utf-8") as f:
            json.dump(faq_entry, f, indent=2, ensure_ascii=False)
        
        # 更新索引
        self.index["faqs"].append({
            "id": entry_id,
            "question": question,
            "category": category,
            "file": str(faq_file.relative_to(self.kb_dir))
        })
        self.index["total_entries"] += 1
        self.save_index()
        
        return entry_id
    
    def create_wiki_page(self, title: str, content: str, tags: List[str] = None) -> str:
        """
        创建 Wiki 页面
        
        Returns:
            page_id: 页面ID
        """
        page_id = hashlib.md5(f"{title}{datetime.now()}".encode()).hexdigest()[:12]
        
        # 生成 Markdown 文件
        filename = f"{title.replace(' ', '_').replace('/', '_')}.md"
        page_file = self.wiki_dir / filename
        
        md_content = f"""# {title}

> 创建时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}
> 标签: {', '.join(tags or [])}

---

{content}

---

*由 KnowledgeBase Builder 自动生成*
"""
        
        with open(page_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        # 更新索引
        self.index["wiki_pages"].append({
            "id": page_id,
            "title": title,
            "file": str(page_file.relative_to(self.kb_dir)),
            "tags": tags or [],
            "created_at": datetime.now().isoformat()
        })
        self.save_index()
        
        return page_id
    
    def search_faqs(self, query: str, limit: int = 5) -> List[Dict]:
        """
        搜索 FAQ
        
        简单实现：基于关键词匹配
        """
        results = []
        query_lower = query.lower()
        
        for faq_info in self.index.get("faqs", []):
            faq_file = self.kb_dir / faq_info["file"]
            if faq_file.exists():
                with open(faq_file) as f:
                    faq = json.load(f)
                
                # 简单匹配
                question_lower = faq["question"].lower()
                answer_lower = faq["answer"].lower()
                
                if any(keyword in question_lower or keyword in answer_lower 
                       for keyword in query_lower.split()):
                    results.append(faq)
                    
                    if len(results) >= limit:
                        break
        
        return results
    
    def get_stats(self) -> Dict:
        """获取知识库统计"""
        return {
            "total_entries": self.index["total_entries"],
            "total_faqs": len(self.index.get("faqs", [])),
            "total_wiki_pages": len(self.index.get("wiki_pages", [])),
            "categories": list(self.index.get("categories", {}).keys()),
            "last_updated": self.index["last_updated"],
            "kb_dir": str(self.kb_dir)
        }
    
    def export_to_markdown(self, output_file: str = None) -> str:
        """
        导出知识库为 Markdown 文档
        """
        if output_file is None:
            output_file = self.kb_dir / f"knowledge_base_{datetime.now().strftime('%Y%m%d')}.md"
        
        lines = [
            "# 📚 知识库",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"> 总条目数: {self.index['total_entries']}",
            "",
            "---",
            "",
            "## 📋 FAQ 问答",
            ""
        ]
        
        # FAQ 部分
        for faq_info in self.index.get("faqs", []):
            faq_file = self.kb_dir / faq_info["file"]
            if faq_file.exists():
                with open(faq_file) as f:
                    faq = json.load(f)
                lines.extend([
                    f"### Q: {faq['question']}",
                    "",
                    f"{faq['answer']}",
                    "",
                    f"*分类: {faq['category']} | 更新时间: {faq['updated_at'][:10]}*",
                    "",
                    "---",
                    ""
                ])
        
        # Wiki 部分
        lines.extend([
            "",
            "## 📝 Wiki 页面",
            ""
        ])
        
        for page_info in self.index.get("wiki_pages", []):
            lines.extend([
                f"- **{page_info['title']}**",
                f"  - 标签: {', '.join(page_info.get('tags', []))}",
                f"  - 文件: `{page_info['file']}`",
                ""
            ])
        
        content = "\n".join(lines)
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        return str(output_file)
    
    def auto_build_from_memory(self):
        """
        自动从 memory 目录构建知识库
        """
        memory_dir = Path.home() / ".openclaw" / "workspace" / "memory"
        
        if not memory_dir.exists():
            return {"error": "memory 目录不存在"}
        
        stats = {
            "processed_files": 0,
            "extracted_entries": 0,
            "added_faqs": 0,
            "created_wiki": 0
        }
        
        # 处理每日记忆文件
        for md_file in memory_dir.glob("2026-*.md"):
            stats["processed_files"] += 1
            
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 提取知识
            entries = self.extract_from_chat(content, source=md_file.name)
            stats["extracted_entries"] += len(entries)
            
            # 将 QA 添加到 FAQ
            for entry in entries:
                if entry["type"] == "qa":
                    self.add_to_faq(
                        entry["question"],
                        entry["answer"],
                        category="auto_extracted"
                    )
                    stats["added_faqs"] += 1
        
        return stats


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="知识库构建器")
    parser.add_argument("action", choices=[
        "extract", "add-faq", "create-wiki", "search", "stats", "export", "auto-build"
    ], help="操作类型")
    parser.add_argument("--file", "-f", help="聊天文件路径")
    parser.add_argument("--question", "-q", help="FAQ 问题")
    parser.add_argument("--answer", "-a", help="FAQ 答案")
    parser.add_argument("--title", "-t", help="Wiki 标题")
    parser.add_argument("--content", "-c", help="Wiki 内容或聊天内容")
    parser.add_argument("--category", default="general", help="分类")
    parser.add_argument("--tags", help="标签（逗号分隔）")
    
    args = parser.parse_args()
    
    kb = KnowledgeBase()
    
    if args.action == "extract":
        if not args.content and not args.file:
            print("❌ 请提供 --content 或 --file")
            return
        
        content = args.content
        if args.file:
            with open(args.file) as f:
                content = f.read()
        
        entries = kb.extract_from_chat(content, args.file or "cli")
        print(f"✅ 提取了 {len(entries)} 条知识:")
        for i, e in enumerate(entries[:5], 1):
            print(f"\n  {i}. [{e['type']}] {str(e)[:100]}...")
        if len(entries) > 5:
            print(f"\n  ... 还有 {len(entries) - 5} 条")
    
    elif args.action == "add-faq":
        if not args.question or not args.answer:
            print("❌ 请提供 --question 和 --answer")
            return
        entry_id = kb.add_to_faq(args.question, args.answer, args.category)
        print(f"✅ FAQ 已添加 (ID: {entry_id})")
    
    elif args.action == "create-wiki":
        if not args.title or not args.content:
            print("❌ 请提供 --title 和 --content")
            return
        tags = args.tags.split(",") if args.tags else []
        page_id = kb.create_wiki_page(args.title, args.content, tags)
        print(f"✅ Wiki 页面已创建 (ID: {page_id})")
    
    elif args.action == "search":
        if not args.question:
            print("❌ 请提供 --question 作为搜索关键词")
            return
        results = kb.search_faqs(args.question)
        print(f"🔍 找到 {len(results)} 个相关 FAQ:")
        for r in results:
            print(f"\n  Q: {r['question']}")
            print(f"  A: {r['answer'][:100]}...")
    
    elif args.action == "stats":
        stats = kb.get_stats()
        print("📊 知识库统计:")
        for k, v in stats.items():
            print(f"   {k}: {v}")
    
    elif args.action == "export":
        output = kb.export_to_markdown()
        print(f"✅ 知识库已导出: {output}")
    
    elif args.action == "auto-build":
        print("🔄 自动构建知识库...")
        result = kb.auto_build_from_memory()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
