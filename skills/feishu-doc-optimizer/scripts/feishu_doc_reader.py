#!/usr/bin/env python3
"""
飞书文档读取器
读取飞书云文档的原始内容
"""

import sys
import requests
import json

# 租户配置 - 密钥从环境变量获取，切勿硬编码！
# 使用: export FEISHU_APP_SECRET_HANXING=xxx FEISHU_APP_SECRET_PERSONAL=xxx
TENANTS = {
    "hanxing": {
        "app_id": os.environ.get("FEISHU_APP_ID_HANXING", "REDACTED_FEISHU_HANXING_APP_ID"),
        "app_secret": os.environ.get("FEISHU_APP_SECRET_HANXING", ""),
    },
    "personal": {
        "app_id": os.environ.get("FEISHU_APP_ID_PERSONAL", "REDACTED_FEISHU_PERSONAL_APP_ID"),
        "app_secret": os.environ.get("FEISHU_APP_SECRET_PERSONAL", ""),
    }
}

# 尝试从 pass 加载密钥
def _load_secrets():
    try:
        import subprocess
        for tenant, pass_path in [("hanxing", "api/feishu-hanxing"), ("personal", "api/feishu-personal")]:
            result = subprocess.run(["pass", "show", pass_path], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if 'secret' in line.lower():
                        TENANTS[tenant]["app_secret"] = line.split('=')[-1].strip() if '=' in line else line.strip()
                        break
    except Exception:
        pass

_load_secrets()

def get_token(tenant="hanxing"):
    """获取 tenant_access_token"""
    config = TENANTS.get(tenant, TENANTS["hanxing"])
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": config["app_id"], "app_secret": config["app_secret"]},
        timeout=10
    )
    return resp.json().get("tenant_access_token")

def read_document(doc_token, tenant="hanxing"):
    """读取文档原始内容"""
    token = get_token(tenant)
    headers = {"Authorization": f"Bearer {token}"}
    
    # 获取原始内容
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/raw_content",
        headers=headers,
        timeout=30
    )
    result = resp.json()
    
    if result.get('code') == 0:
        return result.get('data', {}).get('content', '')
    else:
        print(f"错误: {result.get('msg')}", file=sys.stderr)
        return None

def get_document_info(doc_token, tenant="hanxing"):
    """获取文档基本信息"""
    token = get_token(tenant)
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}",
        headers=headers,
        timeout=30
    )
    result = resp.json()
    
    if result.get('code') == 0:
        doc = result.get('data', {}).get('document', {})
        return {
            "title": doc.get('title'),
            "document_id": doc.get('document_id'),
            "revision_id": doc.get('revision_id')
        }
    return None

def main():
    if len(sys.argv) < 2:
        print("用法: python feishu_doc_reader.py <doc_token> [tenant]")
        print("示例: python feishu_doc_reader.py JM3WdqG2bolLsNxlVnJcTdMjnce hanxing")
        sys.exit(1)
    
    doc_token = sys.argv[1]
    tenant = sys.argv[2] if len(sys.argv) > 2 else "hanxing"
    
    # 获取文档信息
    info = get_document_info(doc_token, tenant)
    if info:
        print(f"📄 文档标题: {info['title']}")
        print(f"📝 文档ID: {info['document_id']}")
        print(f"🔄 版本: {info['revision_id']}")
        print("=" * 50)
    
    # 读取内容
    content = read_document(doc_token, tenant)
    if content:
        print(content)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
