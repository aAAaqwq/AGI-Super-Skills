/**
 * content-distributor / platforms / wechat.ts
 * 微信公众号发布器 — 官方 API
 *
 * 流程:
 * 1. 获取 access_token
 * 2. 上传封面图到素材库
 * 3. 替换文章内图片为公众号素材 URL
 * 4. 新建草稿 (draft)
 * 5. (可选) 发布草稿
 *
 * 环境变量:
 *   WECHAT_APPID       公众号 AppID
 *   WECHAT_APPSECRET   公众号 AppSecret
 */

import fs from 'fs';
import path from 'path';

const API_BASE = 'https://api.weixin.qq.com/cgi-bin';

export interface WechatConfig {
  appId: string;
  appSecret: string;
}

export interface WechatArticle {
  title: string;
  content: string;           // CSS-内联 HTML
  author?: string;
  digest?: string;           // 摘要
  thumb_media_id?: string;   // 封面图素材 ID
  content_source_url?: string; // 原文链接
  need_open_comment?: 0 | 1;
}

// ─── Access Token ────────────────────────────────────────────────────

let _cachedToken: { token: string; expiresAt: number } | null = null;

export async function getAccessToken(config: WechatConfig): Promise<string> {
  if (_cachedToken && Date.now() < _cachedToken.expiresAt) {
    return _cachedToken.token;
  }

  const url = `${API_BASE}/token?grant_type=client_credential&appid=${config.appId}&secret=${config.appSecret}`;
  const res = await fetch(url);
  const data = await res.json() as any;

  if (data.errcode) {
    throw new Error(`微信 API 错误: ${data.errcode} - ${data.errmsg}`);
  }

  _cachedToken = {
    token: data.access_token,
    expiresAt: Date.now() + (data.expires_in - 300) * 1000, // 提前 5 分钟过期
  };

  return _cachedToken.token;
}

// ─── 素材上传 ────────────────────────────────────────────────────────

export async function uploadImage(config: WechatConfig, imagePath: string): Promise<string> {
  const token = await getAccessToken(config);
  const url = `${API_BASE}/media/uploadimg?access_token=${token}`;

  const formData = new FormData();
  const buffer = fs.readFileSync(imagePath);
  const blob = new Blob([buffer], { type: 'image/png' });
  formData.append('media', blob, path.basename(imagePath));

  const res = await fetch(url, { method: 'POST', body: formData });
  const data = await res.json() as any;

  if (data.errcode) {
    throw new Error(`上传图片失败: ${data.errcode} - ${data.errmsg}`);
  }

  return data.url; // 返回公众号图片 URL (可直接用于文章内)
}

export async function uploadThumb(config: WechatConfig, imagePath: string): Promise<string> {
  const token = await getAccessToken(config);
  const url = `${API_BASE}/material/add_material?access_token=${token}&type=image`;

  const formData = new FormData();
  const buffer = fs.readFileSync(imagePath);
  const blob = new Blob([buffer], { type: 'image/png' });
  formData.append('media', blob, path.basename(imagePath));

  const res = await fetch(url, { method: 'POST', body: formData });
  const data = await res.json() as any;

  if (data.errcode) {
    throw new Error(`上传封面图失败: ${data.errcode} - ${data.errmsg}`);
  }

  return data.media_id;
}

// ─── 文章内图片替换 ──────────────────────────────────────────────────

export async function replaceLocalImages(
  config: WechatConfig,
  htmlContent: string,
  basePath: string
): Promise<string> {
  // 匹配所有 <img src="..."> (本地路径)
  const imgRegex = /<img[^>]+src="([^"]+)"[^>]*>/g;
  let match: RegExpExecArray | null;
  let result = htmlContent;

  while ((match = imgRegex.exec(htmlContent)) !== null) {
    const src = match[1];
    // 跳过已是 http 的图片
    if (src.startsWith('http://') || src.startsWith('https://')) continue;

    const localPath = path.resolve(basePath, src);
    if (fs.existsSync(localPath)) {
      try {
        const wechatUrl = await uploadImage(config, localPath);
        result = result.replace(src, wechatUrl);
        console.log(`  📷 图片上传: ${path.basename(localPath)} → ${wechatUrl.substring(0, 60)}...`);
      } catch (e) {
        console.warn(`  ⚠️ 图片上传失败: ${localPath} — ${e}`);
      }
    }
  }

  return result;
}

// ─── 创建草稿 ────────────────────────────────────────────────────────

export async function createDraft(config: WechatConfig, articles: WechatArticle[]): Promise<string> {
  const token = await getAccessToken(config);
  const url = `${API_BASE}/draft/add?access_token=${token}`;

  const body = {
    articles: articles.map(a => ({
      title: a.title,
      author: a.author || '',
      digest: a.digest || '',
      content: a.content,
      content_source_url: a.content_source_url || '',
      thumb_media_id: a.thumb_media_id || '',
      need_open_comment: a.need_open_comment || 0,
    })),
  };

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await res.json() as any;
  if (data.errcode) {
    throw new Error(`创建草稿失败: ${data.errcode} - ${data.errmsg}`);
  }

  return data.media_id; // 草稿 media_id
}

// ─── 发布草稿 ────────────────────────────────────────────────────────

export async function publishDraft(config: WechatConfig, mediaId: string): Promise<string> {
  const token = await getAccessToken(config);
  const url = `${API_BASE}/freepublish/submit?access_token=${token}`;

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ media_id: mediaId }),
  });

  const data = await res.json() as any;
  if (data.errcode) {
    throw new Error(`发布失败: ${data.errcode} - ${data.errmsg}`);
  }

  return data.publish_id;
}

// ─── 一站式发布 ──────────────────────────────────────────────────────

export async function publishToWechat(
  config: WechatConfig,
  article: WechatArticle,
  opts?: { publish?: boolean; thumbPath?: string; contentBasePath?: string }
): Promise<{ draftId: string; publishId?: string }> {
  console.log('🔑 获取 access_token...');
  await getAccessToken(config);

  // 上传封面图
  if (opts?.thumbPath) {
    console.log('🖼️ 上传封面图...');
    article.thumb_media_id = await uploadThumb(config, opts.thumbPath);
  }

  // 替换文章内本地图片
  if (opts?.contentBasePath) {
    console.log('📷 替换本地图片...');
    article.content = await replaceLocalImages(config, article.content, opts.contentBasePath);
  }

  // 创建草稿
  console.log('📝 创建草稿...');
  const draftId = await createDraft(config, [article]);
  console.log(`✅ 草稿已创建: ${draftId}`);

  // 发布
  if (opts?.publish) {
    console.log('🚀 发布中...');
    const publishId = await publishDraft(config, draftId);
    console.log(`✅ 已发布: ${publishId}`);
    return { draftId, publishId };
  }

  return { draftId };
}
