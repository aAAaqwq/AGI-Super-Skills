#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DEFAULT_POLICY_PATH = path.resolve(__dirname, '../config/review_policy.json');
const DEFAULT_TAXONOMY_PATH = path.resolve(__dirname, '../config/review_taxonomy.json');

const DEFAULT_POLICY = {
  text: {
    min_body_len: 80,
    blocked_link_tlds: ['com', 'cn', 'net', 'org', 'io', 'me', 'co', 'app', 'dev'],
    hard_block_phrases: [
      '100%不被识别',
      '100% undetectable',
      '稳赚不赔',
      '保本保收益',
      '包治百病',
      '私信领取',
      '加微信',
      'vx:',
      'vx：',
    ],
    high_risk_patterns: [
      '(治愈|根治|包治|药到病除)',
      '(保证收益|稳赚|翻倍|保本)',
      '(兼职|刷单|返利|薅羊毛教程)',
      '(加微|加v|私聊我|私信我领取)',
    ],
    medium_risk_keywords: [
      '最强',
      '必买',
      '立刻下单',
      '免费领',
      '内幕',
      '黑科技',
      '秒过',
      '保姆级',
    ],
  },
  source: {
    min_evidence_snippet_len: 16,
    min_key_facts_count: 2,
  },
  ai: {
    provider: 'auto',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    temperature: 0,
    timeout_ms: 30000,
    max_images: 3,
    max_inline_image_bytes: 1200000,
    send_images: true,
  },
  decision: {
    pass_max_risk_score: 28,
    block_min_risk_score: 70,
    block_on_review: true,
    block_on_ai_error: true,
    max_hits: 12,
    review_queue: {
      enabled: true,
      name: 'xhs_manual_review',
      owner: 'content_safety',
      default_priority: 'P2',
      block_priority: 'P1',
      review_priority: 'P2',
      sla_minutes: 60,
    },
    severity_score: {
      low: 8,
      medium: 20,
      high: 45,
    },
  },
};

function usage() {
  return `review_publish_payload

Usage:
  node ./scripts/review_publish_payload.mjs --in <payloadJsonPath> [--mode hot] [--json]
  node ./scripts/review_publish_payload.mjs --in <payloadJsonPath> [--policy ./skills/xhs-skill/config/review_policy.json]
  node ./scripts/review_publish_payload.mjs --in <payloadJsonPath> [--taxonomy ./skills/xhs-skill/config/review_taxonomy.json]
  node ./scripts/review_publish_payload.mjs --in <payloadJsonPath> [--ai-provider auto|openai|none] [--require-ai on|off]
`;
}

function str(v) {
  return String(v || '').trim();
}

function pickArray(v) {
  return Array.isArray(v) ? v : [];
}

function toPositiveInt(value, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.floor(n);
}

function toFiniteNumber(value, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return n;
}

function parseToggle(value, fallback = true) {
  const s = String(value ?? '').trim().toLowerCase();
  if (!s) return fallback;
  if (['1', 'true', 'on', 'yes', 'y'].includes(s)) return true;
  if (['0', 'false', 'off', 'no', 'n'].includes(s)) return false;
  return fallback;
}

function uniqueList(items) {
  const out = [];
  const seen = new Set();
  for (const it of items) {
    const v = str(it);
    if (!v) continue;
    const key = v.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(v);
  }
  return out;
}

