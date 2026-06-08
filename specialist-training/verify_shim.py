#!/usr/bin/env python3
"""Specialist /verify shim — bridges the role-os gate contract to the budgeter's llama.cpp endpoint.

The gate (role-os/src/specialist/client.mjs) POSTs /verify {adapter_id, role, input, trace_id} and
expects {verdict, score, adapter_id (MUST echo the pinned id), base_model, duration_ms}. The budgeter
(Token Budget Analyst) estimates the weighted-token spend of an upcoming dispatch from its learned cost
model (input ×1, cache-write ×1.25, cache-read ×0.1, output ×5; cache-read = context re-read each step).

Run alongside the served adapter: llama.cpp on :8090 (Qwen3-14B-Q4 + budgeter-14b600-soup @ --lora
scale 4), this shim on :8000. Register backend_url=http://localhost:8000.
"""
import json, re, time, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

LLAMA = "http://localhost:8090/v1/chat/completions"
BASE_MODEL = "Qwen/Qwen3-14B"
ADAPTER_ID = "budgeter-14b600-soup"   # the adapter this shim actually serves
SYS = ("You are a Token Budget Analyst for an LLM agent studio. You reason about the token "
       "economics of agent dispatches under this cost model (weighted tokens): input ×1, "
       "cache-write ×1.25, cache-read ×0.1, output ×5. Work through the numbers, then "
       "give a short, exact answer.")


def estimate_spend(inp):
    ctx = int(inp.get("context_tokens") or 0)
    steps = int(inp.get("steps") or 1)
    out = int(inp.get("output_estimate") or 0)
    q = (f"A dispatch will re-read ~{ctx:,} tokens of context over ~{steps} steps and write "
         f"~{out:,} output tokens. Estimate the TOTAL weighted-token spend. Give one number.")
    body = json.dumps({"messages": [{"role": "system", "content": SYS},
                                    {"role": "user", "content": q}],
                       "max_tokens": 320, "temperature": 0.1}).encode()
    req = urllib.request.Request(LLAMA, body, {"Content-Type": "application/json"})
    txt = json.loads(urllib.request.urlopen(req, timeout=8).read())["choices"][0]["message"]["content"]
    ans = txt.split("</think>")[-1]
    nums = re.findall(r"\d[\d,]*", ans)            # numbers in the terse answer
    spend = int(nums[-1].replace(",", "")) if nums else None
    return spend


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.rstrip("/") != "/verify":
            self.send_response(404); self.end_headers(); return
        t0 = time.time()
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            spend = estimate_spend(req.get("input") or {})
        except Exception as e:                      # transport/parse failure -> 500, gate fails open
            self.send_response(500); self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode()); return
        resp = {
            "verdict": {"spend_weighted": spend},
            "score": 0.9 if spend is not None else 0.2,   # informational; gate routes on its own classifier
            "adapter_id": ADAPTER_ID,                      # the adapter we serve; gate fails open if it != the pinned id
            "base_model": BASE_MODEL,
            "duration_ms": int((time.time() - t0) * 1000),
        }
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(resp).encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("verify-shim on :8000 -> budgeter llama.cpp :8090", flush=True)
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
