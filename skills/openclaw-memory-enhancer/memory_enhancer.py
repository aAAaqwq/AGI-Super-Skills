#!/usr/bin/env python3
"""
OpenClaw 记忆增强器 - Memory Enhancer with RAG
功能：
1. 向量语义检索（Sentence Transformers）
2. 自动加载 OpenClaw 记忆文件
3. 对话中智能召回相关记忆
4. 记忆关联图谱构建
"""

import os
import json
import re
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import hashlib

class MemoryEnhancer:
    """OpenClaw 记忆增强器 - 让 OpenClaw 拥有长期记忆"""
    
    def __init__(self):
        self.home = Path.home()
        self.workspace = self.home / ".openclaw" / "workspace"
        self.memory_dir = self.workspace / "memory"
        self.kb_dir = self.workspace / "knowledge-base"
        self.vector_dir = self.kb_dir / "vectors"
        
        # 确保目录存在
        for d in [self.kb_dir, self.vector_dir, self.kb_dir / "faqs", self.kb_dir / "wiki"]:
            d.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.kb_dir / "memory_index.json"
        self.embeddings_file = self.vector_dir / "embeddings.npy"
        self.metadata_file = self.vector_dir / "metadata.json"
        
        # 加载或初始化
        self.load_index()
        self.load_embeddings()
        
        # 尝试加载 sentence-transformers
        self.encoder = None
        self._init_encoder()
    
    def _init_encoder(self):
        """初始化向量编码器"""
        try:
            from sentence_transformers import SentenceTransformer
            # 使用轻量级模型，适合本地运行
            self.encoder = SentenceTransformer('paraphrase-MiniLM-L3-v2')
            print("✅ 向量编码器已加载")
        except ImportError:
            print("⚠️  sentence-transformers 未安装，使用简单词频匹配")
            print("     安装: pip install sentence-transformers")
        except Exception as e:
            print(f"⚠️  编码器加载失败: {e}")
    
    def load_index(self):
        """加载记忆索引"""
        if self.index_file.exists():
            with open(self.index_file) as f:
                self.index = json.load(f)
        else:
            self.index = {
                "version": "2.0",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_memories": 0,
                "categories": {},
                "sources": []
            }
            self.save_index()
    
    def save_index(self):
        """保存记忆索引"""
        self.index["last_updated"] = datetime.now().isoformat()
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)
    
    def load_embeddings(self):
        """加载向量嵌入"""
        if self.embeddings_file.exists() and self.metadata_file.exists():
            try:
                self.embeddings = np.load(self.embeddings_file)
                with open(self.metadata_file) as f:
                    self.metadata = json.load(f)
                print(f"✅ 已加载 {len(self.metadata)} 条记忆向量")
            except Exception as e:
                print(f"⚠️  加载向量失败: {e}")
                self.embeddings = np.array([])
                self.metadata = []
        else:
            self.embeddings = np.array([])
            self.metadata = []
    
    def save_embeddings(self):
        """保存向量嵌入"""
        if len(self.embeddings) > 0:
            np.save(self.embeddings_file, self.embeddings)
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def encode_text(self, text: str) -> np.ndarray:
        """将文本编码为向量"""
        if self.encoder:
            return self.encoder.encode(text)
        else:
            # fallback: 简单的词频向量
            words = set(text.lower().split())
            # 创建一个简单的哈希向量
            vec = np.zeros(384)
            for word in words:
                hash_val = hash(word) % 384
                vec[hash_val] = 1
            return vec
    
    def add_memory(self, content: str, source: str = "manual", 
                   memory_type: str = "general", metadata: Dict = None) -> str:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            source: 来源（如 memory/2026-02-22.md, chat, faq）
            memory_type: 类型（general, qa, instruction, solution）
            metadata: 额外元数据
        """
        memory_id = hashlib.md5(f"{content}{datetime.now()}".encode()).hexdigest()[:12]
        
        memory_entry = {
            "id": memory_id,
            "content": content,
            "source": source,
            "type": memory_type,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        # 编码为向量
        embedding = self.encode_text(content)
        
        # 添加到向量库
        if len(self.embeddings) == 0:
            self.embeddings = np.array([embedding])
        else:
            self.embeddings = np.vstack([self.embeddings, embedding])
        
        self.metadata.append(memory_entry)
        
        # 更新索引
        self.index["total_memories"] = len(self.metadata)
        if source not in self.index["sources"]:
            self.index["sources"].append(source)
        
        # 保存
        self.save_embeddings()
        self.save_index()
        
        return memory_id
    
    def search_memory(self, query: str, top_k: int = 5, threshold: float = 0.5) -> List[Dict]:
        """
        语义搜索记忆
        
        Args:
            query: 查询内容
            top_k: 返回最相关的k条
            threshold: 相似度阈值（0-1）
            
        Returns:
            相关记忆列表
        """
        if len(self.metadata) == 0:
            return []
        
        # 编码查询
        query_vec = self.encode_text(query)
        
        # 计算相似度
        if len(self.embeddings.shape) == 1:
            similarities = np.dot(self.embeddings, query_vec)
        else:
            similarities = np.dot(self.embeddings, query_vec) / (
                np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_vec) + 1e-8
            )
        
        # 获取 top-k
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if similarities[idx] >= threshold:
                memory = self.metadata[idx].copy()
                memory["similarity"] = float(similarities[idx])
                results.append(memory)
        
        return results
    
    def load_openclaw_memory(self):
        """自动加载 OpenClaw 的记忆文件"""
        loaded_count = 0
        
        # 1. 加载 memory/ 目录下的所有 .md 文件
        if self.memory_dir.exists():
            for md_file in self.memory_dir.glob("*.md"):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 按段落分割
                    paragraphs = content.split('\n\n')
                    for para in paragraphs:
                        para = para.strip()
                        if len(para) > 50:  # 只保存有意义的段落
                            self.add_memory(
                                content=para,
                                source=f"memory/{md_file.name}",
                                memory_type="daily_log"
                            )
                            loaded_count += 1
                    
                    print(f"✅ 已加载 {md_file.name}")
                except Exception as e:
                    print(f"⚠️  加载 {md_file.name} 失败: {e}")
        
        # 2. 加载 CAPABILITIES.md
        capabilities_file = self.memory_dir / "CAPABILITIES.md"
        if capabilities_file.exists():
            try:
                with open(capabilities_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 提取能力条目
                sections = re.split(r'###\s+', content)
                for section in sections[1:]:  # 跳过标题
                    if len(section) > 100:
                        self.add_memory(
                            content=section[:500],  # 限制长度
                            source="memory/CAPABILITIES.md",
                            memory_type="capability"
                        )
                        loaded_count += 1
                
                print(f"✅ 已加载 CAPABILITIES.md")
            except Exception as e:
                print(f"⚠️  加载 CAPABILITIES.md 失败: {e}")
        
        # 3. 加载 MEMORY.md
        memory_md = self.memory_dir / "MEMORY.md"
        if memory_md.exists():
            try:
                with open(memory_md, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 提取重要约定
                sections = content.split('\n## ')
                for section in sections[1:]:
                    if len(section) > 50:
                        self.add_memory(
                            content=section[:500],
                            source="memory/MEMORY.md",
                            memory_type="core_memory"
                        )
                        loaded_count += 1
                
                print(f"✅ 已加载 MEMORY.md")
            except Exception as e:
                print(f"⚠️  加载 MEMORY.md 失败: {e}")
        
        print(f"\n📊 共加载 {loaded_count} 条记忆")
        return loaded_count
    
    def recall_for_prompt(self, user_input: str, max_memories: int = 3) -> str:
        """
        为用户输入召回相关记忆，用于增强 prompt
        
        Args:
            user_input: 用户输入内容
            max_memories: 最多召回几条记忆
            
        Returns:
            格式化的记忆上下文
        """
        memories = self.search_memory(user_input, top_k=max_memories, threshold=0.3)
        
        if not memories:
            return ""
        
        context = "\n[相关记忆]\n"
        for i, mem in enumerate(memories, 1):
            context += f"{i}. {mem['content'][:200]}...\n"
            context += f"   来源: {mem['source']}\n"
        
        return context
    
    def extract_from_chat(self, chat_content: str, source: str = "chat") -> List[str]:
        """
        从聊天记录中提取有价值的记忆
        
        Returns:
            提取的记忆ID列表
        """
        memory_ids = []
        
        # 提取问答对
        qa_patterns = [
            r'(?:Q|问|问题)[：:]\s*(.+?)\n+(?:A|答|回答)[：:]\s*(.+?)(?=\n(?:Q|问|问题)[：:]|\Z)',
            r'(?:用户|User)[：:]\s*(.+?)\n+(?:助手|Assistant|AI)[：:]\s*(.+?)(?=\n(?:用户|User)[：:]|\Z)',
        ]
        
        for pattern in qa_patterns:
            for match in re.finditer(pattern, chat_content, re.DOTALL | re.IGNORECASE):
                question = match.group(1).strip()
                answer = match.group(2).strip()
                
                if len(question) > 10 and len(answer) > 20:
                    content = f"Q: {question}\nA: {answer}"
                    mid = self.add_memory(
                        content=content,
                        source=source,
                        memory_type="qa"
                    )
                    memory_ids.append(mid)
        
        # 提取重要约定
        instruction_patterns = [
            r'(?:记住|请记住|记住这个)[：:]\s*(.+?)(?=\n|$)',
            r'(?:以后|下次|以后每次)[：:]\s*(.+?)(?=\n|$)',
            r'(?:重要|注意|提醒)[：:]\s*(.+?)(?=\n|$)',
        ]
        
        for pattern in instruction_patterns:
            for match in re.finditer(pattern, chat_content, re.IGNORECASE):
                content = match.group(1).strip()
                if len(content) > 10:
                    mid = self.add_memory(
                        content=content,
                        source=source,
                        memory_type="instruction"
                    )
                    memory_ids.append(mid)
        
        # 提取技术方案
        solution_pattern = r'(?:方案|解决方案|解决步骤|操作步骤)[：:]\s*\n?(.+?)(?=\n\n|\Z)'
        for match in re.finditer(solution_pattern, chat_content, re.DOTALL | re.IGNORECASE):
            content = match.group(1).strip()
            if len(content) > 50:
                mid = self.add_memory(
                    content=content,
                    source=source,
                    memory_type="solution"
                )
                memory_ids.append(mid)
        
        return memory_ids
    
    def get_stats(self) -> Dict:
        """获取记忆统计信息"""
        return {
            "total_memories": len(self.metadata),
            "sources": list(set(m["source"] for m in self.metadata)),
            "types": {}
        }
    
    def export_memories(self, output_file: str = None) -> str:
        """导出所有记忆为 Markdown"""
        if output_file is None:
            output_file = self.kb_dir / f"memories_export_{datetime.now().strftime('%Y%m%d')}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# OpenClaw 记忆导出\n\n")
            f.write(f"导出时间: {datetime.now().isoformat()}\n")
            f.write(f"记忆总数: {len(self.metadata)}\n\n")
            f.write("---\n\n")
            
            for mem in sorted(self.metadata, key=lambda x: x["created_at"], reverse=True):
                f.write(f"## {mem['id']}\n\n")
                f.write(f"**类型**: {mem['type']}\n\n")
                f.write(f"**来源**: {mem['source']}\n\n")
                f.write(f"**时间**: {mem['created_at']}\n\n")
                f.write(f"**内容**:\n\n{mem['content']}\n\n")
                f.write("---\n\n")
        
        return str(output_file)


# CLI 接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenClaw Memory Enhancer")
    parser.add_argument("--load", action="store_true", help="加载 OpenClaw 记忆文件")
    parser.add_argument("--search", type=str, help="搜索记忆")
    parser.add_argument("--add", type=str, help="添加记忆")
    parser.add_argument("--extract", type=str, help="从文件提取聊天记录")
    parser.add_argument("--export", action="store_true", help="导出所有记忆")
    parser.add_argument("--stats", action="store_true", help="显示统计")
    
    args = parser.parse_args()
    
    enhancer = MemoryEnhancer()
    
    if args.load:
        print("🔄 加载 OpenClaw 记忆文件...")
        count = enhancer.load_openclaw_memory()
        print(f"✅ 完成！共加载 {count} 条记忆")
    
    elif args.search:
        print(f"🔍 搜索: {args.search}")
        results = enhancer.search_memory(args.search)
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['similarity']:.2f}] {r['content'][:100]}...")
            print(f"   来源: {r['source']}")
    
    elif args.add:
        mid = enhancer.add_memory(args.add)
        print(f"✅ 记忆已添加，ID: {mid}")
    
    elif args.extract:
        with open(args.extract, 'r') as f:
            content = f.read()
        ids = enhancer.extract_from_chat(content, source=args.extract)
        print(f"✅ 提取了 {len(ids)} 条记忆")
    
    elif args.export:
        file = enhancer.export_memories()
        print(f"✅ 已导出到: {file}")
    
    elif args.stats:
        stats = enhancer.get_stats()
        print(f"📊 记忆统计:")
        print(f"  总数: {stats['total_memories']}")
        print(f"  来源: {', '.join(stats['sources'])}")
    
    else:
        parser.print_help()
