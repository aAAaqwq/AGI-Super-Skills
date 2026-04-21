# wemp-operator
> 微信公众号全功能运营——草稿/发布/评论/用户/素材/群发/统计/菜单/二维码 API 封装

## 使用场景
- 微信公众号文章草稿管理（创建/编辑/删除/列表）
- 文章发布与发布状态查询
- 粉丝管理（用户信息/标签/拉黑）
- 素材上传（临时/永久/图文内图片）
- 客服消息发送（文字/图片/语音/视频/图文/输入状态）
- 数据统计（用户/图文/阅读/分享/消息）
- 群发消息（按标签/按 OpenID）
- 菜单管理、二维码生成
- 评论管理（精选/回复/删除/开关）
- 模板消息推送

## 使用方法
```bash
# Node.js 模块引用
import { addDraft, publishDraft, getArticleSummary, sendTemplateMessage } from '~/clawd/skills/wemp-operator/scripts/lib/utils.mjs';

# 创建草稿
const { mediaId } = await addDraft([{ title: '标题', content: '<p>HTML内容</p>', thumb_media_id: '...' }]);

// 发布草稿
const { publishId } = await publishDraft(mediaId);

// 获取图文数据
const stats = await getArticleSummary('2026-03-22');
```

## API 覆盖范围
| 模块 | 接口 |
|------|------|
| 草稿 | add/update/get/list/delete/count |
| 发布 | submit/get/batchget/getarticle/delete |
| 评论 | list/reply/delete/markelect/open/close |
| 用户 | info/batchget/getFollowers/remark/blacklist |
| 标签 | create/get/update/delete/tagging/untagging |
| 模板消息 | get_all/add/del/send/industry |
| 素材 | uploadTemp/uploadPermanent/uploadArticleImg/count/list/delete |
| 客服消息 | text/image/voice/video/news/mpnews/typing |
| 菜单 | create/get/delete/getCurrentSelfMenuInfo |
| 二维码 | create/getImageUrl |
| 群发 | sendByTag/sendByOpenIds/preview/getStatus/delete |
| 统计 | getUserSummary/getUserCumulate/getArticleSummary/getArticleTotal/getUserRead/getUserShare/getUpstreamMsg |

## 配置要求
- Node.js 18+
- 微信公众号 appId + appSecret 配置在 `~/.openclaw/openclaw.json` 的 `channels.wemp`
- 自动管理 access_token 缓存

## 相关文件
- `scripts/lib/utils.mjs` — 全功能 API 封装（700+ 行）
- `config/default.json` — 默认运营配置
- `data/` — 数据存储
