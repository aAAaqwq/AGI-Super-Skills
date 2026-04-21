# trailofbits-skills
> Trail of Bits 安全审计——基于 Trail of Bits 开源工具链的安全审计插件

**状态**: 部分实现 — 有安全审计插件

## 已有模块
- `plugins/constant-time-analysis/` — 常量时间分析
- `plugins/zeroize-audit/` — 零化审计（含 Rust 回归测试 fixtures）

## 配置要求
- Rust 工具链（用于 zeroize-audit）
- uv（Python 包管理，用于 constant-time-analysis）

## 相关文件
- `plugins/constant-time-analysis/` — 常量时间分析插件
- `plugins/zeroize-audit/` — 零化审计插件
