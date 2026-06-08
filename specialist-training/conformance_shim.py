#!/usr/bin/env python3
"""Conformance /verify shim — bridges the role-os gate contract to the Tool-Call Conformance watcher's
llama.cpp endpoint. The gate (role-os/src/specialist/client.mjs) POSTs /verify {adapter_id, role, input,
trace_id}; `input` carries the pre-serialized {evidence, claim} that conformance-consult.mjs built in the
trained EVIDENCE/CLAIM shape. Returns {verdict, score, adapter_id (MUST echo the pin), base_model,
duration_ms}. The DETERMINISTIC schema floor (L1-3) runs caller-side before this is ever hit — this shim
serves only the LLM ceiling (L4 semantic-contract, L5 intent).

Run alongside the served adapter: llama.cpp on :8094 (Qwen3-14B-Q4 + conformance-14b-soup @ --lora
scale 4), this shim on :8001. Register backend_url=http://localhost:8001."""
import json, time, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

LLAMA = "http://localhost:8094/v1/chat/completions"
BASE_MODEL = "Qwen/Qwen3-14B"
ADAPTER_ID = "conformance-14b-soup"   # the adapter this shim serves; gate fails open on a pin mismatch
SYS = ("You are a Tool-Call Conformance Verifier. Given a TOOL (its name, contract, and parameter "
       "schema) and a proposed CALL (the arguments), decide whether the call conforms to BOTH the "
       "schema and the tool's documented contract. Answer 'conformant' (every argument matches the "
       "schema and the contract), 'nonconformant' (some argument violates a type, a required field, "
       "an enum/range/format, or the documented contract, OR the call does not match the stated "
       "intent), or 'abstain' (the tool or call is underspecified — insufficient to judge). Reason "
       "briefly, then give the one-word verdict.")


def verdict_of(inp):
    user = f"EVIDENCE:\n{inp.get('evidence') or ''}\n\nCLAIM:\n{inp.get('claim') or ''}"
    body = json.dumps({"messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": user}],
                       "max_tokens": 320, "temperature": 0.1}).encode()
    req = urllib.request.Request(LLAMA, body, {"Content-Type": "application/json"})
    txt = json.loads(urllib.request.urlopen(req, timeout=30).read())["choices"][0]["message"]["content"]
    t = txt.split("</think>")[-1].lower()
    # ORDER MATTERS: 'nonconformant' contains 'conformant'; never read a bad call as conformant.
    for v in ("nonconformant", "abstain", "conformant"):
        if v in t:
            return v
    return "abstain"   # safe default — never the dangerous 'conformant'


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.rstrip("/") != "/verify":
            self.send_response(404); self.end_headers(); return
        t0 = time.time()
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            verdict = verdict_of(req.get("input") or {})
        except Exception as e:                              # transport/parse failure -> 500, gate fails open
            self.send_response(500); self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode()); return
        resp = {"verdict": verdict, "score": 0.9 if verdict != "abstain" else 0.5,
                "adapter_id": ADAPTER_ID, "base_model": BASE_MODEL,
                "duration_ms": int((time.time() - t0) * 1000)}
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(resp).encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("conformance-shim on :8001 -> conformance llama.cpp :8094", flush=True)
    HTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
