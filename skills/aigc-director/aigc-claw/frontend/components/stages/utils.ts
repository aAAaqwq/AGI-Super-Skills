/**
 * 阶段数据工具函数
 * - 路径转 URL
 * - 剧本/分镜结构化文本解析与重建
 */

/** 将后端本地文件路径转换为浏览器可访问的 URL */
export function assetUrl(path: string): string {
  if (!path) return '';
  if (path.startsWith('http') || path.startsWith('/') || path.startsWith('blob:') || path.startsWith('data:')) return path;
  return '/' + path;
}

/* ─── 剧本 / 分镜 结构化文本解析 ─── */

export interface ParsedCharacter {
  name: string;
  description: string;
}

export interface ParsedSetting {
  name: string;
  description: string;
}

export interface ParsedScene {
  id: string;
  characters: string[];
  settings: string[];
  description: string;
  raw: string;
}

export interface ParsedScript {
  characters: ParsedCharacter[];
  settings: ParsedSetting[];
  scenes: ParsedScene[];
  isZh: boolean;
}

/** 解析结构化剧本/分镜文本 → 角色 + 场景 + 故事线 */
export function parseScriptText(text: string): ParsedScript {
  if (!text) return { characters: [], settings: [], scenes: [], isZh: false };

  const normalized = text.replace(/\\n/g, '\n');
  const isZh = /角色[:：]|场景设置[:：]|视频片段/.test(normalized);

  const charHeader = isZh ? /角色[:：]/ : /Characters[:：]/;
  const settingHeader = isZh ? /场景设置[:：]/ : /Settings[:：]/;
  const sceneHeader = isZh ? /视频片段[:：]/ : /Scenes[:：]/;

  function findMatch(src: string, pat: RegExp) {
    const m = src.match(pat);
    return m ? { index: src.indexOf(m[0]), length: m[0].length } : null;
  }

  function extractBlock(src: string, startPat: RegExp, endPat: RegExp | null): string {
    const sm = findMatch(src, startPat);
    if (!sm) return '';
    const sp = sm.index + sm.length;
    if (endPat) {
      const em = findMatch(src.slice(sp), endPat);
      return em ? src.slice(sp, sp + em.index) : src.slice(sp);
    }
    return src.slice(sp);
  }

  const charBlock = extractBlock(normalized, charHeader, settingHeader).trim();
  const settingBlock = extractBlock(normalized, settingHeader, sceneHeader).trim();
  const sceneBlock = extractBlock(normalized, sceneHeader, null).trim();

  const characters: ParsedCharacter[] = [];
  for (const line of charBlock.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    const ci = t.search(/[:：]/);
    if (ci > 0) {
      characters.push({
        name: t.slice(0, ci).trim(),
        description: t.slice(ci + 1).trim().replace(/\.\s*$/, ''),
      });
    }
  }

  const settings: ParsedSetting[] = [];
  for (const line of settingBlock.split('\n')) {
    const t = line.trim();
    if (!t) continue;
    const ci = t.search(/[:：]/);
    if (ci > 0) {
      settings.push({
        name: t.slice(0, ci).trim(),
        description: t.slice(ci + 1).trim().replace(/\.\s*$/, ''),
      });
    }
  }

  const scenes: ParsedScene[] = [];
  const scenePat = isZh
    ? /^视频片段\s*(\d+)\s*[:：]\s*(.*)/
    : /^Scene\s+(\d+)\s*[:：]\s*(.*)/i;

  for (const line of sceneBlock.split('\n')) {
    const m = line.trim().match(scenePat);
    if (m) {
      const raw = m[2];
      const cm = raw.match(/\[(?:Characters|角色)\s*[:：]\s*([^\]]+)\]/i);
      const sm2 = raw.match(/\[(?:Settings|场景(?:设置)?)\s*[:：]\s*([^\]]+)\]/i);
      const chars = cm ? cm[1].split(/[,，]/).map(s => s.trim()).filter(Boolean) : [];
      const sets = sm2 ? sm2[1].split(/[,，]/).map(s => s.trim()).filter(Boolean) : [];
      const desc = raw.replace(/\[.*?\]/g, '').trim();
      scenes.push({ id: m[1], characters: chars, settings: sets, description: desc, raw });
    }
  }

  return { characters, settings, scenes, isZh };
}

/** 将解析后的结构重建为标准文本格式 */
export function reconstructScriptText(parsed: ParsedScript): string {
  const { isZh, characters, settings, scenes } = parsed;
  const charH = isZh ? '角色:' : 'Characters:';
  const settH = isZh ? '场景设置:' : 'Settings:';
  const sceneH = isZh ? '视频片段:' : 'Scenes:';
  const scenePrefix = isZh ? '视频片段' : 'Scene';
  const charLabel = isZh ? '角色' : 'Characters';
  const settLabel = isZh ? '场景' : 'Settings';

  const lines: string[] = [];
  lines.push(charH);
  for (const c of characters) {
    lines.push(`${c.name}: ${c.description}`);
  }
  lines.push(settH);
  for (const s of settings) {
    lines.push(`${s.name}: ${s.description}`);
  }
  lines.push(sceneH);
  for (const sc of scenes) {
    const cp = sc.characters.length ? `[${charLabel}: ${sc.characters.join(', ')}]` : '';
    const sp = sc.settings.length ? `[${settLabel}: ${sc.settings.join(', ')}]` : '';
    const parts = [`${scenePrefix} ${sc.id}:`, cp, sp, sc.description].filter(Boolean);
    lines.push(parts.join(' '));
  }
  return lines.join('\n');
}
