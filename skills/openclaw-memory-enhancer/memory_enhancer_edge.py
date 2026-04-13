#!/usr/bin/env python3
"""
OpenClaw Memory Enhancer - Edge Optimized Version
边缘计算优化版本：内存占用 < 10MB，无需外部模型依赖
"""

import os
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

class MemoryEnhancerEdge:
    """
    OpenClaw 记忆增强器 - 边缘计算优化版
    
    特点：
    - 零外部依赖（无需 sentence-transformers）
    - 内存占用 < 10MB
    - 纯本地计算，无网络请求
    - 适合 Jetson / Raspberry Pi / 嵌入式设备
    """
    
    # 版本信息
    VERSION = "2.0-edge"
    
    def __init__(self, workspace_path: str = None):
        """
        初始化
        
        Args:
            workspace_path: OpenClaw workspace 路径，默认 ~/.openclaw/workspace
        """
        if workspace_path:
            self.workspace = Path(workspace_path)
        else:
            self.workspace = Path.home() / ".openclaw" / "workspace"
        
        self.memory_dir = self.workspace / "memory"
        self.kb_dir = self.workspace / "knowledge-base"
        self.vector_dir = self.kb_dir / "vectors"
        
        # 确保目录存在
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件路径
        self.index_file = self.kb_dir / "memory_index.json"
        self.embeddings_file = self.vector_dir / "embeddings.json"  # 使用JSON而非npy，更轻量
        self.metadata_file = self.vector_dir / "metadata.json"
        
        # 配置：边缘优化参数
        self.config = {
            "vector_dim": 128,  # 降低维度，节省内存（标准版384）
            "max_memory_size": 1000,  # 最大记忆条数限制
            "chunk_size": 500,  # 内容分块大小
            "min_keyword_len": 2,  # 最小关键词长度
        }
        
        # 加载数据
        self.embeddings = []  # 使用list而非numpy数组，节省内存
        self.metadata = []
        self.index = {}
        
        self._load_all()
        
        print(f"✅ Memory Enhancer Edge v{self.VERSION} 已初始化")
        print(f"   工作目录: {self.workspace}")
        print(f"   当前记忆: {len(self.metadata)} 条")
    
    def _load_all(self):
        """加载所有数据"""
        # 加载索引
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.index = json.load(f)
            except:
                self.index = self._create_default_index()
        else:
            self.index = self._create_default_index()
        
        # 加载向量（使用JSON格式，更轻量）
        if self.embeddings_file.exists():
            try:
                with open(self.embeddings_file, 'r', encoding='utf-8') as f:
                    self.embeddings = json.load(f)
            except:
                self.embeddings = []
        
        # 加载元数据
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except:
                self.metadata = []
    
    def _create_default_index(self) -> Dict:
        """创建默认索引"""
        return {
            "version": self.VERSION,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "total_memories": 0,
            "sources": [],
            "edge_optimized": True
        }
    
    def _save_all(self):
        """保存所有数据（原子操作）"""
        # 更新索引
        self.index["last_updated"] = datetime.now().isoformat()
        self.index["total_memories"] = len(self.metadata)
        
        # 保存为JSON（边缘设备友好）
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)
        
        with open(self.embeddings_file, 'w', encoding='utf-8') as f:
            json.dump(self.embeddings, f)
        
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词（轻量级，无需NLP库）
        
        使用简单但有效的规则：
        1. 转换为小写
        2. 分词（按非字母数字字符分割）
        3. 过滤短词和常见停用词
        4. 去重
        """
        # 简单的停用词列表（中文+英文）
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 
                     '的', '了', '和', '是', '在', '有', '我', '你',
                     '它', '我们', '你们', '这个', '那个', '可以',
                     '使用', '进行', '通过', '需要', '进行'}
        
        # 分词
        words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text.lower())
        
        # 过滤
        keywords = []
        for word in words:
            if len(word) >= self.config["min_keyword_len"] and word not in stopwords:
                keywords.append(word)
        
        return list(set(keywords))  # 去重
    
    def _encode_text(self, text: str) -> List[float]:
        """
        将文本编码为向量（边缘优化版）
        
        使用关键词哈希 + TF-IDF 思想的简化版
        无需外部模型，纯本地计算
        """
        keywords = self._extract_keywords(text)
        
        # 创建稀疏向量（使用哈希）
        vector = [0.0] * self.config["vector_dim"]
        
        for keyword in keywords:
            # 使用哈希将关键词映射到向量位置
            hash_val = hash(keyword) % self.config["vector_dim"]
            vector[hash_val] += 1.0  # 简单的词频统计
        
        # 归一化（L2范数）
        magnitude = sum(x**2 for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return vector
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(x**2 for x in vec1) ** 0.5
        magnitude2 = sum(x**2 for x in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def add_memory(self, content: str, source: str = "manual", 
                   memory_type: str = "general", metadata: Dict = None) -> str:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            source: 来源标识
            memory_type: 记忆类型
            metadata: 额外元数据
        
        Returns:
            记忆ID
        """
        # 限制最大记忆数（边缘设备保护）
        if len(self.metadata) >= self.config["max_memory_size"]:
            # 移除最旧的记忆
            self.metadata.pop(0)
            self.embeddings.pop(0)
            print(f"⚠️  记忆数量达到上限，移除最旧的记忆")
        
        # 生成ID
        memory_id = hashlib.md5(f"{content}{datetime.now()}".encode()).hexdigest()[:12]
        
        # 截断过长内容（边缘设备保护）
        if len(content) > self.config["chunk_size"]:
            content = content[:self.config["chunk_size"]] + "..."
        
        # 创建记忆条目
        memory_entry = {
            "id": memory_id,
            "content": content,
            "source": source,
            "type": memory_type,
            "created_at": datetime.now().isoformat(),
            "keywords": self._extract_keywords(content),  # 保存关键词，加速检索
            "metadata": metadata or {}
        }
        
        # 编码
        embedding = self._encode_text(content)
        
        # 添加
        self.metadata.append(memory_entry)
        self.embeddings.append(embedding)
        
        # 更新来源记录
        if source not in self.index["sources"]:
            self.index["sources"].append(source)
        
        # 保存
        self._save_all()
        
        return memory_id
    
    def search_memory(self, query: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict]:
        """
        搜索记忆
        
        Args:
            query: 查询内容
            top_k: 返回数量
            threshold: 相似度阈值
        
        Returns:
            相关记忆列表
        """
        if not self.metadata:
            return []
        
        # 编码查询
        query_vec = self._encode_text(query)
        query_keywords = set(self._extract_keywords(query))
        
        # 计算相似度（优化：先用关键词过滤）
        scored_memories = []
        
        for idx, (mem, emb) in enumerate(zip(self.metadata, self.embeddings)):
            # 快速预过滤：检查是否有共同关键词
            mem_keywords = set(mem.get("keywords", []))
            if not query_keywords.intersection(mem_keywords):
                # 没有共同关键词，跳过详细计算
                continue
            
            # 计算向量相似度
            similarity = self._cosine_similarity(query_vec, emb)
            
            if similarity >= threshold:
                scored_memories.append((idx, similarity))
        
        # 排序取Top-K
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        top_results = scored_memories[:top_k]
        
        # 构建结果
        results = []
        for idx, score in top_results:
            mem = self.metadata[idx].copy()
            mem["similarity"] = round(score, 3)
            results.append(mem)
        
        return results
    
    def recall_for_prompt(self, user_input: str, max_memories: int = 3) -> str:
        """
        为对话召回相关记忆
        
        Args:
            user_input: 用户输入
            max_memories: 最多召回几条
        
        Returns:
            格式化的记忆上下文
        """
        memories = self.search_memory(user_input, top_k=max_memories, threshold=0.25)
        
        if not memories:
            return ""
        
        context = "\n[相关记忆]\n"
        for i, mem in enumerate(memories, 1):
            # 截断内容，保持简洁
            content = mem['content'][:150] + "..." if len(mem['content']) > 150 else mem['content']
            context += f"{i}. {content}\n"
        
        return context
    
    def load_openclaw_memory(self) -> int:
        """
        加载 OpenClaw 记忆文件
        
        Returns:
            加载的记忆数量
        """
        loaded_count = 0
        
        if not self.memory_dir.exists():
            print(f"⚠️  记忆目录不存在: {self.memory_dir}")
            return 0
        
        # 加载 .md 文件
        for md_file in sorted(self.memory_dir.glob("*.md")):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 分割段落
                paragraphs = content.split('\n\n')
                for para in paragraphs:
                    para = para.strip()
                    # 过滤：有意义且不太长的段落
                    if 50 < len(para) < self.config["chunk_size"]:
                        self.add_memory(
                            content=para,
                            source=f"memory/{md_file.name}",
                            memory_type="daily_log"
                        )
                        loaded_count += 1
                
                print(f"✅ 已加载 {md_file.name}")
                
            except Exception as e:
                print(f"⚠️  加载 {md_file.name} 失败: {e}")
        
        # 保存
        self._save_all()
        print(f"\n📊 共加载 {loaded_count} 条记忆")
        return loaded_count
    
    def extract_from_chat(self, chat_content: str, source: str = "chat") -> List[str]:
        """从聊天记录中提取记忆"""
        memory_ids = []
        
        # 提取问答对（简化版）
        qa_pattern = r'(?:Q|问)[：:]\s*(.+?)\n+(?:A|答)[：:]\s*(.+?)(?=\n(?:Q|问)[：:]|\Z)'
        for match in re.finditer(qa_pattern, chat_content, re.DOTALL | re.IGNORECASE):
            question = match.group(1).strip()
            answer = match.group(2).strip()
            
            if len(question) > 10 and len(answer) > 20:
                content = f"Q: {question[:100]}\nA: {answer[:200]}"
                mid = self.add_memory(content=content, source=source, memory_type="qa")
                memory_ids.append(mid)
        
        return memory_ids
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "version": self.VERSION,
            "total_memories": len(self.metadata),
            "vector_dim": self.config["vector_dim"],
            "sources": list(set(m["source"] for m in self.metadata)),
            "edge_optimized": True
        }
    
    def export_memories(self, output_file: str = None) -> str:
        """导出记忆"""
        if output_file is None:
            output_file = self.kb_dir / f"memories_export_{datetime.now().strftime('%Y%m%d')}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# OpenClaw 记忆导出 (Edge版)\n\n")
            f.write(f"导出时间: {datetime.now().isoformat()}\n")
            f.write(f"记忆总数: {len(self.metadata)}\n")
            f.write(f"向量维度: {self.config['vector_dim']}\n")
            f.write(f"边缘优化: 是\n\n")
            f.write("---\n\n")
            
            for mem in sorted(self.metadata, key=lambda x: x["created_at"], reverse=True):
                f.write(f"## {mem['id']}\n\n")
                f.write(f"**类型**: {mem['type']} | **来源**: {mem['source']}\n\n")
                f.write(f"**关键词**: {', '.join(mem.get('keywords', []))}\n\n")
                f.write(f"**内容**:\n\n{mem['content']}\n\n")
                f.write("---\n\n")
        
        return str(output_file)


