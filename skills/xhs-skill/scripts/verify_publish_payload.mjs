#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { getImageSize } from '../lib/image.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DEFAULT_POLICY_PATH = path.resolve(__dirname, '../config/verify_publish_policy.json');

function usage() {
  return `verify_publish_payload

Usage:
  node ./scripts/verify_publish_payload.mjs --in <payloadJsonPath> [--mode hot] [--json]
  node ./scripts/verify_publish_payload.mjs --in <payloadJsonPath> [--tag-registry ./data/tag_registry.json]
  node ./scripts/verify_publish_payload.mjs --in <payloadJsonPath> [--policy ./skills/xhs-skill/config/verify_publish_policy.json]

Payload JSON example:
{
  "topic": "今日热点：......",
  "source": {
    "name": "央视新闻",
    "url": "https://...",
    "date": "2026-02-12",
    "evidence_snippet": "2月12日该媒体报道：......",
    "key_facts": ["融资规模约300亿美元", "时间点为2026年2月12日"]
  },
  "post": {
    "title": "标题",
    "body": "正文",
    "tags": ["#热点", "#小红书"],
    "real_topics": ["#人工智能", "#AI热点", "#科技新闻"],
    "media": ["/abs/path/cover.png"]
  }
}
`;
}

const DEFAULT_POLICY = {
  topic: {
    min_len: 4,
  },
  post: {
    title_min_len: 8,
    title_max_len: 20,
    body_min_len: 80,
  },
  tags: {
    min_count: 3,
    max_count: 8,
    placeholder_patterns: [
      '^#?(标签|话题|测试|示例|模板)$',
      '^#?(test|tag|demo|sample|xxx)$',
    ],
  },
  real_topics: {
    min_count: 3,
    max_count: 8,
    placeholder_patterns: [
      '^#?(标签|话题|测试|示例|模板)$',
      '^#?(test|tag|demo|sample|xxx)$',
    ],
  },
  tag_registry: {
    fresh_within_days: 7,
    required_platform: 'xiaohongshu',
  },
  source: {
    evidence_snippet_min_len: 16,
    evidence_snippet_max_len: 180,
    key_facts_min_count: 2,
    key_facts_max_count: 5,
    key_fact_min_len: 8,
    key_fact_max_len: 80,
  },
  media: {
    min_count: 1,
    screenshot_keywords: ['screenshot', 'screen_shot', 'xhs_login', 'login_qr', 'after_click'],
    ratio_target: 3 / 4,
    ratio_tolerance: 0.02,
    preferred_sizes: [{ width: 1242, height: 1660 }],
    max_detail_items: 12,
  },
  anti_ai: {
    template_phrases: [
      '总的来说',
      '综上所述',
      '不难看出',
      '值得注意的是',
      '随着人工智能的发展',
      '随着ai的发展',
      '未来可期',
      '首先',
      '其次',
      '最后',
    ],
    personal_voice_keywords: ['我', '我们', '我觉得', '我观察', '我测了', '我试了', '我踩坑', '我自己', '这周我'],
    week_keywords: ['这周', '本周', '今天', '昨日', '刚刚'],
    strict_min_digit_count: 2,
    strict_min_signal_count: 2,
  },
  link_detection: {
    blocked_tlds: ['com', 'cn', 'net', 'org', 'io', 'me', 'co', 'app', 'dev'],
  },
  hot_mode: {
    source_date_must_be_today: true,
  },
};

function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function isScreenshotLike(pathLike, keywords) {
  if (!pathLike) return false;
  const s = String(pathLike).toLowerCase();
  const words = pickArray(keywords).map((x) => str(x).toLowerCase()).filter(Boolean);
  return words.some((w) => s.includes(w));
}

function str(v) {
  return String(v || '').trim();
}

function isValidDateYYYYMMDD(v) {
  return /^\d{4}-\d{2}-\d{2}$/.test(v);
}

function isHttpUrl(v) {
  return /^https?:\/\//i.test(v);
}

function pickArray(v) {
  return Array.isArray(v) ? v : [];
}

function hasLiteralBackslashN(body) {
  const s = String(body || '');
  return s.includes('\\n');
}

function hasSlashNToken(body) {
  const s = String(body || '');
  return /(^|\s)\/n(\s|$)/.test(s);
}

