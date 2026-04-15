#!/usr/bin/env python3
"""
小红书竞品账号分析工具

分析指定账号的：
- 爆款内容特征
- 发布频率和时间
- 内容类型分布
- 互动数据分析
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import Counter
import statistics


class CompetitorAnalyzer:
    def __init__(self):
        self.results = {}
    
    def analyze_posts(self, posts: List[Dict]) -> Dict:
        """
        分析笔记列表
        
        Args:
            posts: 笔记数据列表，每个笔记应包含:
                - title: 标题
                - content: 内容
                - likes: 点赞数
                - comments: 评论数
                - collects: 收藏数
                - publish_time: 发布时间
                - type: 类型(image/video)
                
        Returns:
            分析结果
        """
        if not posts:
            return {"error": "没有笔记数据"}
        
        analysis = {
            "total_posts": len(posts),
            "engagement": self._analyze_engagement(posts),
            "content_types": self._analyze_content_types(posts),
            "publish_pattern": self._analyze_publish_pattern(posts),
            "viral_characteristics": self._analyze_viral_content(posts),
            "recommendations": []
        }
        
        # 生成建议
        analysis["recommendations"] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _analyze_engagement(self, posts: List[Dict]) -> Dict:
        """分析互动数据"""
        likes = [p.get("likes", 0) for p in posts]
        comments = [p.get("comments", 0) for p in posts]
        collects = [p.get("collects", 0) for p in posts]
        
        def stats(arr):
            if not arr:
                return {"avg": 0, "max": 0, "min": 0, "median": 0}
            return {
                "avg": round(statistics.mean(arr), 2),
                "max": max(arr),
                "min": min(arr),
                "median": statistics.median(arr)
            }
        
        return {
            "likes": stats(likes),
            "comments": stats(comments),
            "collects": stats(collects),
            "engagement_rate": round(
                sum(likes) / len(posts) if posts else 0, 2
            )
        }
    
    def _analyze_content_types(self, posts: List[Dict]) -> Dict:
        """分析内容类型分布"""
        types = Counter(p.get("type", "image") for p in posts)
        
        # 分析标题长度
        title_lengths = [len(p.get("title", "")) for p in posts]
        
        # 分析是否有emoji
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F800-\U0001F8FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "]+"
        )
        with_emoji = sum(
            1 for p in posts 
            if emoji_pattern.search(p.get("title", "") + p.get("content", ""))
        )
        
        return {
            "image_vs_video": dict(types),
            "avg_title_length": round(
                statistics.mean(title_lengths) if title_lengths else 0, 1
            ),
            "emoji_usage_rate": round(with_emoji / len(posts) * 100, 1) if posts else 0
        }
    
    def _analyze_publish_pattern(self, posts: List[Dict]) -> Dict:
        """分析发布模式"""
        times = []
        weekdays = []
        
        for p in posts:
            pub_time = p.get("publish_time")
            if pub_time:
                try:
                    if isinstance(pub_time, str):
                        dt = datetime.fromisoformat(pub_time.replace("Z", "+00:00"))
                    elif isinstance(pub_time, (int, float)):
                        dt = datetime.fromtimestamp(pub_time / 1000)
                    else:
                        continue
                    times.append(dt.hour)
                    weekdays.append(dt.weekday())
                except:
                    continue
        
        if not times:
            return {"error": "没有有效的发布时间数据"}
        
        hour_counter = Counter(times)
        weekday_counter = Counter(weekdays)
        
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        return {
            "best_hours": [
                {"hour": h, "count": c} 
                for h, c in hour_counter.most_common(5)
            ],
            "best_weekdays": [
                {"day": weekday_names[w], "count": c}
                for w, c in weekday_counter.most_common(3)
            ],
            "avg_posts_per_day": round(len(posts) / 7, 1)
        }
    
    def _analyze_viral_content(self, posts: List[Dict]) -> Dict:
        """分析爆款内容特征"""
        # 定义爆款：点赞数在前20%
        sorted_posts = sorted(
            posts, 
            key=lambda p: p.get("likes", 0), 
            reverse=True
        )
        top_20_count = max(1, len(posts) // 5)
        viral_posts = sorted_posts[:top_20_count]
        
        # 分析爆款标题特征
        viral_titles = [p.get("title", "") for p in viral_posts]
        
        # 常见关键词
        keywords = []
        for title in viral_titles:
            # 提取2-4字关键词
            keywords.extend(re.findall(r'[\u4e00-\u9fa5]{2,4}', title))
        
        keyword_counter = Counter(keywords)
        
        # 检测数字
        has_numbers = sum(1 for t in viral_titles if re.search(r'\d+', t))
        
        return {
            "viral_threshold_likes": min(
                p.get("likes", 0) for p in viral_posts
            ) if viral_posts else 0,
            "common_keywords": [
                {"keyword": k, "count": c}
                for k, c in keyword_counter.most_common(10)
            ],
            "number_in_title_rate": round(
                has_numbers / len(viral_posts) * 100, 1
            ) if viral_posts else 0,
            "viral_examples": [
                {
                    "title": p.get("title", ""),
                    "likes": p.get("likes", 0)
                }
                for p in viral_posts[:3]
            ]
        }
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 基于互动数据
        engagement = analysis.get("engagement", {})
        if engagement.get("engagement_rate", 0) < 100:
            recommendations.append("建议优化内容质量，当前互动率偏低")
        
        # 基于发布时间
        pattern = analysis.get("publish_pattern", {})
        best_hours = pattern.get("best_hours", [])
        if best_hours:
            recommendations.append(
                f"建议在{best_hours[0]['hour']}点左右发布，该时段表现最佳"
            )
        
        # 基于爆款特征
        viral = analysis.get("viral_characteristics", {})
        if viral.get("number_in_title_rate", 0) > 50:
            recommendations.append("爆款标题常包含数字，建议标题中加入具体数字")
        
        # 基于内容类型
        content_types = analysis.get("content_types", {})
        emoji_rate = content_types.get("emoji_usage_rate", 0)
        if emoji_rate < 60:
            recommendations.append("爆款内容emoji使用率高，建议适当增加emoji")
        
        return recommendations


def main():
    """示例用法"""
    # 示例数据
    sample_posts = [
        {
            "title": "3个超好用的AI工具推荐",
            "content": "今天分享我常用的AI工具...",
            "likes": 5000,
            "comments": 200,
            "collects": 800,
            "publish_time": "2026-03-14T18:00:00Z",
            "type": "image"
        },
        {
            "title": "我的AI学习笔记",
            "content": "学习AI的30天...",
            "likes": 3000,
            "comments": 150,
            "collects": 500,
            "publish_time": "2026-03-13T12:00:00Z",
            "type": "image"
        }
    ]
    
    analyzer = CompetitorAnalyzer()
    result = analyzer.analyze_posts(sample_posts)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
