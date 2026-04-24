#!/usr/bin/env python3
"""
小红书发布到草稿箱工具

注意：需要登录态cookie才能使用
使用前需配置cookie到环境变量或配置文件
"""

import os
import json
import requests
from datetime import datetime
from typing import Optional, Dict, List

class XiaohongshuPublisher:
    def __init__(self, cookie: Optional[str] = None):
        self.cookie = cookie or os.getenv("XIAOHONGSHU_COOKIE")
        self.base_url = "https://www.xiaohongshu.com"
        self.api_url = "https://edith.xiaohongshu.com"
        
        if not self.cookie:
            raise ValueError("需要提供小红书cookie，请设置XIAOHONGSHU_COOKIE环境变量")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Cookie": self.cookie,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Origin": "https://www.xiaohongshu.com",
            "Referer": "https://www.xiaohongshu.com/"
        }
    
    def create_draft(
        self,
        title: str,
        content: str,
        images: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        cover_image: Optional[str] = None
    ) -> Dict:
        """
        创建草稿
        
        Args:
            title: 笔记标题
            content: 笔记正文
            images: 图片URL列表（最多9张）
            topics: 话题标签列表
            cover_image: 封面图URL
            
        Returns:
            创建结果
        """
        payload = {
            "note_title": title,
            "note_content": content,
            "images": images or [],
            "topics": topics or [],
            "cover": cover_image,
            "draft": True,
            "post_time": None
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/api/sns/web/v1/note/draft",
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def schedule_publish(
        self,
        draft_id: str,
        publish_time: datetime
    ) -> Dict:
        """
        定时发布
        
        Args:
            draft_id: 草稿ID
            publish_time: 发布时间
            
        Returns:
            定时发布结果
        """
        payload = {
            "draft_id": draft_id,
            "post_time": int(publish_time.timestamp() * 1000)
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/api/sns/web/v1/note/schedule",
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def list_drafts(self, page: int = 1, size: int = 20) -> Dict:
        """
        获取草稿列表
        
        Args:
            page: 页码
            size: 每页数量
            
        Returns:
            草稿列表
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/sns/web/v1/note/drafts",
                headers=self._get_headers(),
                params={"page": page, "size": size},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}


def main():
    """示例用法"""
    # 需要先设置cookie
    # export XIAOHONGSHU_COOKIE="your_cookie_here"
    
    publisher = XiaohongshuPublisher()
    
    # 创建草稿示例
    result = publisher.create_draft(
        title="测试标题 - 3个超好用的AI工具",
        content="""
今天分享3个我常用的AI工具！

1️⃣ ChatGPT - 写作助手
2️⃣ Midjourney - 图片生成
3️⃣ Notion AI - 笔记整理

评论区告诉我你常用的工具是哪个？👇

#AI工具 #效率提升 #干货分享
        """.strip(),
        topics=["AI工具", "效率提升", "干货分享"]
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
