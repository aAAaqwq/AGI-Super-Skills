# Chrome DevTools MCP 安装脚本
# 老王出品 - 暴躁但靠谱

$settingsPath = "$env:USERPROFILE\.claude\settings.json"
$backupPath = "$env:USERPROFILE\.claude\settings.json.backup"

Write-Host "艹，开始安装Chrome DevTools MCP..." -ForegroundColor Cyan

# 备份原文件
Write-Host "备份原settings.json..." -ForegroundColor Yellow
if (Test-Path $settingsPath) {
    Copy-Item $settingsPath $backupPath -Force
    Write-Host "✓ 备份完成: $backupPath" -ForegroundColor Green
} else {
    Write-Host "警告: 原settings.json不存在！" -ForegroundColor Red
    exit 1
}

# 读取现有配置
Write-Host "读取现有配置..." -ForegroundColor Yellow
$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json

# 添加权限（如果不存在）
if ($settings.permissions.allow -notcontains "mcp__chrome-devtools") {
    Write-Host "添加mcp__chrome-devtools权限..." -ForegroundColor Yellow
    $settings.permissions.allow += "mcp__chrome-devtools"
}

# 添加mcpServers配置
$serverConfig = @{
    "chrome-devtools" = @{
        "command" = "node"
        "args" = @("C:/Users/Administrator/.claude/servers/chrome-devtools-mcp/build/src/index.js")
    }
}

Write-Host "配置MCP服务器..." -ForegroundColor Yellow
$settings | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue $serverConfig -Force

# 写回文件
Write-Host "写入新配置..." -ForegroundColor Yellow
$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8

Write-Host ""
Write-Host "✓✓✓ 安装完成！乖乖，Chrome DevTools MCP已经配置好了！" -ForegroundColor Green
Write-Host ""
Write-Host "接下来要做的事：" -ForegroundColor Cyan
Write-Host "1. 重启Claude Desktop" -ForegroundColor White
Write-Host "2. Chrome DevTools MCP就可以用了" -ForegroundColor White
Write-Host ""
Write-Host "如果遇到问题，备份文件在: $backupPath" -ForegroundColor Yellow
