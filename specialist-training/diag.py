#!/usr/bin/env python3
"""Sweep the LoRA apply-scale on one L1 puzzle to test the rsLoRA-vs-llama.cpp scaling mismatch:
if a higher scale (compensating alpha/sqrt(r)=8 vs baked alpha/r=2) produces a sensible answer, the
adapter is just served too weak — not undertrained."""
import json, urllib.request, collections
SYS = ("You are a Token Budget Analyst for an LLM agent studio. You reason about the token "
       "economics of agent dispatches under this cost model (weighted tokens): input ×1, "
       "cache-write ×1.25, cache-read ×0.1, output ×5. Work through the numbers, then "
       "give a short, exact answer.")
EXAM = "/mnt/e/AI/role-os/tools/token-budget-dataset/dataset/v0.1/puzzles/puzzles_exam.jsonl"
puz = [json.loads(l) for l in open(EXAM)]
by = collections.defaultdict(list)
for p in puz:
    by[p["level"]].append(p)


def post(path, body):
    req = urllib.request.Request("http://localhost:8090" + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=90).read())


l1 = by[1][0]
print(f"L1 gold={l1['answer']!r}")
for scale in (0.0, 1.0, 2.0, 4.0, 8.0):
    post("/lora-adapters", [{"id": 0, "scale": scale}])
    r = post("/v1/chat/completions", {"messages": [{"role": "system", "content": SYS},
                                                   {"role": "user", "content": l1["prompt"]}],
                                      "max_tokens": 200, "temperature": 0.1})
    out = r["choices"][0]["message"]["content"]
    print(f"  scale={scale}: {out[:140]!r}")
