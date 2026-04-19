#!/bin/bash

# Humanizer 脚本处理抖音AI痕迹消除

echo "=== Humanizer 抖音内容AI痕迹消除处理 ==="

# 三个主题文件
TOPICS=(
    "topic1-script.md:AI视频制作神器"
    "topic1-description.md:AI视频制作描述" 
    "topic2-script.md:AI营销矩阵"
    "topic2-description.md:AI营销描述"
    "topic3-script.md:抖音AI用户增长"
    "topic3-description.md:抖音AI描述"
)

for topic in "${TOPICS[@]}"; do
    input_file="${topic%%:*}"
    topic_name="${topic##*:}"
    
    echo ""
    echo "=== 处理: $topic_name ==="
    
    # 复制到humanizer目录
    cp "/home/aa/.openclaw/workspace-cco/$(date +%Y-%m-%d)/douyin/$input_file" /home/aa/.openclaw/agents/cco/agent/skills/humanizer/input.md
    
    # 运行humanizer处理
    cd /home/aa/.openclaw/agents/cco/agent/skills/humanizer
    ./process.sh
    
    # 复制回原位置
    cp output.md "/home/aa/.openclaw/workspace-cco/$(date +%Y-%m-%d)/douyin/humanized-$input_file"
    
    echo "✅ $topic_name 处理完成"
done

echo ""
echo "=== 所有主题处理完成 ==="
ls -la /home/aa/.openclaw/workspace-cco/$(date +%Y-%m-%d)/douyin/humanized-*.md