function normalizeTag(tag) {
  const v = str(tag);
  if (!v) return '';
  return v.startsWith('#') ? v : `#${v}`;
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

async function loadPolicy(filePath) {
  const policyPath = str(filePath);
  if (!policyPath) {
    throw new Error('Missing review policy path');
  }
  try {
    const raw = await readFile(policyPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!isPlainObject(parsed)) {
      throw new Error(`Review policy must be a JSON object: ${policyPath}`);
    }
    return { exists: true, path: policyPath, overrides: parsed };
  } catch (e) {
    throw new Error(`Failed to load review policy "${policyPath}": ${e?.message || String(e)}`);
  }
}

function parseFirstJsonObject(text) {
  const s = str(text);
  if (!s) return null;
  const i = s.indexOf('{');
  const j = s.lastIndexOf('}');
  if (i < 0 || j <= i) return null;
  try {
    return JSON.parse(s.slice(i, j + 1));
  } catch {
    return null;
  }
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
  const domainLike = new RegExp(`\\b[a-z0-9-]+\\.(${tldPattern})\\b`, 'i');
  return domainLike.test(s);
}

function compileRegexList(patterns) {
  const out = [];
  for (const raw of pickArray(patterns)) {
    const source = str(raw);
    if (!source) continue;
    try {
      out.push(new RegExp(source, 'i'));
    } catch {
      // ignore invalid regex from custom policy
    }
  }
  return out;
}

function normalizeRiskPath(pathLike) {
  if (Array.isArray(pathLike)) {
    return pathLike.map((x) => str(x).toLowerCase()).filter(Boolean).slice(0, 8);
  }
  const s = str(pathLike);
  if (!s) return [];
  return s
    .split(/[>|/]/)
    .map((x) => str(x).toLowerCase())
    .filter(Boolean)
    .slice(0, 8);
}

function riskPathText(pathArr) {
  const parts = normalizeRiskPath(pathArr);
  return parts.join(' > ');
}

async function loadTaxonomy(filePath) {
  const taxonomyPath = str(filePath);
  if (!taxonomyPath) {
    throw new Error('Missing review taxonomy path');
  }
  try {
    const raw = await readFile(taxonomyPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!isPlainObject(parsed)) {
      throw new Error(`Review taxonomy must be a JSON object: ${taxonomyPath}`);
    }
    return { exists: true, path: taxonomyPath, value: parsed };
  } catch (e) {
    throw new Error(`Failed to load review taxonomy "${taxonomyPath}": ${e?.message || String(e)}`);
  }
}

function buildTaxonomyIndex(rawTaxonomy) {
  const ruleIdToPath = new Map();
  const categoryToPath = new Map();
  const keywordMatchers = [];
  const declaredPaths = [];

  for (const item of pickArray(rawTaxonomy?.paths)) {
    const id = str(item?.id);
    const pathArr = normalizeRiskPath(item?.path || id);
    if (!pathArr.length) continue;
    declaredPaths.push({ id: id || riskPathText(pathArr), path: pathArr, label: str(item?.label) || null });

    for (const rid of pickArray(item?.rule_hit_ids)) {
      const key = str(rid).toLowerCase();
      if (!key) continue;
      ruleIdToPath.set(key, pathArr);
    }
    for (const cat of pickArray(item?.categories)) {
      const key = str(cat).toLowerCase();
      if (!key) continue;
      categoryToPath.set(key, pathArr);
    }
    for (const kw of pickArray(item?.keywords)) {
      const key = str(kw).toLowerCase();
      if (!key) continue;
      keywordMatchers.push({ keyword: key, path: pathArr });
    }
  }

  return {
    declared_paths: declaredPaths,
    rule_id_to_path: ruleIdToPath,
    category_to_path: categoryToPath,
    keyword_matchers: keywordMatchers.sort((a, b) => b.keyword.length - a.keyword.length),
  };
}

function fallbackRiskPathByHitId(hitId) {
  const id = str(hitId).toLowerCase();
  if (!id) return [];
  if (id === 'link_or_source_url_violation') return ['content', 'diversion', 'link'];
  if (id === 'hard_block_phrases' || id === 'high_risk_pattern') return ['content', 'marketing', 'false_promise'];
  if (id === 'medium_risk_keywords') return ['content', 'marketing', 'suspicious_phrase'];
  if (id === 'source_traceability_weak') return ['content', 'authenticity', 'traceability'];
  if (id === 'body_too_short') return ['content', 'quality', 'low_information'];
  return [];
}

function inferRiskPathFromText(text, taxonomyIndex) {
  const s = str(text).toLowerCase();
  if (!s) return [];
  for (const m of taxonomyIndex.keyword_matchers) {
    if (s.includes(m.keyword)) return m.path;
  }
  return [];
}

function inferRiskPathFromCategory(category, taxonomyIndex) {
  const key = str(category).toLowerCase();
  if (!key) return [];
  if (taxonomyIndex.category_to_path.has(key)) {
    return taxonomyIndex.category_to_path.get(key);
  }
  return inferRiskPathFromText(key, taxonomyIndex);
}

function inferRiskPathForRuleHit(hitId, hitText, taxonomyIndex) {
  const hitKey = str(hitId).toLowerCase();
  if (hitKey && taxonomyIndex.rule_id_to_path.has(hitKey)) {
    return taxonomyIndex.rule_id_to_path.get(hitKey);
  }
  const byText = inferRiskPathFromText(hitText, taxonomyIndex);
  if (byText.length) return byText;
  return fallbackRiskPathByHitId(hitId);
}

function evidenceQuote(v) {
  const s = str(v);
  return s ? s.slice(0, 240) : '';
}

function collectPayload(payload) {
  const topic = str(payload?.topic);
  const sourceName = str(payload?.source?.name);
  const sourceUrl = str(payload?.source?.url);
  const sourceDate = str(payload?.source?.date);
  const sourceEvidenceSnippet = str(payload?.source?.evidence_snippet);
  const sourceKeyFacts = uniqueList(pickArray(payload?.source?.key_facts).map((x) => str(x)).filter(Boolean));

  const title = str(payload?.post?.title);
  const body = str(payload?.post?.body);
  const tags = uniqueList(pickArray(payload?.post?.tags).map((x) => normalizeTag(x)).filter(Boolean));
  const realTopics = uniqueList(pickArray(payload?.post?.real_topics).map((x) => normalizeTag(x)).filter(Boolean));
  const media = pickArray(payload?.post?.media).map((x) => str(x)).filter(Boolean);

  const textBundle = [
    `topic: ${topic}`,
    `title: ${title}`,
    `body: ${body}`,
    `tags: ${tags.join(' ')}`,
    `real_topics: ${realTopics.join(' ')}`,
    `source_name: ${sourceName}`,
    `source_url: ${sourceUrl}`,
    `source_date: ${sourceDate}`,
    `source_evidence_snippet: ${sourceEvidenceSnippet}`,
    `source_key_facts: ${sourceKeyFacts.join(' | ')}`,
  ].join('\n');

  return {
    topic,
    sourceName,
    sourceUrl,
    sourceDate,
    sourceEvidenceSnippet,
    sourceKeyFacts,
    title,
    body,
    tags,
    realTopics,
    media,
    textBundle,
  };
}

function scoreHits(hits, severityScore) {
  let score = 0;
  for (const hit of hits) {
    const sev = str(hit?.severity || 'low').toLowerCase();
    score += toPositiveInt(severityScore?.[sev], 8);
  }
  return Math.min(100, score);
}

function buildRuleLayer(collected, policy, mode, taxonomyIndex) {
  const hits = [];
  const addHit = ({ id, severity, message, evidence = null, hard_block = false, risk_path = [] }) => {
    const riskPath = normalizeRiskPath(risk_path).length
      ? normalizeRiskPath(risk_path)
      : inferRiskPathForRuleHit(id, `${message}\n${JSON.stringify(evidence || '')}`, taxonomyIndex);

    let evidenceItems = [];
    if (typeof evidence === 'string') {
      evidenceItems = [{ quote: evidenceQuote(evidence), severity: str(severity).toLowerCase(), risk_path: riskPath }];
    } else if (Array.isArray(evidence)) {
      evidenceItems = evidence
        .map((x) => ({ quote: evidenceQuote(x), severity: str(severity).toLowerCase(), risk_path: riskPath }))
        .filter((x) => x.quote);
    } else if (evidence && typeof evidence === 'object') {
      const snippet = JSON.stringify(evidence);
      evidenceItems = [{ quote: evidenceQuote(snippet), severity: str(severity).toLowerCase(), risk_path: riskPath }];
    }

    hits.push({
      id,
      severity,
      message,
      evidence,
      evidence_items: evidenceItems.slice(0, 4),
      hard_block: !!hard_block,
      risk_path: riskPath,
      risk_path_text: riskPathText(riskPath),
    });
  };

  const bodyLen = [...collected.body].length;
  const minBodyLen = toPositiveInt(policy?.text?.min_body_len, 80);
  if (bodyLen < minBodyLen) {
    addHit({
      id: 'body_too_short',
      severity: 'medium',
      message: `正文长度不足: ${bodyLen} < ${minBodyLen}`,
      evidence: collected.body.slice(0, 120),
    });
  }

  const blockedTlds = pickArray(policy?.text?.blocked_link_tlds);
  const links = {
    title: containsLinkLike(collected.title, blockedTlds),
    body: containsLinkLike(collected.body, blockedTlds),
    tags: collected.tags.some((x) => containsLinkLike(x, blockedTlds)),
    real_topics: collected.realTopics.some((x) => containsLinkLike(x, blockedTlds)),
    source_url_is_http: /^https?:\/\//i.test(collected.sourceUrl),
  };
  if (links.title || links.body || links.tags || links.real_topics || !links.source_url_is_http) {
    addHit({
      id: 'link_or_source_url_violation',
      severity: 'high',
      message: '检测到链接导流风险或来源 URL 非 http/https',
      evidence: links,
      hard_block: true,
    });
  }

  const lowerText = `${collected.title}\n${collected.body}\n${collected.tags.join(' ')}\n${collected.realTopics.join(' ')}`.toLowerCase();
  const hardPhrases = pickArray(policy?.text?.hard_block_phrases).map((x) => str(x).toLowerCase()).filter(Boolean);
  const hardPhraseHits = hardPhrases.filter((p) => lowerText.includes(p));
  if (hardPhraseHits.length) {
    addHit({
      id: 'hard_block_phrases',
      severity: 'high',
      message: '命中硬拦截短语',
      evidence: hardPhraseHits,
      hard_block: true,
    });
  }

  const highPatterns = compileRegexList(policy?.text?.high_risk_patterns);
  const highPatternHits = [];
  for (const re of highPatterns) {
    const m = `${collected.title}\n${collected.body}`.match(re);
    if (m && m[0]) highPatternHits.push(m[0]);
  }
  if (highPatternHits.length) {
    addHit({
      id: 'high_risk_pattern',
      severity: 'high',
      message: '命中高风险表达模式',
      evidence: uniqueList(highPatternHits),
      hard_block: false,
    });
  }

  const mediumKeywords = pickArray(policy?.text?.medium_risk_keywords).map((x) => str(x).toLowerCase()).filter(Boolean);
  const mediumHits = mediumKeywords.filter((k) => lowerText.includes(k));
  if (mediumHits.length) {
    addHit({
      id: 'medium_risk_keywords',
      severity: 'medium',
      message: '命中可疑营销表达',
      evidence: mediumHits,
      hard_block: false,
    });
  }

  const minEvidenceSnippetLen = toPositiveInt(policy?.source?.min_evidence_snippet_len, 16);
  const minKeyFactsCount = toPositiveInt(policy?.source?.min_key_facts_count, 2);
  if (collected.sourceEvidenceSnippet.length < minEvidenceSnippetLen || collected.sourceKeyFacts.length < minKeyFactsCount) {
    addHit({
      id: 'source_traceability_weak',
      severity: mode === 'hot' ? 'high' : 'medium',
      message: '来源可追溯字段不足（evidence_snippet/key_facts）',
      evidence: {
        evidence_snippet_len: collected.sourceEvidenceSnippet.length,
        min_evidence_snippet_len: minEvidenceSnippetLen,
        key_facts_count: collected.sourceKeyFacts.length,
        min_key_facts_count: minKeyFactsCount,
      },
    });
  }

  const severityScore = policy?.decision?.severity_score || {};
  const rawRiskScore = scoreHits(hits, severityScore);
  const passMax = toFiniteNumber(policy?.decision?.pass_max_risk_score, 28);
  const blockMin = toFiniteNumber(policy?.decision?.block_min_risk_score, 70);
  const hardBlocked = hits.some((x) => !!x.hard_block);

  let decision = 'pass';
  if (hardBlocked || rawRiskScore >= blockMin) {
    decision = 'block';
  } else if (rawRiskScore > passMax) {
    decision = 'review';
  }

  const maxHits = toPositiveInt(policy?.decision?.max_hits, 12);
  const hitPaths = uniqueList(hits.map((x) => riskPathText(x.risk_path)).filter(Boolean));
  return {
    ok: decision === 'pass',
    decision,
    risk_score: rawRiskScore,
    hard_blocked: hardBlocked,
    thresholds: {
      pass_max_risk_score: passMax,
      block_min_risk_score: blockMin,
    },
    links,
    risk_paths: hitPaths,
    hits: hits.slice(0, maxHits),
  };
}

function mimeByPath(filePath) {
  const s = String(filePath || '').toLowerCase();
  if (s.endsWith('.png')) return 'image/png';
  if (s.endsWith('.jpg') || s.endsWith('.jpeg')) return 'image/jpeg';
  if (s.endsWith('.webp')) return 'image/webp';
  return null;
}

async function loadAiImages(media, policy) {
  const maxImages = toPositiveInt(policy?.ai?.max_images, 3);
  const maxInlineBytes = toPositiveInt(policy?.ai?.max_inline_image_bytes, 1200000);
  const imagePaths = media.filter((x) => !!mimeByPath(x)).slice(0, maxImages);
  const out = [];

  for (const p of imagePaths) {
    const absPath = path.resolve(p);
    const mime = mimeByPath(absPath);
    if (!mime) continue;

    try {
      const st = await stat(absPath);
      const sizeBytes = Number(st.size) || 0;
      if (sizeBytes <= 0) {
        out.push({ path: absPath, ok: false, reason: 'empty_file' });
        continue;
      }
      if (sizeBytes > maxInlineBytes) {
        out.push({ path: absPath, ok: false, reason: 'too_large', size_bytes: sizeBytes, max_inline_bytes: maxInlineBytes });
        continue;
      }
      const buff = await readFile(absPath);
      const dataUrl = `data:${mime};base64,${buff.toString('base64')}`;
      out.push({ path: absPath, ok: true, size_bytes: sizeBytes, mime, data_url: dataUrl });
    } catch (e) {
      out.push({ path: absPath, ok: false, reason: e?.message || String(e) });
    }
  }

  return out;
}

function sanitizeAiJson(json, taxonomyIndex) {
  const decisionRaw = str(json?.decision).toLowerCase();
  const decision = ['pass', 'review', 'block'].includes(decisionRaw) ? decisionRaw : 'review';
  const riskScore = Math.max(0, Math.min(100, toFiniteNumber(json?.risk_score, 60)));
  const reasons = pickArray(json?.reasons).map((x) => str(x)).filter(Boolean).slice(0, 12);
  const evidence = pickArray(json?.evidence)
    .map((x) => ({
      quote: str(x?.quote),
      category: str(x?.category),
      severity: str(x?.severity).toLowerCase() || 'medium',
      risk_path: normalizeRiskPath(x?.risk_path || x?.path),
    }))
    .filter((x) => x.quote)
    .map((x) => {
      const inferredPath =
        x.risk_path.length
          ? x.risk_path
          : inferRiskPathFromCategory(x.category, taxonomyIndex).length
            ? inferRiskPathFromCategory(x.category, taxonomyIndex)
            : inferRiskPathFromText(x.quote, taxonomyIndex);
      return {
        ...x,
        risk_path: inferredPath,
        risk_path_text: riskPathText(inferredPath),
      };
    })
    .slice(0, 12);

  const riskPaths = uniqueList(evidence.map((x) => x.risk_path_text).filter(Boolean));

  return {
    decision,
    risk_score: riskScore,
    reasons,
    evidence,
    risk_paths: riskPaths,
    need_human: !!json?.need_human,
  };
}

async function callOpenAiReview({ collected, policy, mode, ruleLayer, taxonomyIndex, requestedProvider, requireAi }) {
  const providerRaw = str(requestedProvider || policy?.ai?.provider || 'auto').toLowerCase();
  const openAiKey = str(process.env.OPENAI_API_KEY);

  let provider = providerRaw;
  if (provider === 'auto') {
    provider = openAiKey ? 'openai' : 'none';
  }

  if (provider === 'none') {
    return {
      enabled: false,
      used: false,
      ok: !requireAi,
      provider: 'none',
      reason: requireAi ? 'ai_required_but_disabled' : 'ai_disabled',
    };
  }

  if (provider !== 'openai') {
    return {
      enabled: true,
      used: false,
      ok: false,
      provider,
      reason: `unsupported_ai_provider:${provider}`,
    };
  }

  if (!openAiKey) {
    return {
      enabled: true,
      used: false,
      ok: false,
      provider: 'openai',
      reason: 'OPENAI_API_KEY missing',
    };
  }

  const baseUrl = str(process.env.OPENAI_BASE_URL || policy?.ai?.base_url || 'https://api.openai.com/v1').replace(/\/$/, '');
  const model = str(process.env.OPENAI_MODEL || policy?.ai?.model || 'gpt-4o-mini');
  const temperature = toFiniteNumber(policy?.ai?.temperature, 0);
  const timeoutMs = toPositiveInt(policy?.ai?.timeout_ms, 30000);
  const sendImages = parseToggle(policy?.ai?.send_images, true);

  const images = sendImages ? await loadAiImages(collected.media, policy) : [];
  const usableImages = images.filter((x) => x.ok && x.data_url);

  const systemPrompt = [
    '你是小红书发布前风控审核器。',
    '目标：识别违规/高风险内容并给出可解释证据。',
    '输出必须是 JSON 对象，不要输出 markdown，不要输出多余文本。',
    '字段要求：',
    '- decision: pass | review | block',
    '- risk_score: 0-100 数字',
    '- reasons: 字符串数组（简短）',
    '- evidence: 数组，每项含 quote/category/severity/risk_path(数组，层级路径)',
    '- need_human: 布尔值',
  ].join('\n');

  const userText = [
    `mode: ${mode}`,
    'payload:',
    collected.textBundle,
    'rule_layer_summary:',
    JSON.stringify(
      {
        decision: ruleLayer.decision,
        risk_score: ruleLayer.risk_score,
        hits: ruleLayer.hits,
      },
      null,
      2
    ),
    'risk_taxonomy_paths:',
    JSON.stringify(taxonomyIndex.declared_paths, null, 2),
    '请基于文本与图片（如果有）做多模态风险评估。',
  ].join('\n');

  const userContent = [{ type: 'text', text: userText }];
  for (const img of usableImages) {
    userContent.push({
      type: 'image_url',
      image_url: {
        url: img.data_url,
      },
    });
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resp = await fetch(`${baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${openAiKey}`,
      },
      body: JSON.stringify({
        model,
        temperature,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userContent },
        ],
      }),
      signal: controller.signal,
    });

    const raw = await resp.text();
    if (!resp.ok) {
      return {
        enabled: true,
        used: true,
        ok: false,
        provider: 'openai',
        model,
        status: resp.status,
        reason: `openai_http_${resp.status}`,
        error: str(raw).slice(0, 300),
        images: images.map((x) => ({ path: x.path, ok: x.ok, reason: x.reason || null, size_bytes: x.size_bytes || null })),
      };
    }

    const parsed = JSON.parse(raw);
    const content = parsed?.choices?.[0]?.message?.content;
    let contentText = '';
    if (typeof content === 'string') {
      contentText = content;
    } else if (Array.isArray(content)) {
      contentText = content
        .map((item) => (item && typeof item === 'object' && typeof item.text === 'string' ? item.text : ''))
        .filter(Boolean)
        .join('\n');
    }

    const aiJson = parseFirstJsonObject(contentText);
    if (!aiJson) {
      return {
        enabled: true,
        used: true,
        ok: false,
        provider: 'openai',
        model,
        reason: 'invalid_ai_json',
        raw_preview: str(contentText).slice(0, 300),
        images: images.map((x) => ({ path: x.path, ok: x.ok, reason: x.reason || null, size_bytes: x.size_bytes || null })),
      };
    }

    const sanitized = sanitizeAiJson(aiJson, taxonomyIndex);
    return {
      enabled: true,
      used: true,
      ok: true,
      provider: 'openai',
      model,
      ...sanitized,
      images: images.map((x) => ({ path: x.path, ok: x.ok, reason: x.reason || null, size_bytes: x.size_bytes || null })),
    };
  } catch (e) {
    return {
      enabled: true,
      used: true,
      ok: false,
      provider: 'openai',
      model,
      reason: e?.name === 'AbortError' ? 'ai_timeout' : 'ai_request_failed',
      error: e?.message || String(e),
    };
  } finally {
    clearTimeout(timer);
  }
}

