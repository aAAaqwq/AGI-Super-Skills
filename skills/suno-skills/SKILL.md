---
name: suno-skills
description: AI音乐生成工具Suno的浏览器自动化Skill。通过Playwright控制Suno网站(https://suno.com)进行：生成歌曲(含自定义歌词)、管理创作、下载音频。触发场景："用suno生成歌曲"、"Suno创作"、"AI音乐生成"、"生成一首...风格的歌"、"上传歌词到Suno"
---

# Suno Skills

通过真实浏览器自动化控制 Suno (https://suno.com) 进行 AI 音乐生成。

## 前置要求

- Suno 账号（支持 Google 登录）
- 浏览器已安装 Playwright

## 工作流程

### 1. 打开 Suno 并登录

```python
browser.open("https://suno.com")
```

### 2. 生成歌曲（Custom Mode + 自定义歌词）

在 Suno 的 Custom Mode 页面：
- **Style Prompt**: 风格描述（不含歌词）
- **Lyrics**: 歌词内容（可填入已有歌词）

### 3. 核心操作

| 操作 | 执行方式 |
|------|----------|
| 打开创作页面 | `browser.open("https://suno.com/create")` |
| 填入风格描述 | 输入框 ref 查找 |
| 填入歌词 | 歌词输入框 ref 查找 |
| 点击生成 | "Create" 按钮 |
| 等待生成完成 | 轮询检查状态 |
| 获取音频链接 | 解析返回结果 |

## Suno Custom Mode Prompt 模板

### G.E.M. 邓紫棋 风格

**Style Prompt:**
```
G.E.M. style, powerful belting vocals, husky tones, R&B pop, 
wide vocal range, emotional delivery, Cantonese/Mandarin singing,
breathy chorus, soulful ballads, 2000s-2020s C-pop diva energy
```

### 中文 R&B 抒情

**Style Prompt:**
```
Mid-tempo R&B pop ballad, emotional Mandarin vocals,
piano-driven, cinematic atmosphere, Jay Chou style melody,
nostalgic mood, rainy day atmosphere
```

### 完整 Custom Mode 输入模板

```
[Verse]
(歌词内容)

[Chorus]
(副歌内容)

[Bridge]
(桥段)

[Outro]
(结尾)
---
Style: (风格描述)
Tempo: (BPM)
Mood: (情绪氛围)
```

## 《那天下雨了》完整歌词 (Suno 格式)

```plain text
[Intro]
車子緩緩的開 你慢慢走來 我竟然看著你發呆

[Verse 1]
你尷尬Say個Hi 沒位坐下來
我想叫旁邊的離開
我車票都還在 心卻在窗外
因為你已下了站台
遠遠的看著你點點頭車已開
你一句話我爬窗離開

[Verse 2]
你證件掉了出來 我才明白
是那隔壁班的女孩
這麼多年彼此竟然沒認出來
是你變美還是我變帥

[Chorus]
你經過花就開 離開雨就來
這裡適合談個戀愛
如果我要一個夢幻的開場白
沒有比你更美的對白

[Bridge]
雪白的天空等待彩虹出現
你我的遇見是誰許的願
黑黑的夜空繁星變得耀眼
因為你出現在我身邊

[Verse 3]
你老家有點遠 但我有點閒
也許能陪你走一圈
把你的父母都見 吃幾口麻醬麵
也許還能打個幾圈

[Verse 4]
鄉間的麥芽田 害羞的臉
你提到多年前的暗戀
你剪下校園畢業冊的那一頁
是因為我在照片裡面

[Chorus]
雪白的天空等待彩虹出現
你我的遇見是誰許的願
黑黑的夜空繁星變得耀眼
因為你出現在我身邊

[Verse 5]
原來多年前在那個書店
借我課本的是你
原來看我被雨淋的那天
幫我撐傘也是你

[Bridge]
翹課的那一天 花落那一天
教室那間我已看見
消失的下雨天 我想再淋一遍
我應該對你唱著晴天

[Outro]
送你到家門外 我才明白
原來你早已有人疼愛
如果回到過去那一個下雨天
我會為了你把傘撐開
如果回到過去那一個下雨天
我絕不再 轉身離開

---
Style: Mid-tempo R&B pop ballad, nostalgic rainy day atmosphere, emotional Mandarin vocals, piano and strings arrangement, Jay Chou style melody, romantic and bittersweet mood
Tempo: 75 BPM
Mood: Nostalgic, emotional, romantic, bittersweet
```

## 浏览器自动化脚本模板

```python
#!/usr/bin/env python3
"""suno_create.py - 通过浏览器自动化在 Suno 生成歌曲"""

import asyncio
import sys
sys.path.insert(0, '/home/aa/clawd/skills/suno-skills/scripts')

from playwright.async_api import async_playwright

SUNO_URL = "https://suno.com/create"

async def create_song(style_prompt: str, lyrics: str = ""):
    """生成歌曲"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 打开创作页面
        await page.goto(SUNO_URL)
        await page.wait_for_load_state("networkidle")
        
        # 查找 Custom Mode 开关并开启
        custom_mode_toggle = page.locator("text=Custom Mode")
        if await custom_mode_toggle.is_visible():
            await custom_mode_toggle.click()
        
        # 填入 Style Prompt
        style_input = page.locator("textarea").first
        await style_input.fill(style_prompt)
        
        # 如果有歌词，填入歌词框
        if lyrics:
            # 查找歌词输入框（通常在 Style 下方）
            lyrics_input = page.locator("textarea").nth(1)
            await lyrics_input.fill(lyrics)
        
        # 点击 Create 按钮
        create_btn = page.locator("button:has-text('Create')")
        await create_btn.click()
        
        # 等待生成完成（轮询）
        for _ in range(60):  # 最多等待60次
            await asyncio.sleep(10)
            # 检查是否生成完成
            status = await page.locator(".audio-container").count()
            if status > 0:
                print("✅ 歌曲生成完成！")
                break
        
        await browser.close()

if __name__ == "__main__":
    # 示例：G.E.M. 风格《那天下雨了》
    style = "G.E.M. style, powerful belting vocals, R&B pop, emotional Mandarin singing"
    lyrics = """(歌词内容)"""
    asyncio.run(create_song(style, lyrics))
```

## 输出产物

| 类型 | 说明 |
|------|------|
| 音频文件 | MP3/WAV 格式 |
| 封面图 | 自动生成 |
| 歌曲链接 | Suno 站内 URL |

## 注意事项

1. **免费额度**: 每天 5 次生成，Pro 订阅更多
2. **版权提示**: 生成的歌曲版权归 Suno 用户所有
3. **歌词长度**: 建议不超过 500 字
4. **生成时间**: 通常 1-3 分钟
