#!/usr/bin/env python3
import argparse
import glob
import json
import os
from typing import Dict, List, Tuple

HOME = os.path.expanduser('~')
OPENCLAW_DIR = os.path.join(HOME, '.openclaw')
AGENTS_DIR = os.path.join(OPENCLAW_DIR, 'agents')
CRON_JOBS = os.path.join(OPENCLAW_DIR, 'cron', 'jobs.json')
OPENCLAW_JSON = os.path.join(OPENCLAW_DIR, 'openclaw.json')

STANDARD_PRIMARY = 'shibacc/claude-opus-4-6'
STANDARD_FALLBACKS = [
    'xingsuancode/claude-opus-4-6',
    'zai/glm-5-turbo',
    'minimax/MiniMax-M2.5',
    'ollama/qwen3.5:9b',
]


def read_json(path: str, default=None):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def parse_model_string(model: str) -> Tuple[str, str]:
    if not model or '/' not in model:
        return ('', model or '')
    provider, model_id = model.split('/', 1)
    return provider, model_id


def load_global_providers() -> Dict[str, List[str]]:
    data = read_json(OPENCLAW_JSON, {}) or {}
    out = {}
    providers = (((data.get('models') or {}).get('providers')) or {})
    for provider, cfg in providers.items():
        model_ids = []
        for m in (cfg.get('models') or []):
            mid = m.get('id')
            if mid:
                model_ids.append(mid)
        out[provider] = sorted(set(model_ids))
    return out


def load_agent_local_providers(agent_dir: str) -> Dict[str, List[str]]:
    models_json = os.path.join(agent_dir, 'agent', 'models.json')
    data = read_json(models_json, {}) or {}
    out = {}
    providers = (data.get('providers') or {})
    for provider, cfg in providers.items():
        model_ids = []
        for m in (cfg.get('models') or []):
            mid = m.get('id')
            if mid:
                model_ids.append(mid)
        out[provider] = sorted(set(model_ids))
    return out


def merge_provider_maps(a: Dict[str, List[str]], b: Dict[str, List[str]]) -> Dict[str, List[str]]:
    keys = set(a) | set(b)
    out = {}
    for k in keys:
        out[k] = sorted(set((a.get(k) or []) + (b.get(k) or [])))
    return out


def provider_configured(model: str, providers: Dict[str, List[str]]) -> bool:
    provider, _ = parse_model_string(model)
    return bool(provider and provider in providers)


def model_resolvable(model: str, providers: Dict[str, List[str]]) -> bool:
    provider, model_id = parse_model_string(model)
    if not provider or provider not in providers:
        return False
    if not model_id:
        return False
    return model_id in (providers.get(provider) or [])


def normalize_fallbacks(v) -> List[str]:
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str) and x.strip()]
    return []


def chain_matches(primary: str, fallbacks: List[str]) -> bool:
    return primary == STANDARD_PRIMARY and fallbacks == STANDARD_FALLBACKS


def short_chain(primary: str, fallbacks: List[str]) -> str:
    parts = [primary] if primary else []
    parts += list(fallbacks or [])
    return ' -> '.join(parts) if parts else '-'


def summarize_drift(primary: str, fallbacks: List[str], resolvable: bool, provider_ok: bool) -> str:
    issues = []
    if not provider_ok:
        issues.append('provider-missing')
    if not resolvable:
        issues.append('model-unresolvable')
    if primary != STANDARD_PRIMARY:
        issues.append('primary-drift')
    if fallbacks != STANDARD_FALLBACKS:
        issues.append('fallback-drift')
    return ','.join(issues) if issues else '-'


def audit_agents(scope_diff_only=False):
    global_providers = load_global_providers()
    rows = []
    for agent_json in sorted(glob.glob(os.path.join(AGENTS_DIR, '*', 'agent', 'agent.json'))):
        agent_root = os.path.dirname(os.path.dirname(agent_json))
        agent_id = os.path.basename(agent_root)
        data = read_json(agent_json, {}) or {}
        local_providers = load_agent_local_providers(agent_root)
        providers = merge_provider_maps(global_providers, local_providers)
        primary = data.get('model') if isinstance(data.get('model'), str) else ''
        fallbacks = normalize_fallbacks(data.get('fallbackModels'))
        provider_ok = provider_configured(primary, providers)
        resolvable = model_resolvable(primary, providers)
        matches = chain_matches(primary, fallbacks)
        drift = summarize_drift(primary, fallbacks, resolvable, provider_ok)
        status = 'OK' if matches and provider_ok and resolvable else 'DRIFT'
        row = {
            'agentId': agent_id,
            'primary': primary or '',
            'fallbacks': fallbacks,
            'providerConfigured': provider_ok,
            'modelResolvable': resolvable,
            'status': status,
            'drift': drift,
            'chainMatchesStandard': matches,
        }
        if not scope_diff_only or status != 'OK':
            rows.append(row)
    return rows


