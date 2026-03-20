# 知识星球配置指南

## 环境变量

```bash
export ZSXQ_ACCESS_TOKEN="your_token_here"
```

## 配置文件方式

创建 `~/.config/zsxq/config.json`:

```json
{
  "access_token": "your_zsxq_access_token",
  "default_group_id": "your_default_group_id"
}
```

## Token获取步骤

1. 打开浏览器，访问 https://wx.zsxq.com
2. 使用微信扫码登录
3. 登录成功后，打开浏览器开发者工具（F12）
4. 进入 Application → Cookies → 选择 zsxq.com 域名
5. 找到 `zsxq_access_token`，复制其值

## Token有效期

- `zsxq_access_token` 有效期较长（通常数天到数周）
- 如果API返回401，需要重新扫码获取新token
- 建议定期检查token有效性

## 获取Group ID

方法1：从URL获取
- 进入星球主页: `https://wx.zsxq.com/group/GROUP_ID`
- URL中的数字部分就是GROUP_ID

方法2：通过API获取
```bash
python3 scripts/publish.py --check-auth
```
会列出所有已加入的星球及其ID。

## 安全注意事项

- 不要将token提交到版本控制
- 不要分享token给他人
- 定期轮换token
- 使用配置文件时确保文件权限: `chmod 600 ~/.config/zsxq/config.json`