function mergeDecision(ruleLayer, aiLayer, policy, requireAi) {
  const passMax = toFiniteNumber(policy?.decision?.pass_max_risk_score, 28);
  const blockMin = toFiniteNumber(policy?.decision?.block_min_risk_score, 70);
  const blockOnReview = parseToggle(policy?.decision?.block_on_review, true);
  const blockOnAiError = parseToggle(policy?.decision?.block_on_ai_error, true);

  if (ruleLayer.decision === 'block') {
    return {
      decision: 'block',
      risk_score: ruleLayer.risk_score,
      reason: 'rule_layer_block',
    };
  }

  if (requireAi && (!aiLayer.used || !aiLayer.ok)) {
    return {
      decision: 'block',
      risk_score: Math.max(ruleLayer.risk_score, 80),
      reason: 'ai_required_but_unavailable',
    };
  }

  if (aiLayer.used && !aiLayer.ok) {
    if (blockOnAiError) {
      return {
        decision: 'block',
        risk_score: Math.max(ruleLayer.risk_score, 75),
        reason: 'ai_layer_error',
      };
    }
    return {
      decision: ruleLayer.decision,
      risk_score: ruleLayer.risk_score,
      reason: 'ai_layer_error_but_ignored',
    };
  }

  if (aiLayer.used && aiLayer.ok) {
    const combinedRisk = Math.round(Math.max(ruleLayer.risk_score, toFiniteNumber(aiLayer.risk_score, 0)));

    if (aiLayer.decision === 'block' || combinedRisk >= blockMin) {
      return {
        decision: 'block',
        risk_score: combinedRisk,
        reason: 'ai_or_combined_block',
      };
    }

    if (aiLayer.decision === 'review' || ruleLayer.decision === 'review' || combinedRisk > passMax) {
      return {
        decision: blockOnReview ? 'block' : 'review',
        risk_score: combinedRisk,
        reason: blockOnReview ? 'review_treated_as_block' : 'needs_review',
      };
    }

    return {
      decision: 'pass',
      risk_score: combinedRisk,
      reason: 'rule_and_ai_pass',
    };
  }

  return {
    decision: ruleLayer.decision,
    risk_score: ruleLayer.risk_score,
    reason: 'rule_layer_only',
  };
}

