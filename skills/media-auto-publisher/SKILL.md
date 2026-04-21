# media-auto-publisher
> 多平台自动发布——内容一键分发到多个社交媒体平台

## 使用场景
- 将同一内容适配不同平台格式后自动发布
- 平台登录态管理（Cookie 管理）
- 批量发布任务执行

## 使用方法
Agent 通过 `scripts/` 中的模块调用，管理平台导航和登录态。

## 相关文件
- `scripts/platform_navigator.py` — 平台导航与自动化
- `scripts/cookie_manager.py` — 登录态 Cookie 管理
