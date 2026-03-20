# 微信公众号 API 接口参考

## 概览

微信公众号提供两类发布方式：

| 方式 | 适用场景 | 限制 |
|------|---------|------|
| **Browser 自动化** | 富文本排版、预览 | 需要扫码登录 |
| **API 直接发布** | 自动化批量发布 | 需要 AppID/AppSecret |

## API 发布流程

```
获取 access_token → 上传素材 → 新建草稿 → 发布草稿
```

## 1. 获取 access_token

**GET** `https://api.weixin.qq.com/cgi-bin/token`

参数：
- `grant_type=client_credential`
- `appid={APP_ID}`
- `secret={APP_SECRET}`

返回：
```json
{
  "access_token": "ACCESS_TOKEN",
  "expires_in": 7200
}
```

## 2. 上传图片素材

### 永久素材（封面图）
**POST** `https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=TOKEN&type=image`

- 图片格式：jpg/png/gif
- 大小：≤10MB
- 返回：`media_id`（用于封面）

### 正文图片
**POST** `https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=TOKEN`

- 图片格式：jpg/png
- 大小：≤10MB
- 返回：图片 URL（可直接插入正文 HTML）

## 3. 新建草稿

**POST** `https://api.weixin.qq.com/cgi-bin/draft/add?access_token=TOKEN`

请求体：
```json
{
  "articles": [{
    "title": "文章标题（≤64字符）",
    "author": "作者",
    "digest": "摘要（≤120字符）",
    "content": "<p>HTML 正文</p>",
    "content_source_url": "",
    "thumb_media_id": "封面图 media_id",
    "need_open_comment": 0,
    "only_fans_can_comment": 0
  }]
}
```

返回：`media_id`（草稿 ID）

## 4. 发布草稿

**POST** `https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token=TOKEN`

请求体：
```json
{
  "media_id": "草稿 media_id"
}
```

返回：`publish_id`

## 5. 定时发布

**POST** `https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token=TOKEN`

请求体：
```json
{
  "media_id": "草稿 media_id",
  "send_publish_date": "2026-03-18T20:00:00+08:00"
}
```

## 限制

| 项目 | 限制 |
|------|------|
| 标题长度 | ≤64 字符 |
| 摘要长度 | ≤120 字符 |
| 服务号发布频率 | 4次/天 |
| 订阅号发布频率 | 1次/天 |
| 图片大小 | ≤10MB |
| access_token 有效期 | 7200秒（2小时） |
| API 调用频率 | 2000次/天 |

## 参考文档

- 草稿箱: https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html
- 发布: https://developers.weixin.qq.com/doc/offiaccount/Publish/Publish.html
- 素材管理: https://developers.weixin.qq.com/doc/offiaccount/Asset_Management/New_temporary_materials.html
