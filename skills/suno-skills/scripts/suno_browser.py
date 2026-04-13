#!/usr/bin/env python3
"""
suno_browser.py - Suno 浏览器自动化脚本
用法: python suno_browser.py --lyrics "歌词" --style "风格描述"
"""

import argparse
import asyncio
import sys
import os
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ 请先安装 playwright: pip install playwright && playwright install")
    sys.exit(1)

SUNO_URL = "https://suno.com/create"
OUTPUT_DIR = os.path.expanduser("~/clawd/skills/suno-skills/output")

class SunoBrowser:
    """Suno 浏览器自动化类"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        
    async def __aenter__(self):
        self.p = async_playwright()
        await self.p.__aenter__()
        self.browser = await self.p.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        self.page = await self.context.new_page()
        return self
    
    async def __aexit__(self, *args):
        if self.browser:
            await self.browser.close()
        if self.p:
            await self.p.__aexit__(*args)
    
    async def open_create_page(self):
        """打开创作页面"""
        await self.page.goto(SUNO_URL)
        await self.page.wait_for_load_state("networkidle")
        print("✅ 已打开 Suno 创作页面")
        
    async def enable_custom_mode(self):
        """启用 Custom Mode"""
        try:
            # 尝试点击 Custom Mode 开关
            toggle = self.page.locator('button:has-text("Custom Mode"), label:has-text("Custom Mode")')
            if await toggle.is_visible(timeout=5000):
                await toggle.click()
                print("✅ 已启用 Custom Mode")
                return True
        except Exception:
            pass
        
        try:
            # 备选方案：查找开关
            custom_switch = self.page.locator("[data-testid='custom-mode-toggle']")
            if await custom_switch.is_visible():
                await custom_switch.click()
                print("✅ 已启用 Custom Mode")
                return True
        except Exception:
            pass
        
        print("⚠️ 未找到 Custom Mode 开关，可能已在 Custom Mode 下")
        return False
    
    async def fill_style(self, style_prompt: str):
        """填入风格描述"""
        try:
            # 尝试多个可能的选择器
            selectors = [
                "textarea[name='style']",
                "textarea[placeholder*='style' i]",
                "textarea[placeholder*='描述' i]",
                "div[contenteditable='true']"
            ]
            
            for selector in selectors:
                try:
                    elem = self.page.locator(selector).first
                    if await elem.is_visible(timeout=3000):
                        await elem.fill(style_prompt)
                        print(f"✅ 已填入风格描述 ({len(style_prompt)} 字符)")
                        return True
                except Exception:
                    continue
            
            # 如果找不到，尝试点击并输入
            textareas = self.page.locator("textarea")
            count = await textareas.count()
            if count >= 1:
                await textareas.first.click()
                await textareas.first.fill(style_prompt)
                print(f"✅ 已填入风格描述 ({len(style_prompt)} 字符)")
                return True
                
        except Exception as e:
            print(f"❌ 填入风格描述失败: {e}")
        return False
    
    async def fill_lyrics(self, lyrics: str):
        """填入歌词"""
        if not lyrics:
            print("⚠️ 未提供歌词，跳过")
            return False
            
        try:
            # 尝试查找歌词输入框
            textareas = self.page.locator("textarea")
            count = await textareas.count()
            
            if count >= 2:
                # 第二个 textarea 通常是歌词
                await textareas.nth(1).fill(lyrics)
                print(f"✅ 已填入歌词 ({len(lyrics)} 字符)")
                return True
            elif count == 1:
                # 只有一个时，可能需要通过其他方式
                print("⚠️ 只找到一个 textarea，歌词可能需要手动填入")
                
        except Exception as e:
            print(f"❌ 填入歌词失败: {e}")
        return False
    
    async def click_create(self):
        """点击创建按钮"""
        try:
            create_btn = self.page.locator("button:has-text('Create'), button[type='submit']")
            if await create_btn.is_visible(timeout=5000):
                await create_btn.click()
                print("🎵 正在生成歌曲...")
                return True
        except Exception as e:
            print(f"❌ 点击创建按钮失败: {e}")
        return False
    
    async def wait_for_completion(self, timeout: int = 300) -> dict:
        """等待歌曲生成完成"""
        start_time = asyncio.get_event_loop().time()
        last_status = ""
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            await asyncio.sleep(10)
            
            try:
                # 检查是否有音频元素
                audio_elements = self.page.locator("audio, [data-testid='audio-player']")
                count = await audio_elements.count()
                
                if count > 0:
                    # 获取音频链接
                    audio_src = await audio_elements.first.get_attribute("src")
                    print(f"✅ 歌曲生成完成！音频: {audio_src[:50] if audio_src else 'N/A'}...")
                    return {"status": "complete", "audio_url": audio_src}
                
                # 检查进度状态
                try:
                    status_elem = self.page.locator("text=/生成中|creating|loading/i")
                    if await status_elem.is_visible():
                        last_status = "生成中..."
                    else:
                        progress = self.page.locator("text=/\\d+%/").first
                        if await progress.is_visible():
                            last_status = await progress.text_content()
                except:
                    pass
                    
                print(f"⏳ 等待中... {last_status}")
                
            except Exception as e:
                print(f"⏳ 检查状态中... ({e})")
        
        print("⏰ 生成超时")
        return {"status": "timeout"}
    
    async def get_song_info(self) -> dict:
        """获取生成的歌曲信息"""
        info = {
            "url": self.page.url,
            "title": None,
            "audio_url": None
        }
        
        try:
            # 尝试获取标题
            title_elem = self.page.locator("h1, h2, [data-testid='song-title']").first
            if await title_elem.is_visible():
                info["title"] = await title_elem.text_content()
        except:
            pass
        
        try:
            # 尝试获取音频链接
            audio_elem = self.page.locator("audio").first
            if await audio_elem.is_visible():
                info["audio_url"] = await audio_elem.get_attribute("src")
        except:
            pass
        
        return info


async def main():
    parser = argparse.ArgumentParser(description="Suno 浏览器自动化")
    parser.add_argument("--lyrics", "-l", type=str, default="", help="歌词内容")
    parser.add_argument("--style", "-s", type=str, default="", help="风格描述")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--title", "-t", type=str, default="", help="歌曲标题(可选)")
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 默认风格
    if not args.style:
        args.style = """Mid-tempo R&B pop ballad, emotional Mandarin vocals,
piano-driven, cinematic atmosphere, Jay Chou style melody,
nostalgic mood, rainy day atmosphere"""
    
    print("=" * 50)
    print("🎵 Suno AI 音乐生成器")
    print("=" * 50)
    
    async with SunoBrowser(headless=args.headless) as suno:
        # 1. 打开创作页面
        await suno.open_create_page()
        
        # 2. 启用 Custom Mode
        await suno.enable_custom_mode()
        
        # 3. 填入风格描述
        await suno.fill_style(args.style)
        
        # 4. 填入歌词
        if args.lyrics:
            await suno.fill_lyrics(args.lyrics)
        
        # 5. 点击创建
        await suno.click_create()
        
        # 6. 等待生成
        result = await suno.wait_for_completion(timeout=300)
        
        if result["status"] == "complete":
            # 7. 获取歌曲信息
            info = await suno.get_song_info()
            
            # 保存结果
            output_file = os.path.join(OUTPUT_DIR, f"suno_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "status": "success",
                    "song_info": info,
                    "lyrics": args.lyrics,
                    "style": args.style,
                    "generated_at": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 结果已保存: {output_file}")
            print(f"🎵 歌曲信息: {info}")
        else:
            print("❌ 生成失败或超时")


if __name__ == "__main__":
    asyncio.run(main())