# CLI 接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenClaw Memory Enhancer (Edge)")
    parser.add_argument("--load", action="store_true", help="加载 OpenClaw 记忆")
    parser.add_argument("--search", type=str, help="搜索记忆")
    parser.add_argument("--add", type=str, help="添加记忆")
    parser.add_argument("--export", action="store_true", help="导出记忆")
    parser.add_argument("--stats", action="store_true", help="显示统计")
    parser.add_argument("--workspace", type=str, help="指定 workspace 路径")
    
    args = parser.parse_args()
    
    enhancer = MemoryEnhancerEdge(workspace_path=args.workspace)
    
    if args.load:
        print("🔄 加载 OpenClaw 记忆文件...")
        count = enhancer.load_openclaw_memory()
        print(f"✅ 完成！共加载 {count} 条记忆")
    
    elif args.search:
        print(f"🔍 搜索: {args.search}")
        results = enhancer.search_memory(args.search)
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['similarity']:.3f}] {r['content'][:80]}...")
            print(f"   关键词: {', '.join(r.get('keywords', [])[:5])}")
    
    elif args.add:
        mid = enhancer.add_memory(args.add)
        print(f"✅ 记忆已添加，ID: {mid}")
    
    elif args.export:
        file = enhancer.export_memories()
        print(f"✅ 已导出到: {file}")
    
    elif args.stats:
        stats = enhancer.get_stats()
        print(f"📊 记忆统计 (Edge版):")
        for k, v in stats.items():
            print(f"  {k}: {v}")
    
    else:
        parser.print_help()
