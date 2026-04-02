#!/usr/bin/env python3
"""Model & Provider Health Check — tests all configured providers and models."""

import json, subprocess, sys, os, time
from pathlib import Path

CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
PASS_DIR = os.path.expanduser("~/.password-store")

def get_env_value(key_ref):
    """Resolve ${VAR_NAME} from .env or pass."""
    if not key_ref or not key_ref.startswith("${"):
        return key_ref
    var_name = key_ref.strip("${}").split("_KEY")[0] + "_KEY"
    # Try .env first
    env_path = os.path.expanduser("~/.openclaw/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{var_name}="):
                    return line.split("=", 1)[1].strip('"').strip("'")
    # Try pass
    pass_name = "api/" + var_name.lower().replace("_api_key", "").replace("_key", "")
    try:
        result = subprocess.run(["pass", "show", pass_name], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return key_ref

def test_provider(name, cfg, test_model=None):
    """Test a single provider with one model."""
    base = cfg.get("baseUrl", "")
    api_type = cfg.get("api", "openai-completions")
    key = get_env_value(cfg.get("apiKey", ""))
    
    models = cfg.get("models", [])
    if not models:
        return None
    
    # Pick test model
    if test_model:
        model_id = test_model
    else:
        model_id = models[0].get("id", "")
    
    result = {"provider": name, "model": model_id, "api": api_type}
    
    try:
        start = time.time()
        if "anthropic" in api_type:
            # Anthropic format
            cmd = [
                "curl", "-s", "-w", "\\nHTTP_STATUS:%{http_code}", "--max-time", "10",
                "-H", f"x-api-key: {key}",
                "-H", "Content-Type: application/json",
                "-H", "anthropic-version: 2023-06-01",
                "-d", json.dumps({"model": model_id, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 3}),
                f"{base}/v1/messages"
            ]
        elif "ollama" in api_type:
            # Ollama format
            cmd = [
                "curl", "-s", "-w", "\\nHTTP_STATUS:%{http_code}", "--max-time", "10",
                "--noproxy", "*",
                "-d", json.dumps({"model": model_id, "messages": [{"role": "user", "content": "ok"}], "stream": False}),
                f"{base}/api/chat"
            ]
        else:
            # OpenAI format
            cmd = [
                "curl", "-s", "-w", "\\nHTTP_STATUS:%{http_code}", "--max-time", "10",
                "-H", f"Authorization: Bearer {key}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({"model": model_id, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 3}),
                f"{base}/v1/chat/completions"
            ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        elapsed = time.time() - start
        output = proc.stdout.strip()
        
        result["time_ms"] = int(elapsed * 1000)
        
        # Parse HTTP status
        for line in output.split("\n"):
            if line.startswith("HTTP_STATUS:"):
                result["http_code"] = int(line.split(":")[1])
            elif line.startswith("{"):
                try:
                    body = json.loads(line)
                    if "error" in body:
                        result["error"] = str(body["error"])[:100]
                    elif "choices" in body or "content" in body:
                        result["status"] = "ok"
                    elif "base_resp" in body:
                        status_code = body.get("base_resp", {}).get("status_code", 0)
                        if status_code != 0:
                            result["error"] = f"status_code={status_code}"
                        else:
                            result["status"] = "ok"
                    else:
                        result["status"] = "ok"
                except:
                    result["status"] = "unknown"
        
        if "status" not in result:
            if "http_code" in result and result["http_code"] == 200:
                result["status"] = "ok"
            elif "error" not in result:
                result["error"] = f"HTTP {result.get('http_code', 'unknown')}"
        
    except subprocess.TimeoutExpired:
        result["error"] = "timeout"
        result["time_ms"] = 10000
    except Exception as e:
        result["error"] = str(e)[:80]
        result["time_ms"] = -1
    
    return result

def main():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    
    providers = cfg.get("models", {}).get("providers", {})
    
    # Resolve --type filter
    filter_type = None
    test_model = None
    for arg in sys.argv[1:]:
        if arg.startswith("--type="):
            filter_type = arg.split("=")[1]
        if arg.startswith("--model="):
            test_model = arg.split("=")[1]
    
    print("=" * 70)
    print("Model & Provider Health Check")
    print("=" * 70)
    
    results = []
    for pname in sorted(providers.keys()):
        pcfg = providers[pname]
        
        # Skip if filtering by type
        if filter_type:
            has_match = False
            for m in pcfg.get("models", []):
                mid = m.get("id", "")
                if filter_type in mid.lower() or filter_type in m.get("name", "").lower():
                    has_match = True
                    break
            if not has_match:
                continue
        
        if test_model:
            r = test_provider(pname, pcfg, test_model)
        else:
            # Test first model only for speed
            r = test_provider(pname, pcfg)
        
        if r:
            results.append(r)
            status_icon = "✅" if r.get("status") == "ok" else "❌"
            time_str = f"{r.get('time_ms', 0)}ms" if r.get('time_ms', 0) > 0 else "N/A"
            error = f" | {r.get('error', '')[:40]}" if r.get('error') else ""
            print(f"{status_icon} {pname:15s}/{r['model']:35s} {time_str:>8s}{error}")
    
    # Summary
    ok = sum(1 for r in results if r.get("status") == "ok")
    fail = len(results) - ok
    print(f"\n{'=' * 70}")
    print(f"Total: {len(results)} | ✅ OK: {ok} | ❌ Failed: {fail}")
    
    # List embedding models
    if not filter_type:
        print(f"\n{'=' * 70}")
        print("Embedding Models:")
        for pname, pcfg in sorted(providers.items()):
            for m in pcfg.get("models", []):
                mid = m.get("id", "")
                if "embed" in mid.lower():
                    print(f"  🟢 {pname}/{mid}")
        
        # Local Ollama
        for host, label in [("100.65.110.126", "Mac Studio"), ("100.104.252.33", "小m")]:
            try:
                proc = subprocess.run([
                    "curl", "-s", "--max-time", "3", "--noproxy", "*",
                    f"http://{host}:11434/api/tags"
                ], capture_output=True, text=True, timeout=5)
                if proc.returncode == 0:
                    tags = json.loads(proc.stdout)
                    for m in tags.get("models", []):
                        if "embed" in m.get("name", "").lower():
                            size_gb = m.get("size", 0) / (1024**3)
                            print(f"  🟢 {label} Ollama: {m['name']} ({size_gb:.1f}GB)")
            except:
                pass

if __name__ == "__main__":
    main()
