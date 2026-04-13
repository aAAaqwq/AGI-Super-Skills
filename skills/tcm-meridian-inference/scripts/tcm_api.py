#!/usr/bin/env python3
"""TCM Meridian Inference HTTP API - Python 3.6+ compatible"""
import json, sys, os, signal
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from importlib import util as importlib_util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
INFER_SCRIPT = os.path.join(SCRIPT_DIR, "infer.py")
RULES_DIR = os.path.join(PROJECT_DIR, "rules")
PORT = int(os.environ.get("TCM_API_PORT", 18790))

_infer_mod = None
_thresholds = None
_meridian_rules = None
_combo_rules = None


def load_infer():
    global _infer_mod
    if _infer_mod is not None:
        return _infer_mod
    spec = importlib_util.spec_from_file_location("infer", INFER_SCRIPT)
    _infer_mod = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(_infer_mod)
    return _infer_mod


def load_rules():
    global _thresholds, _meridian_rules, _combo_rules
    if _thresholds is not None:
        return
    with open(os.path.join(RULES_DIR, "thresholds.json")) as f:
        _thresholds = json.load(f)
    with open(os.path.join(RULES_DIR, "meridian_rules.json")) as f:
        _meridian_rules = json.load(f)
    with open(os.path.join(RULES_DIR, "combination_rules.json")) as f:
        _combo_rules = json.load(f)


def run_inference(payload):
    load_rules()
    mod = load_infer()
    return mod.infer(payload, _thresholds, _meridian_rules, _combo_rules)


SAMPLE_DATA = {
    "measurements": {
        "liver": {"left": 34.5, "right": 34.3},
        "heart": {"left": 35.0, "right": 34.8},
        "spleen": {"left": 34.8, "right": 34.6},
        "kidney": {"left": 33.5, "right": 34.2},
        "stomach": {"left": 34.0, "right": 34.5},
        "gallbladder": {"left": 34.2, "right": 34.0},
        "bladder": {"left": 33.8, "right": 34.8}
    }
}


class TCMHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/health", "/healthz"):
            self._json({"status": "ok", "service": "tcm-meridian-api", "python": sys.version})
        elif path == "/":
            self._json({
                "service": "TCM Meridian Inference API",
                "version": "0.3.0",
                "endpoints": {
                    "POST /": "Run inference (legacy)",
                    "POST /test": "Run with sample data",
                    "GET /health": "Health check (legacy)",
                    "GET /healthz": "Health check",
                    "POST /api/inference/meridian-diagnosis": "Run inference"
                },
                "meridians": ["liver", "spleen", "kidney", "stomach", "gallbladder", "bladder"]
            })
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/test":
                payload = SAMPLE_DATA
            elif path in ("/", "/api/inference/meridian-diagnosis"):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                payload = json.loads(body)
            else:
                self._json({"error": "not found"}, 404)
                return

            result = run_inference(payload)
            self._json(result)
        except ValueError as e:
            self._json({"error": "invalid JSON: " + str(e)}, 400)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def log_message(self, fmt, *args):
        pass  # suppress logs


def main():
    server = HTTPServer(("0.0.0.0", PORT), TCMHandler)
    print("TCM API on 0.0.0.0:%d" % PORT, flush=True)

    def shutdown(sig, frame):
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    server.serve_forever()


if __name__ == "__main__":
    main()