function containsLinkLike(text, blockedTlds) {
  const s = String(text || '').trim();
  if (!s) return false;
  if (/https?:\/\//i.test(s)) return true;
  if (/www\./i.test(s)) return true;
  const tlds = uniqueList(pickArray(blockedTlds).map((x) => str(x).toLowerCase()).filter(Boolean));
  if (!tlds.length) return false;
  const tldPattern = tlds.map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  if (!tldPattern) return false;
  // very rough domain detection; intentionally strict to avoid accidental bans
  const domainLike = new RegExp(`\\b[a-z0-9-]+\\.(${tldPattern})\\b`, 'i');
  if (domainLike.test(s)) return true;
  return false;
}

function normalizeTag(tag) {
  const v = str(tag);
  if (!v) return '';
  return v.startsWith('#') ? v : `#${v}`;
}

function uniqueList(items) {
  const out = [];
  const seen = new Set();
  for (const it of items) {
    const v = str(it);
    if (!v) continue;
    const k = v.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(v);
  }
  return out;
}

function parseDateSafe(iso) {
  const s = str(iso);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const d = new Date(`${s}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

function toPositiveInt(value, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.floor(n);
}

function parseToggle(value, fallback = true) {
  const s = String(value ?? '').trim().toLowerCase();
  if (!s) return fallback;
  if (['1', 'true', 'on', 'yes', 'y'].includes(s)) return true;
  if (['0', 'false', 'off', 'no', 'n'].includes(s)) return false;
  return fallback;
}

function toFiniteNumber(value, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return n;
}

function isPlainObject(v) {
  return !!v && typeof v === 'object' && !Array.isArray(v);
}

function deepMerge(base, override) {
  if (Array.isArray(base)) {
    return Array.isArray(override) ? override : [...base];
  }
  if (isPlainObject(base)) {
    const out = { ...base };
    if (isPlainObject(override)) {
      for (const key of Object.keys(override)) {
        if (Object.prototype.hasOwnProperty.call(base, key)) {
          out[key] = deepMerge(base[key], override[key]);
        } else {
          out[key] = override[key];
        }
      }
    }
    return out;
  }
  return override === undefined ? base : override;
}

function compileRegexList(patterns, fallbackPatterns = []) {
  const out = [];
  const input = pickArray(patterns);
  for (const raw of input) {
    const source = str(raw);
    if (!source) continue;
    try {
      out.push(new RegExp(source, 'i'));
    } catch {
      // Ignore invalid custom regex patterns; defaults still apply.
    }
  }
  if (out.length > 0 || input.length === 0) return out;
  if (!fallbackPatterns.length) return out;
  return compileRegexList(fallbackPatterns, []);
}

function hasAnyKeyword(text, keywords) {
  const s = String(text || '');
  if (!s) return false;
  const words = pickArray(keywords).map((x) => str(x)).filter(Boolean);
  return words.some((w) => s.includes(w));
}

async function loadPolicy(filePath, { allowMissing = false } = {}) {
  const policyPath = str(filePath);
  if (!policyPath) {
    return { exists: false, path: null, overrides: {}, error: null };
  }
  try {
    const raw = await readFile(policyPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!isPlainObject(parsed)) {
      throw new Error(`Policy file is not a JSON object: ${policyPath}`);
    }
    return { exists: true, path: policyPath, overrides: parsed, error: null };
  } catch (e) {
    const code = e?.code || '';
    if (allowMissing && code === 'ENOENT') {
      return { exists: false, path: policyPath, overrides: {}, error: null };
    }
    throw new Error(`Failed to load policy file "${policyPath}": ${e?.message || String(e)}`);
  }
}

function daysSince(isoDate) {
  const d = parseDateSafe(isoDate);
  if (!d) return null;
  const now = new Date();
  const nowAtDay = new Date(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}T00:00:00`);
  const diff = nowAtDay.getTime() - d.getTime();
  return Math.floor(diff / (24 * 60 * 60 * 1000));
}

async function loadTagRegistry(filePath) {
  try {
    const raw = await readFile(filePath, 'utf8');
    const data = JSON.parse(raw);
    const tagsRaw = Array.isArray(data)
      ? data
      : Array.isArray(data?.tags)
        ? data.tags
        : [];
    const normalized = uniqueList(tagsRaw.map(normalizeTag).filter(Boolean));
    return {
      exists: true,
      path: filePath,
      updated_at: str(data?.updated_at) || null,
      source: data?.source && typeof data.source === 'object' ? data.source : null,
      tags: normalized,
    };
  } catch {
    return {
      exists: false,
      path: filePath,
      updated_at: null,
      source: null,
      tags: [],
    };
  }
}

function hasAiTemplateStyle(body, phrases) {
  const s = String(body || '').toLowerCase();
  const templates = pickArray(phrases).map((x) => str(x)).filter(Boolean);
  return templates.filter((p) => s.includes(p.toLowerCase()));
}

function hasPersonalVoice(body, keywords) {
  return hasAnyKeyword(body, keywords);
}

function hasConcreteSignals({ body, sourceName, sourceDate, strictAntiAi, policy }) {
  const s = String(body || '');
  const minDigitCount = toPositiveInt(policy?.anti_ai?.strict_min_digit_count, 2);
  const minSignalCount = toPositiveInt(policy?.anti_ai?.strict_min_signal_count, 2);
  const weekKeywords = pickArray(policy?.anti_ai?.week_keywords);
  const digitCount = (s.match(/\d/g) || []).length;
  const hasDateLike = /\d{4}[年\-/.]\d{1,2}[月\-/.]\d{1,2}日?/.test(s) || /\d{1,2}月\d{1,2}日/.test(s);
  const hasAmountLike = /\d+\s*(亿|万|%|美元|人民币|条|家|款|次)/.test(s);
  const hasSourceMention = !!sourceName && s.includes(sourceName);
  const hasWeekMention = hasAnyKeyword(s, weekKeywords) || (!!sourceDate && s.includes(sourceDate));
  const hasHardFactSignal = digitCount >= minDigitCount || hasDateLike || hasAmountLike;
  const signalCount = [digitCount >= minDigitCount, hasDateLike, hasAmountLike, hasSourceMention, hasWeekMention].filter(Boolean).length;
  return {
    ok: strictAntiAi ? hasSourceMention && hasHardFactSignal && signalCount >= minSignalCount : signalCount >= 1,
    value: {
      digit_count: digitCount,
      min_digit_count: minDigitCount,
      has_date_like: hasDateLike,
      has_amount_like: hasAmountLike,
      has_source_mention: hasSourceMention,
      has_week_mention: hasWeekMention,
      has_hard_fact_signal: hasHardFactSignal,
      signal_count: signalCount,
      strict_min_signal_count: minSignalCount,
      strict_anti_ai: strictAntiAi,
    },
  };
}

function hasPlaceholderTag(tags, compiledPatterns) {
  const hit = [];
  for (const t of tags) {
    const x = str(t);
    if (!x) continue;
    if (compiledPatterns.some((re) => re.test(x))) hit.push(x);
  }
  return hit;
}

function isImagePath(p) {
  const s = String(p || '').toLowerCase();
  return s.endsWith('.png') || s.endsWith('.jpg') || s.endsWith('.jpeg');
}

async function checkMediaDims(media, policy) {
  const images = media.filter(isImagePath);
  const results = [];
  for (const p of images) {
    try {
      const { width, height, format } = await getImageSize(p);
      const ratio = width / height;
      results.push({ path: p, ok: true, width, height, ratio, format });
    } catch (e) {
      results.push({ path: p, ok: false, error: e?.message || String(e) });
    }
  }

  // Strict-ish: expect portrait 3:4 assets for XHS cards (prefer 1242x1660).
  const ratioTarget = toFiniteNumber(policy?.media?.ratio_target, 3 / 4);
  const ratioTol = toFiniteNumber(policy?.media?.ratio_tolerance, 0.02);
  const preferredSizes = pickArray(policy?.media?.preferred_sizes);
  const maxDetailItems = toPositiveInt(policy?.media?.max_detail_items, 12);
  const bad = results.filter((r) => r.ok && Math.abs(r.ratio - ratioTarget) > ratioTol);
  const parseFailed = results.filter((r) => !r.ok);

  const hasAny = images.length > 0;
  const ok = !hasAny || (bad.length === 0 && parseFailed.length === 0);

  const perfect = results.filter((r) =>
    r.ok &&
    preferredSizes.some((s) => r.width === toPositiveInt(s?.width, -1) && r.height === toPositiveInt(s?.height, -1))
  );
  return {
    ok,
    value: {
      checked_images: images.length,
      passed: results.filter((r) => r.ok).length,
      parse_failed: parseFailed.length,
      ratio_bad: bad.length,
      perfect_1242x1660: perfect.length,
      preferred_size_matched: perfect.length,
      details: results.slice(0, maxDetailItems), // keep output bounded
    },
  };
}

async function buildChecks(payload, mode, { policy, tagRegistry, allowUnverifiedTags, minRegistryTags, requireSourceEvidence, strictAntiAi }) {
  const topic = str(payload?.topic);
  const sourceName = str(payload?.source?.name);
  const sourceUrl = str(payload?.source?.url);
  const sourceDate = str(payload?.source?.date);
  const sourceEvidenceSnippet = str(payload?.source?.evidence_snippet);
  const sourceKeyFacts = uniqueList(pickArray(payload?.source?.key_facts).map((x) => str(x)).filter(Boolean));

  const title = str(payload?.post?.title);
  const body = str(payload?.post?.body);
  const tagsRaw = pickArray(payload?.post?.tags).map((x) => normalizeTag(x)).filter(Boolean);
  const tags = tagsRaw.filter((x) => x.startsWith('#'));
  const realTopicsRaw = pickArray(payload?.post?.real_topics).map((x) => normalizeTag(x)).filter(Boolean);
  const realTopics = realTopicsRaw.filter((x) => x.startsWith('#'));
  const media = pickArray(payload?.post?.media).map((x) => str(x)).filter(Boolean);

  const topicMinLen = toPositiveInt(policy?.topic?.min_len, 4);
  const titleMinLen = toPositiveInt(policy?.post?.title_min_len, 8);
  const titleMaxLen = Math.max(titleMinLen, toPositiveInt(policy?.post?.title_max_len, 20));
  const bodyMinLen = toPositiveInt(policy?.post?.body_min_len, 80);
  const tagMinCount = toPositiveInt(policy?.tags?.min_count, 3);
  const tagMaxCount = Math.max(tagMinCount, toPositiveInt(policy?.tags?.max_count, 8));
  const realTopicMinCount = toPositiveInt(policy?.real_topics?.min_count, 3);
  const realTopicMaxCount = Math.max(realTopicMinCount, toPositiveInt(policy?.real_topics?.max_count, 8));
  const registryFreshWithinDays = toPositiveInt(policy?.tag_registry?.fresh_within_days, 7);
  const requiredRegistryPlatform = str(policy?.tag_registry?.required_platform || 'xiaohongshu').toLowerCase();
  const sourceEvidenceMinLen = toPositiveInt(policy?.source?.evidence_snippet_min_len, 16);
  const sourceEvidenceMaxLen = Math.max(sourceEvidenceMinLen, toPositiveInt(policy?.source?.evidence_snippet_max_len, 180));
  const keyFactMinCount = toPositiveInt(policy?.source?.key_facts_min_count, 2);
  const keyFactMaxCount = Math.max(keyFactMinCount, toPositiveInt(policy?.source?.key_facts_max_count, 5));
  const keyFactMinLen = toPositiveInt(policy?.source?.key_fact_min_len, 8);
  const keyFactMaxLen = Math.max(keyFactMinLen, toPositiveInt(policy?.source?.key_fact_max_len, 80));
  const mediaMinCount = toPositiveInt(policy?.media?.min_count, 1);
  const screenshotKeywords = pickArray(policy?.media?.screenshot_keywords);
  const blockedTlds = pickArray(policy?.link_detection?.blocked_tlds);
  const tagPlaceholderPatterns = compileRegexList(policy?.tags?.placeholder_patterns, DEFAULT_POLICY.tags.placeholder_patterns);
  const realTopicPlaceholderPatterns = compileRegexList(policy?.real_topics?.placeholder_patterns, DEFAULT_POLICY.real_topics.placeholder_patterns);
  const hotSourceDateMustBeToday = parseToggle(policy?.hot_mode?.source_date_must_be_today, true);

  const titleLen = [...title].length;
  const bodyLen = [...body].length;
  const screenshotOnly = media.length > 0 && media.every((x) => isScreenshotLike(x, screenshotKeywords));
  const hotMode = mode === 'hot';
  const hasBackslashN = hasLiteralBackslashN(body);
  const hasSlashN = hasSlashNToken(body);
  const mediaDims = await checkMediaDims(media, policy);
  const linkInTitle = containsLinkLike(title, blockedTlds);
  const linkInBody = containsLinkLike(body, blockedTlds);
  const linkInTags = tagsRaw.some((t) => containsLinkLike(t, blockedTlds));
  const linkInMediaPath = media.some((p) => containsLinkLike(p, blockedTlds) || String(p).includes('://'));
  const duplicateTagCount = tagsRaw.length - uniqueList(tagsRaw).length;
  const duplicateRealTopicCount = realTopicsRaw.length - uniqueList(realTopicsRaw).length;
  const placeholderTags = hasPlaceholderTag(tagsRaw, tagPlaceholderPatterns);
  const placeholderRealTopics = hasPlaceholderTag(realTopicsRaw, realTopicPlaceholderPatterns);
  const aiTemplateHits = hasAiTemplateStyle(body, policy?.anti_ai?.template_phrases);
  const personalVoice = hasPersonalVoice(body, policy?.anti_ai?.personal_voice_keywords);
  const concreteSignals = hasConcreteSignals({ body, sourceName, sourceDate, strictAntiAi, policy });
  const registryTagSet = new Set((tagRegistry?.tags || []).map((x) => str(x).toLowerCase()));
  const unverifiedTags = tags.filter((t) => !registryTagSet.has(str(t).toLowerCase()));
  const unverifiedRealTopics = realTopics.filter((t) => !registryTagSet.has(str(t).toLowerCase()));
  const registryAgeDays = daysSince(tagRegistry?.updated_at);
  const registryFresh = registryAgeDays !== null && registryAgeDays >= 0 && registryAgeDays <= registryFreshWithinDays;
  const registrySourcePlatform = str(tagRegistry?.source?.platform).toLowerCase();
  const registrySourceMethod = str(tagRegistry?.source?.method);

  const sourceEvidenceOk =
    !requireSourceEvidence ||
    (sourceEvidenceSnippet.length >= sourceEvidenceMinLen &&
      sourceEvidenceSnippet.length <= sourceEvidenceMaxLen &&
      !containsLinkLike(sourceEvidenceSnippet, blockedTlds) &&
      (!!sourceName && sourceEvidenceSnippet.includes(sourceName)));

  const sourceKeyFactLengthBad = sourceKeyFacts.filter((x) => x.length < keyFactMinLen || x.length > keyFactMaxLen);
  const sourceKeyFactLinkBad = sourceKeyFacts.filter((x) => containsLinkLike(x, blockedTlds));
  const sourceKeyFactHasDateOrNumber = sourceKeyFacts.some(
    (x) => /\d/.test(x) || /\d{4}[年\-/.]\d{1,2}[月\-/.]\d{1,2}日?/.test(x) || /\d{1,2}月\d{1,2}日/.test(x)
  );
  const sourceKeyFactsOk =
    !requireSourceEvidence ||
    (sourceKeyFacts.length >= keyFactMinCount &&
      sourceKeyFacts.length <= keyFactMaxCount &&
      sourceKeyFactLengthBad.length === 0 &&
      sourceKeyFactLinkBad.length === 0 &&
      sourceKeyFactHasDateOrNumber);

  const checks = {
    has_topic: {
      ok: topic.length >= topicMinLen,
      value: topic || null,
    },
    has_source: {
      ok: !!sourceName && isHttpUrl(sourceUrl) && isValidDateYYYYMMDD(sourceDate),
      value: { name: sourceName || null, url: sourceUrl || null, date: sourceDate || null },
    },
    source_evidence_snippet_ok: {
      ok: sourceEvidenceOk,
      value: {
        required: requireSourceEvidence,
        min_len: sourceEvidenceMinLen,
        max_len: sourceEvidenceMaxLen,
        length: sourceEvidenceSnippet.length,
        contains_source_name: !!sourceName && sourceEvidenceSnippet.includes(sourceName),
      },
    },
    source_key_facts_ok: {
      ok: sourceKeyFactsOk,
      value: {
        required: requireSourceEvidence,
        min_count: keyFactMinCount,
        max_count: keyFactMaxCount,
        min_len: keyFactMinLen,
        max_len: keyFactMaxLen,
        count: sourceKeyFacts.length,
        bad_length: sourceKeyFactLengthBad,
        has_link_like: sourceKeyFactLinkBad,
        has_date_or_number_signal: sourceKeyFactHasDateOrNumber,
      },
    },
    title_ok: {
      ok: titleLen >= titleMinLen && titleLen <= titleMaxLen,
      value: { title: title || null, length: titleLen, min_len: titleMinLen, max_len: titleMaxLen },
    },
    body_ok: {
      ok: bodyLen >= bodyMinLen,
      value: { length: bodyLen, min_len: bodyMinLen },
    },
    body_newline_normalized: {
      // Allow literal "\\n" in payload (we can normalize before writing), but forbid "/n" token.
      ok: !hasSlashN,
      value: {
        has_literal_backslash_n: hasBackslashN,
        has_slash_n_token: hasSlashN,
      },
    },
    tags_ok: {
      ok: tags.length >= tagMinCount && tags.length <= tagMaxCount && duplicateTagCount === 0,
      value: { count: tags.length, min_count: tagMinCount, max_count: tagMaxCount, duplicate_count: duplicateTagCount, tags },
    },
    tags_not_placeholder: {
      ok: placeholderTags.length === 0,
      value: {
        hit: placeholderTags,
      },
    },
    real_topics_ok: {
      ok: realTopics.length >= realTopicMinCount && realTopics.length <= realTopicMaxCount && duplicateRealTopicCount === 0,
      value: {
        count: realTopics.length,
        min_count: realTopicMinCount,
        max_count: realTopicMaxCount,
        duplicate_count: duplicateRealTopicCount,
        real_topics: realTopics,
      },
    },
    real_topics_not_placeholder: {
      ok: placeholderRealTopics.length === 0,
      value: {
        hit: placeholderRealTopics,
      },
    },
    tag_registry_meta_ok: {
      ok:
        tagRegistry.exists &&
        registryFresh &&
        tagRegistry.tags.length >= minRegistryTags &&
        registrySourcePlatform === requiredRegistryPlatform &&
        !!registrySourceMethod,
      value: {
        registry_exists: !!tagRegistry.exists,
        registry_path: tagRegistry.path,
        registry_updated_at: tagRegistry.updated_at,
        registry_age_days: registryAgeDays,
        registry_fresh: registryFresh,
        registry_fresh_within_days: registryFreshWithinDays,
        registry_fresh_within_days_7: registryFresh,
        registry_tag_count: tagRegistry.tags.length,
        min_registry_tags: minRegistryTags,
        source_platform: registrySourcePlatform || null,
        required_source_platform: requiredRegistryPlatform || null,
        source_method: registrySourceMethod || null,
      },
    },
    tags_from_registry: {
      ok: allowUnverifiedTags || (tagRegistry.exists && registryFresh && unverifiedTags.length === 0),
      value: {
        allow_unverified_tags: allowUnverifiedTags,
        registry_exists: !!tagRegistry.exists,
        registry_path: tagRegistry.path,
        registry_updated_at: tagRegistry.updated_at,
        registry_age_days: registryAgeDays,
        registry_fresh: registryFresh,
        registry_fresh_within_days: registryFreshWithinDays,
        registry_fresh_within_days_7: registryFresh,
        registry_tag_count: tagRegistry.tags.length,
        unverified_tags: unverifiedTags,
      },
    },
    real_topics_from_registry: {
      ok: allowUnverifiedTags || (tagRegistry.exists && registryFresh && unverifiedRealTopics.length === 0),
      value: {
        allow_unverified_tags: allowUnverifiedTags,
        registry_exists: !!tagRegistry.exists,
        registry_path: tagRegistry.path,
        registry_updated_at: tagRegistry.updated_at,
        registry_age_days: registryAgeDays,
        registry_fresh: registryFresh,
        registry_fresh_within_days: registryFreshWithinDays,
        registry_fresh_within_days_7: registryFresh,
        registry_tag_count: tagRegistry.tags.length,
        unverified_real_topics: unverifiedRealTopics,
      },
    },
    no_links_in_content: {
      ok: !(linkInTitle || linkInBody || linkInTags),
      value: {
        title: linkInTitle,
        body: linkInBody,
        tags: linkInTags,
      },
    },
    no_links_in_media_path: {
      ok: !linkInMediaPath,
      value: linkInMediaPath ? media : null,
    },
    media_ok: {
      ok: media.length >= mediaMinCount && !screenshotOnly,
      value: { count: media.length, min_count: mediaMinCount, screenshot_only: screenshotOnly, media },
    },
    media_dim_ok: mediaDims,
    anti_ai_personal_voice: {
      ok: personalVoice,
      value: { has_personal_voice: personalVoice },
    },
    anti_ai_concrete_signals: concreteSignals,
    anti_ai_source_mentioned_in_body: {
      ok: !!sourceName && body.includes(sourceName),
      value: {
        source_name: sourceName || null,
        mentioned: !!sourceName && body.includes(sourceName),
      },
    },
    anti_ai_template_phrase: {
      ok: aiTemplateHits.length === 0,
      value: {
        hit: aiTemplateHits,
      },
    },
    hot_source_is_today: {
      ok: !hotMode || !hotSourceDateMustBeToday || sourceDate === todayISO(),
      value: {
        source_date_must_be_today: hotSourceDateMustBeToday,
        required_date: hotMode && hotSourceDateMustBeToday ? todayISO() : null,
        source_date: sourceDate || null,
      },
    },
  };

  return checks;
}

async function main(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      in: { type: 'string' },
      mode: { type: 'string', default: 'normal' },
      policy: { type: 'string', default: DEFAULT_POLICY_PATH },
      'tag-registry': { type: 'string', default: './data/tag_registry.json' },
      'allow-unverified-tags': { type: 'boolean', default: false },
      'min-registry-tags': { type: 'string', default: '12' },
      'require-source-evidence': { type: 'string', default: 'on' },
      'strict-anti-ai': { type: 'string', default: 'on' },
      json: { type: 'boolean', default: true },
      help: { type: 'boolean', default: false },
    },
    allowPositionals: true,
  });

  if (values.help) {
    console.log(usage());
    return;
  }

  if (!values.in) {
    throw new Error('Missing --in <payloadJsonPath>');
  }

  const raw = await readFile(values.in, 'utf8');
  const payload = JSON.parse(raw);
  const mode = str(values.mode || 'normal').toLowerCase();
  const policyFilePath = str(values.policy) || DEFAULT_POLICY_PATH;
  const customPolicy = await loadPolicy(policyFilePath, { allowMissing: false });
  const effectivePolicy = deepMerge(DEFAULT_POLICY, customPolicy.overrides || {});
  const tagRegistryPath = str(values['tag-registry']) || './data/tag_registry.json';
  const tagRegistry = await loadTagRegistry(tagRegistryPath);
  const allowUnverifiedTags = !!values['allow-unverified-tags'];
  const minRegistryTags = toPositiveInt(values['min-registry-tags'], 12);
  const requireSourceEvidence = parseToggle(values['require-source-evidence'], true);
  const strictAntiAi = parseToggle(values['strict-anti-ai'], true);
  const checks = await buildChecks(payload, mode, {
    policy: effectivePolicy,
    tagRegistry,
    allowUnverifiedTags,
    minRegistryTags,
    requireSourceEvidence,
    strictAntiAi,
  });

  const missing = Object.entries(checks)
    .filter(([, item]) => !item.ok)
    .map(([key]) => key);

  const result = {
    task: 'xhs_publish_payload_validate',
    ok: missing.length === 0,
    mode,
    policy: {
      policy_path: customPolicy.path,
      policy_loaded: customPolicy.exists,
      tag_registry_path: tagRegistry.path,
      allow_unverified_tags: allowUnverifiedTags,
      min_registry_tags: minRegistryTags,
      require_source_evidence: requireSourceEvidence,
      anti_ai_style_required: true,
      strict_anti_ai: strictAntiAi,
      policy_snapshot: effectivePolicy,
    },
    checks,
    missing,
  };

  if (values.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(`ok: ${result.ok}`);
    console.log(`missing: ${missing.join(', ') || '(none)'}`);
  }

  if (!result.ok) {
    process.exitCode = 2;
  }
}

main(process.argv.slice(2)).catch((e) => {
  console.error(e?.message || String(e));
  process.exitCode = 1;
});
