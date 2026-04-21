---
name: minimax-tts
description: Text-to-speech synthesis via MiniMax WebSocket API
---

# MiniMax TTS (WebSocket)

## 触发条件
- "语音合成"、"TTS"、"文字转语音"、"语音生成"、"MiniMax TTS"

## 概述
通过 MiniMax WebSocket API (`wss://api.minimaxi.com/ws/v1/t2a_v2`) 进行语音合成。

## 支持模型
| 模型 | 特性 |
|------|------|
| speech-2.8-hd | 精准还原真实语气细节，全面提升音色相似度 |
| speech-2.6-hd | 超低延时，归一化升级，更高自然度 |
| speech-2.8-turbo | 精准还原真实语气细节，更快更优惠 |
| speech-2.6-turbo | 极速版，适用于语音聊天和数字人 |
| speech-02-hd | 出色韵律、稳定性和复刻相似度 |
| speech-02-turbo | 小语种能力加强 |

## 常用中文音色
| Voice ID | 名称 |
|----------|------|
| female-yujie | 御姐 |
| female-shaonv | 少女 |
| female-shaonv-jingpin | 少女-beta |
| female-tianmei | 甜美女性 |
| qiaopi_mengmei | 俏皮萌妹 |
| wumei_yujie | 妩媚御姐 |
| male-qn-qingse | 青涩青年 |
| male-qn-jingying | 精英青年 |
| Cantonese_CuteGirl | 可爱女孩(粤语) |
| Cantonese_GentleLady | 温柔女声(粤语) |

完整列表: https://platform.minimaxi.com/docs/faq/system-voice-id

## API 密钥
- Key 来源: `openclaw.json` → `env.vars` → `MINIMAX_API_KEY`
- 端点: `wss://api.minimaxi.com/ws/v1/t2a_v2`
- 认证: `Authorization: Bearer {api_key}`

## 使用方法
```python
from tts_ws import synthesize

await synthesize(
    model="speech-2.8-hd",
    voice_id="female-yujie",
    text="你好世界",
    api_key="...",
    output_path="/path/to/output.mp3"
)
```

## 注意事项
- 依赖: `websockets` (pip3 install websockets)
- SSL: 当前跳过证书验证 (ssl.CERT_NONE)
- Clash TUN: `api.minimaxi.com` 已配置 DIRECT 规则，WebSocket 可正常连接
- 单次最长 10,000 字符
- 输出格式: mp3 (32000Hz, 128kbps)
