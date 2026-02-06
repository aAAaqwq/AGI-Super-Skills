#!/usr/bin/env python3
"""
飞书多维表格快捷操作
"""

import sys
import json
from feishu_api import get_client

def list_tables(app_token: str):
    """列出数据表"""
    client = get_client()
    result = client.list_bitable_tables(app_token)
    if result.get("code") == 0:
        tables = result.get("data", {}).get("items", [])
        print(f"找到 {len(tables)} 个数据表:\n")
        for t in tables:
            print(f"  - {t.get('name')}")
            print(f"    ID: {t.get('table_id')}")
            print()
    else:
        print(f"错误: {result}")

def list_records(app_token: str, table_id: str, limit: int = 10):
    """列出记录"""
    client = get_client()
    result = client.get_bitable_records(app_token, table_id, page_size=limit)
    if result.get("code") == 0:
        records = result.get("data", {}).get("items", [])
        print(f"找到 {len(records)} 条记录:\n")
        for r in records:
            print(f"  ID: {r.get('record_id')}")
            print(f"  字段: {json.dumps(r.get('fields', {}), ensure_ascii=False, indent=4)}")
            print()
    else:
        print(f"错误: {result}")

def add_record(app_token: str, table_id: str, fields_json: str):
    """添加记录"""
    client = get_client()
    fields = json.loads(fields_json)
    result = client.add_bitable_record(app_token, table_id, fields)
    if result.get("code") == 0:
        record_id = result.get("data", {}).get("record", {}).get("record_id")
        print(f"✅ 记录已添加: {record_id}")
    else:
        print(f"❌ 添加失败: {result}")

def update_record(app_token: str, table_id: str, record_id: str, fields_json: str):
    """更新记录"""
    client = get_client()
    fields = json.loads(fields_json)
    result = client.update_bitable_record(app_token, table_id, record_id, fields)
    if result.get("code") == 0:
        print(f"✅ 记录已更新")
    else:
        print(f"❌ 更新失败: {result}")

def delete_record(app_token: str, table_id: str, record_id: str):
    """删除记录"""
    client = get_client()
    result = client.delete_bitable_record(app_token, table_id, record_id)
    if result.get("code") == 0:
        print(f"✅ 记录已删除")
    else:
        print(f"❌ 删除失败: {result}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
飞书多维表格操作

用法:
  python bitable.py tables <app_token>                           # 列出数据表
  python bitable.py records <app_token> <table_id> [limit]       # 列出记录
  python bitable.py add <app_token> <table_id> '<fields_json>'   # 添加记录
  python bitable.py update <app_token> <table_id> <record_id> '<fields_json>'  # 更新记录
  python bitable.py delete <app_token> <table_id> <record_id>    # 删除记录

示例:
  python bitable.py tables bascnXXXXXX
  python bitable.py add bascnXXX tblXXX '{"名称": "测试", "状态": "进行中"}'
""")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "tables" and len(sys.argv) >= 3:
        list_tables(sys.argv[2])
    elif cmd == "records" and len(sys.argv) >= 4:
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        list_records(sys.argv[2], sys.argv[3], limit)
    elif cmd == "add" and len(sys.argv) >= 5:
        add_record(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "update" and len(sys.argv) >= 6:
        update_record(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "delete" and len(sys.argv) >= 5:
        delete_record(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(f"参数不足或未知命令: {cmd}")
        sys.exit(1)
