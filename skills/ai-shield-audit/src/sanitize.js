#!/usr/bin/env node
/**
 * OpenClaw Shield — Config Sanitizer
 * Strips secrets from an OpenClaw config before external submission.
 */

'use strict';

const REDACTED = '[REDACTED]';

const SECRET_KEY_PATTERNS = [
  /key$/i, /token$/i, /secret$/i, /password$/i, /credential$/i, /private/i,
];

const SECRET_VALUE_PATTERNS = [
  /^sk-or-v1-[a-f0-9]+$/i,         // OpenRouter
  /^sk-[a-zA-Z0-9]+$/i,             // Generic API key
  /^\d+:[A-Za-z0-9_-]{35,}$/,       // Telegram bot token
  /^0x[a-fA-F0-9]{64}$/i,           // Private key
  /^xai-[a-zA-Z0-9]+$/i,            // xAI
  /^ghp_[a-zA-Z0-9]+$/i,            // GitHub
  /^gho_[a-zA-Z0-9]+$/i,            // GitHub OAuth
  /^glpat-[a-zA-Z0-9_-]+$/i,        // GitLab
  /^AKIA[0-9A-Z]{16}$/i,            // AWS
];

function sanitizeConfig(config) {
  return deepSanitize(JSON.parse(JSON.stringify(config)), []);
}

function deepSanitize(obj, path) {
  if (obj === null || obj === undefined) return obj;

  if (Array.isArray(obj)) {
    return obj.map((item, i) => deepSanitize(item, [...path, String(i)]));
  }

  if (typeof obj === 'object') {
    const result = {};
    for (const [key, val] of Object.entries(obj)) {
      result[key] = deepSanitize(val, [...path, key]);
    }
    return result;
  }

  if (typeof obj === 'string') {
    const currentKey = path[path.length - 1] || '';

    // Check if key name suggests a secret
    if (SECRET_KEY_PATTERNS.some(p => p.test(currentKey))) {
      return REDACTED;
    }

    // Check if value looks like a secret
    if (SECRET_VALUE_PATTERNS.some(p => p.test(obj))) {
      return REDACTED;
    }

    // Redact env sections aggressively
    if (path.includes('env') && obj.length > 20) {
      return REDACTED;
    }
  }

  return obj;
}

function sanitizeAndStringify(config, pretty = true) {
  const clean = sanitizeConfig(config);
  return pretty ? JSON.stringify(clean, null, 2) : JSON.stringify(clean);
}

module.exports = { sanitizeConfig, sanitizeAndStringify };