def audit_cron(agents_index: Dict[str, dict], scope_diff_only=False):
    jobs_data = read_json(CRON_JOBS, {}) or {}
    jobs = jobs_data.get('jobs') or []
    rows = []
    global_providers = load_global_providers()
    for job in jobs:
        payload = job.get('payload') or {}
        agent_id = job.get('agentId') or ''
        explicit_model = payload.get('model') if isinstance(payload.get('model'), str) else ''
        if explicit_model:
            primary = explicit_model
            fallbacks = normalize_fallbacks(payload.get('fallbacks'))
            effective_source = 'cron-explicit'
            provider_ok = provider_configured(primary, global_providers)
            resolvable = model_resolvable(primary, global_providers)
        else:
            agent = agents_index.get(agent_id) or {}
            primary = agent.get('primary') or ''
            fallbacks = agent.get('fallbacks') or []
            effective_source = 'agent-config' if agent else 'unknown/default'
            provider_ok = bool(agent.get('providerConfigured'))
            resolvable = bool(agent.get('modelResolvable'))
        matches = chain_matches(primary, fallbacks)
        drift = summarize_drift(primary, fallbacks, resolvable, provider_ok)
        status = 'OK' if matches and provider_ok and resolvable else 'DRIFT'
        row = {
            'id': job.get('id') or '',
            'name': job.get('name') or '',
            'agentId': agent_id,
            'enabled': bool(job.get('enabled')),
            'explicitModel': explicit_model or '',
            'effectiveSource': effective_source,
            'primary': primary,
            'fallbacks': fallbacks,
            'providerConfigured': provider_ok,
            'modelResolvable': resolvable,
            'status': status,
            'drift': drift,
        }
        if not scope_diff_only or status != 'OK':
            rows.append(row)
    return rows


def build_summary(agent_rows, cron_rows):
    provider_missing = 0
    unresolvable = 0
    drift_count = 0
    for row in list(agent_rows) + list(cron_rows):
        if not row.get('providerConfigured'):
            provider_missing += 1
        if not row.get('modelResolvable'):
            unresolvable += 1
        if row.get('status') != 'OK':
            drift_count += 1
    return {
        'agentsTotal': len(agent_rows),
        'cronTotal': len(cron_rows),
        'agentsOk': sum(1 for r in agent_rows if r['status'] == 'OK'),
        'cronOk': sum(1 for r in cron_rows if r['status'] == 'OK'),
        'driftCount': drift_count,
        'providerMissingCount': provider_missing,
        'modelUnresolvableCount': unresolvable,
        'cronExplicitModelCount': sum(1 for r in cron_rows if r.get('explicitModel')),
    }


def print_summary(summary):
    print('MCSTATUS SUMMARY')
    print(f"Agents: {summary['agentsOk']}/{summary['agentsTotal']} OK")
    print(f"Cron:   {summary['cronOk']}/{summary['cronTotal']} OK")
    print(f"Drift:  {summary['driftCount']}")
    print(f"Provider missing: {summary['providerMissingCount']}")
    print(f"Model unresolvable: {summary['modelUnresolvableCount']}")
    print(f"Cron explicit model: {summary['cronExplicitModelCount']}")
    print()


def print_agents(rows):
    print('AGENTS')
    print('agent | primary | providerOK | resolvable | status | drift')
    print('-' * 120)
    for r in rows:
        print(f"{r['agentId']} | {r['primary']} | {'Y' if r['providerConfigured'] else 'N'} | {'Y' if r['modelResolvable'] else 'N'} | {r['status']} | {r['drift']}")
        print(f"  fallbacks: {', '.join(r['fallbacks']) if r['fallbacks'] else '-'}")
    print()


def print_cron(rows):
    print('CRON')
    print('name | agent | explicitModel | source | primary | status | drift')
    print('-' * 140)
    for r in rows:
        print(f"{r['name']} | {r['agentId']} | {r['explicitModel'] or '-'} | {r['effectiveSource']} | {r['primary'] or '-'} | {r['status']} | {r['drift']}")
        if r['fallbacks']:
            print(f"  fallbacks: {', '.join(r['fallbacks'])}")
    print()


def main():
    ap = argparse.ArgumentParser(description='Audit OpenClaw agent + cron model governance.')
    ap.add_argument('--json', action='store_true', dest='json_output')
    ap.add_argument('--scope', choices=['agents', 'cron', 'all'], default='all')
    ap.add_argument('--diff-only', action='store_true')
    args = ap.parse_args()

    agent_rows = audit_agents(scope_diff_only=args.diff_only)
    agent_index = {r['agentId']: r for r in audit_agents(scope_diff_only=False)}
    cron_rows = audit_cron(agent_index, scope_diff_only=args.diff_only)
    summary = build_summary(agent_rows if args.scope in ('agents', 'all') else [], cron_rows if args.scope in ('cron', 'all') else [])

    payload = {
        'standardChain': {
            'primary': STANDARD_PRIMARY,
            'fallbacks': STANDARD_FALLBACKS,
        },
        'summary': summary,
        'agents': agent_rows if args.scope in ('agents', 'all') else [],
        'cron': cron_rows if args.scope in ('cron', 'all') else [],
    }

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"STANDARD: {short_chain(STANDARD_PRIMARY, STANDARD_FALLBACKS)}")
    print()
    print_summary(summary)
    if args.scope in ('agents', 'all'):
        print_agents(agent_rows)
    if args.scope in ('cron', 'all'):
        print_cron(cron_rows)


if __name__ == '__main__':
    main()
