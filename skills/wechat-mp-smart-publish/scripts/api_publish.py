#!/usr/bin/env python3
"""
微信公众号 API 发布脚本

通过微信官方 API 直接发布文章（无需浏览器）

前置条件:
1. 已获取 access_token（需要 AppID + AppSecret）
2. 图片已上传为永久素材（获得 media_id）

API 流程:
1. 获取 access_token
2. 上传图片素材（如需新封面）
3. 新建草稿
4. 发布草稿

使用方法:
  export WECHAT_APP_ID="your_app_id"
  export WECHAT_APP_SECRET="your_app_secret"
  python3 api_publish.py --title "标题" --content content.html --cover media_id
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path


# API 端点
BASE_URL = "https://api.weixin.qq.com/cgi-bin"
TOKEN_URL = f"{BASE_URL}/token"
UPLOAD_URL = f"{BASE_URL}/material/add_material"
DRAFT_URL = f"{BASE_URL}/draft/add"
PUBLISH_URL = f"{BASE_URL}/freepublish/submit"
MEDIA_UPLOAD_URL = f"{BASE_URL}/media/uploadimg"

# 配置
CONFIG_FILE = os.path.expanduser("~/.openclaw/skills/wechat-mp-smart-publish/wechat_config.json")


class WeChatMPApi:
    """微信公众号 API 封装"""

    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id or os.environ.get("WECHAT_APP_ID")
        self.app_secret = app_secret or os.environ.get("WECHAT_APP_SECRET")

        if not self.app_id or not self.app_secret:
            # 尝试从配置文件加载
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    cfg = json.load(f)
                    self.app_id = self.app_id or cfg.get("app_id")
                    self.app_secret = self.app_secret or cfg.get("app_secret")

        if not self.app_id or not self.app_secret:
            raise ValueError("需要提供 WECHAT_APP_ID 和 WECHAT_APP_SECRET")

        self._token = None
        self._token_expires = 0

    @property
    def access_token(self):
        """获取 access_token（自动缓存）"""
        if self._token and time.time() < self._token_expires:
            return self._token

        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }
        resp = requests.get(TOKEN_URL, params=params, timeout=10)
        data = resp.json()

        if "access_token" not in data:
            raise Exception(f"获取 token 失败: {data}")

        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200) - 300  # 提前5分钟过期
        print(f"🔑 Access Token: {self._token[:16]}...")
        return self._token

    def upload_image(self, image_path, permanent=True):
        """
        上传图片素材
        permanent=True: 永久素材（用于封面）
        permanent=False: 临时素材（用于正文图片）
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片不存在: {image_path}")

        url = f"{UPLOAD_URL}?access_token={self.access_token}&type=image" if permanent \
            else f"{MEDIA_UPLOAD_URL}?access_token={self.access_token}"

        with open(image_path, 'rb') as f:
            files = {'media': (os.path.basename(image_path), f)}
            resp = requests.post(url, files=files, timeout=30)

        data = resp.json()
        if "media_id" in data:
            print(f"✅ 图片上传成功: media_id={data['media_id']}")
            return data["media_id"], data.get("url")
        else:
            raise Exception(f"图片上传失败: {data}")

    def create_draft(self, title, content, author="", digest="", cover_media_id="", thumb_media_id="",
                     content_source_url="", need_open_comment=0, only_fans_can_comment=0):
        """
        新建草稿

        参考: https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html
        """
        articles = [{
            "title": title[:64],  # ≤64字符
            "author": author,
            "digest": digest[:120] if digest else "",  # ≤120字符
            "content": content,  # HTML 正文
            "content_source_url": content_source_url,
            "thumb_media_id": thumb_media_id or cover_media_id,  # 封面图 media_id（必需）
            "need_open_comment": need_open_comment,
            "only_fans_can_comment": only_fans_can_comment,
        }]

        payload = {"articles": articles}

        resp = requests.post(
            f"{DRAFT_URL}?access_token={self.access_token}",
            json=payload,
            timeout=30
        )

        data = resp.json()
        if "media_id" in data:
            print(f"✅ 草稿创建成功: media_id={data['media_id']}")
            return data["media_id"]
        else:
            raise Exception(f"草稿创建失败: {data}")

    def publish(self, media_id):
        """
        发布草稿

        参考: https://developers.weixin.qq.com/doc/offiaccount/Publish/Publish.html
        """
        payload = {"media_id": media_id}

        resp = requests.post(
            f"{PUBLISH_URL}?access_token={self.access_token}",
            json=payload,
            timeout=30
        )

        data = resp.json()
        if data.get("errcode") == 0:
            publish_id = data.get("publish_id")
            print(f"✅ 发布成功！publish_id={publish_id}")
            return publish_id
        else:
            raise Exception(f"发布失败: {data}")

    def publish_article(self, title, content, **kwargs):
        """一键发布：上传封面 → 创建草稿 → 发布"""

        # 1. 上传封面
        cover_path = kwargs.get("cover_path")
        cover_media_id = kwargs.get("cover_media_id")

        if cover_path and not cover_media_id:
            print("📤 上传封面图...")
            cover_media_id, cover_url = self.upload_image(cover_path, permanent=True)
        elif not cover_media_id:
            raise ValueError("需要提供 cover_path 或 cover_media_id")

        # 2. 创建草稿
        print("📝 创建草稿...")
        draft_media_id = self.create_draft(
            title=title,
            content=content,
            author=kwargs.get("author", ""),
            digest=kwargs.get("digest", ""),
            cover_media_id=cover_media_id,
            content_source_url=kwargs.get("source_url", ""),
        )

        # 3. 发布（如果不是草稿模式）
        if kwargs.get("is_draft", True):
            print(f"📄 草稿已保存: {draft_media_id}")
            return draft_media_id
        else:
            print("🚀 发布文章...")
            return self.publish(draft_media_id)


def main():
    parser = argparse.ArgumentParser(description="微信公众号 API 发布")
    parser.add_argument("--title", help="文章标题（≤64字符）", required=True)
    parser.add_argument("--content", help="正文 HTML 文件路径", required=True)
    parser.add_argument("--cover", help="封面图路径（900×500px）")
    parser.add_argument("--cover-id", help="已上传的封面图 media_id")
    parser.add_argument("--author", help="作者名")
    parser.add_argument("--digest", help="摘要（≤120字符）")
    parser.add_argument("--source-url", help="原文链接")
    parser.add_argument("--publish", action="store_true", help="直接发布（默认保存草稿）")
    parser.add_argument("--config", help="JSON 配置文件路径（替代命令行参数）")

    args = parser.parse_args()

    try:
        api = WeChatMPApi()

        with open(args.content, 'r', encoding='utf-8') as f:
            content_html = f.read()

        result = api.publish_article(
            title=args.title,
            content=content_html,
            cover_path=args.cover,
            cover_media_id=args.cover_id,
            author=args.author or "",
            digest=args.digest or "",
            source_url=args.source_url or "",
            is_draft=not args.publish,
        )

        print(f"\n🎉 完成！media_id: {result}")

    except Exception as e:
        print(f"\n❌ 失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