function severityRank(severity) {
  const s = str(severity).toLowerCase();
  if (s === 'high') return 3;
  if (s === 'medium') return 2;
  return 1;
}

function collectAllRiskPaths(ruleLayer, aiLayer) {
  const out = [];
  const add = (pathArr) => {
    const p = normalizeRiskPath(pathArr);
    if (!p.length) return;
    const key = riskPathText(p);
    if (!key) return;
    if (out.some((x) => riskPathText(x) === key)) return;
    out.push(p);
  };

  for (const h of pickArray(ruleLayer?.hits)) add(h?.risk_path);
  for (const e of pickArray(aiLayer?.evidence)) add(e?.risk_path);
  return out;
}

function pickPrimaryRiskPath(ruleLayer, aiLayer, merged) {
  if (merged.decision === 'pass') return [];
  const ruleSorted = [...pickArray(ruleLayer?.hits)].sort((a, b) => severityRank(b?.severity) - severityRank(a?.severity));
  for (const h of ruleSorted) {
    const p = normalizeRiskPath(h?.risk_path);
    if (p.length) return p;
  }
  const aiSorted = [...pickArray(aiLayer?.evidence)].sort((a, b) => severityRank(b?.severity) - severityRank(a?.severity));
  for (const e of aiSorted) {
    const p = normalizeRiskPath(e?.risk_path);
    if (p.length) return p;
  }
  return [];
}

