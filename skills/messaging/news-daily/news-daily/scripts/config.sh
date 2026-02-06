#!/bin/bash
# News Daily - Configuration File
# This file contains global settings for news fetching and delivery

# Default push channel: telegram or whatsapp
DEFAULT_CHANNEL="telegram"

# Default number of articles to summarize
DEFAULT_ARTICLE_COUNT=5

# Log directory
LOG_DIR="/home/aa/clawd/logs"

# Data cache directory
CACHE_DIR="/home/aa/clawd/skills/news-daily/news-daily/.cache"

# Temp directory for processing
TMP_DIR="/home/aa/clawd/skills/news-daily/news-daily/.tmp"

# Telegram configuration (optional overrides)
# Leave empty to use system defaults
TELEGRAM_CHAT_ID=""

# WhatsApp configuration (optional overrides)
# Leave empty to use system defaults
WHATSAPP_CONTACT_ID=""

# Fetch timeout (seconds)
FETCH_TIMEOUT=30

# User agent for web requests
USER_AGENT="NewsDaily/1.0 (OpenClaw News Aggregator)"

# Maximum retries for failed fetches
MAX_RETRIES=3

# Delay between requests (seconds) - be respectful to servers
REQUEST_DELAY=2

# Date format for output
DATE_FORMAT="+%Y-%m-%d %H:%M:%S"

# Summary language (zh-CN, en-US)
SUMMARY_LANG="zh-CN"

# Keywords for AI/tech relevance filtering (comma-separated)
AI_KEYWORDS="人工智能,AI,机器学习,深度学习,大语言模型,LLM,GPT,Claude,Transformer,神经网络,计算机视觉,NLP,AGI,生成式AI,ChatGPT,OpenAI,Google DeepMind,Anthropic,模型训练,推理优化,芯片,半导体,量子计算,自动驾驶,机器人,智能硬件,算法,数据科学"

# Keywords for frontier tech filtering
TECH_KEYWORDS="科技,创新,创业,融资,上市,科创板,独角兽,前沿技术,新兴技术,元宇宙,Web3,区块链,加密货币,云计算,SaaS,企业服务,数字化转型,物联网,5G,6G,边缘计算,芯片,半导体,新能源,生物技术,基因编辑,脑机接口,AR,VR,MR,可穿戴设备"
