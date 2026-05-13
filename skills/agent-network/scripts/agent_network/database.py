#!/usr/bin/env python3
"""
Agent 群聊协作系统 - 数据库管理模块
负责数据库连接、初始化和基本操作
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str = "data/agent_network.db"):
        self.db_path = db_path
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """初始化数据库，执行 schema.sql"""
        # Try multiple possible locations for schema.sql
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', 'references', 'schema.sql'),  # Skill structure
            os.path.join(os.path.dirname(__file__), '..', 'schema.sql'),  # Local dev
            os.path.join(os.path.dirname(__file__), '..', '..', 'schema.sql'),  # Alternate
        ]
        
        schema_path = None
        for path in possible_paths:
            if os.path.exists(path):
                schema_path = path
                break
        
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = f.read()
            
            with self.get_connection() as conn:
                conn.executescript(schema)
        else:
            print(f"警告: 未找到 schema.sql 文件: {schema_path}")
    
    def execute(self, query: str, params: tuple = ()) -> int:
        """执行 SQL 语句，返回影响的行数"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """批量执行 SQL 语句"""
        with self.get_connection() as conn:
            cursor = conn.executemany(query, params_list)
            return cursor.rowcount
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """查询单条记录"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """查询多条记录"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def insert(self, query: str, params: tuple = ()) -> int:
        """插入记录，返回自增ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid


# 全局数据库实例
db = Database()