function buildEvidenceItems(ruleLayer, aiLayer) {
  const items = [];
  for (const h of pickArray(ruleLayer?.hits)) {
    const pathArr = normalizeRiskPath(h?.risk_path);
    const quotes = pickArray(h?.evidence_items);
    if (quotes.length) {
      for (const q of quotes) {
        items.push({
          source: 'rule',
          id: str(h?.id),
          severity: str(h?.severity).toLowerCase(),
          risk_path: pathArr,
          risk_path_text: riskPathText(pathArr),
          quote: evidenceQuote(q?.quote),
          detail: str(h?.message),
          hard_block: !!h?.hard_block,
        });
      }
      continue;
    }
    items.push({
      source: 'rule',
      id: str(h?.id),
      severity: str(h?.severity).toLowerCase(),
      risk_path: pathArr,
      risk_path_text: riskPathText(pathArr),
      quote: evidenceQuote(h?.message),
      detail: str(h?.message),
      hard_block: !!h?.hard_block,
    });
  }

  for (const e of pickArray(aiLayer?.evidence)) {
    const pathArr = normalizeRiskPath(e?.risk_path);
    items.push({
      source: 'ai',
      id: str(e?.category || 'ai_signal'),
      severity: str(e?.severity).toLowerCase() || 'medium',
      risk_path: pathArr,
      risk_path_text: riskPathText(pathArr),
      quote: evidenceQuote(e?.quote),
      detail: str(e?.category),
      hard_block: false,
    });
  }
  return items.slice(0, 30);
}

function buildReviewQueue(merged, policy, primaryRiskPath) {
  const cfg = policy?.decision?.review_queue || {};
  const enabled = parseToggle(cfg?.enabled, true);
  if (!enabled || merged.decision === 'pass') return null;

  const queueName = str(cfg?.name || 'xhs_manual_review');
  const owner = str(cfg?.owner || 'content_safety');
  const defaultPriority = str(cfg?.default_priority || 'P2');
  const blockPriority = str(cfg?.block_priority || defaultPriority);
  const reviewPriority = str(cfg?.review_priority || defaultPriority);
  const priority = merged.decision === 'block' ? blockPriority : reviewPriority;
  const slaMinutes = toPositiveInt(cfg?.sla_minutes, 60);
  const ts = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14);
  const pathKey = (riskPathText(primaryRiskPath) || 'unknown').replace(/[^a-z0-9_]+/ig, '_').replace(/^_+|_+$/g, '').toLowerCase();

  return {
    required: true,
    queue_name: queueName,
    owner,
    priority: priority || defaultPriority,
    sla_minutes: slaMinutes,
    review_ticket_id: `rvw_${ts}_${pathKey || 'risk'}`,
    reason: merged.reason,
    risk_path: normalizeRiskPath(primaryRiskPath),
    risk_path_text: riskPathText(primaryRiskPath),
  };
}

async function main(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      in: { type: 'string' },
      mode: { type: 'string', default: 'normal' },
      policy: { type: 'string', default: DEFAULT_POLICY_PATH },
      taxonomy: { type: 'string', default: DEFAULT_TAXONOMY_PATH },
      'ai-provider': { type: 'string', default: 'auto' },
      'require-ai': { type: 'string', default: 'off' },
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
  const policyPath = str(values.policy) || DEFAULT_POLICY_PATH;
  const loadedPolicy = await loadPolicy(policyPath);
  const taxonomyPath = str(values.taxonomy) || DEFAULT_TAXONOMY_PATH;
  const loadedTaxonomy = await loadTaxonomy(taxonomyPath);
  const taxonomyIndex = buildTaxonomyIndex(loadedTaxonomy.value);
  const policy = deepMerge(DEFAULT_POLICY, loadedPolicy.overrides || {});
  const requireAi = parseToggle(values['require-ai'], false);
  const requestedProvider = str(values['ai-provider'] || policy?.ai?.provider || 'auto').toLowerCase();

  const collected = collectPayload(payload);
  const ruleLayer = buildRuleLayer(collected, policy, mode, taxonomyIndex);
  const aiLayer = await callOpenAiReview({
    collected,
    policy,
    mode,
    ruleLayer,
    taxonomyIndex,
    requestedProvider,
    requireAi,
  });

  const merged = mergeDecision(ruleLayer, aiLayer, policy, requireAi);
  const primaryRiskPath = pickPrimaryRiskPath(ruleLayer, aiLayer, merged);
  const riskPaths = collectAllRiskPaths(ruleLayer, aiLayer);
  const evidenceItems = buildEvidenceItems(ruleLayer, aiLayer);
  const reviewQueue = buildReviewQueue(merged, policy, primaryRiskPath);
  const missing = [];
  if (merged.decision !== 'pass') {
    missing.push('review_pass');
  }

  const result = {
    task: 'xhs_publish_payload_review',
    ok: merged.decision === 'pass',
    mode,
    decision: merged.decision,
    risk_score: merged.risk_score,
    reason: merged.reason,
    risk_path: primaryRiskPath,
    risk_path_text: riskPathText(primaryRiskPath),
    risk_paths: riskPaths.map((x) => ({ path: x, text: riskPathText(x) })),
    evidence: {
      total: evidenceItems.length,
      items: evidenceItems,
    },
    review_queue: reviewQueue,
    policy: {
      review_policy_path: loadedPolicy.path,
      review_taxonomy_path: loadedTaxonomy.path,
      ai_provider_requested: requestedProvider,
      require_ai: requireAi,
      pass_max_risk_score: toFiniteNumber(policy?.decision?.pass_max_risk_score, 28),
      block_min_risk_score: toFiniteNumber(policy?.decision?.block_min_risk_score, 70),
      block_on_review: parseToggle(policy?.decision?.block_on_review, true),
      block_on_ai_error: parseToggle(policy?.decision?.block_on_ai_error, true),
    },
    layers: {
      rule_layer: ruleLayer,
      ai_layer: aiLayer,
    },
    missing,
  };

  if (values.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(`ok: ${result.ok}`);
    console.log(`decision: ${result.decision}`);
    console.log(`risk_score: ${result.risk_score}`);
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
