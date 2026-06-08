#!/usr/bin/env python3
"""Transform the puzzle curriculum into OpenAI-messages SFT (the format backpropagate detects).
user = puzzle prompt; assistant = <think>worked reasoning</think> + the verifiable answer.
The system prompt states the cost model (the weights) but NOT the heuristic conclusion — that's
what the puzzles teach (and L2 'which-costs-more' is a trap that punishes the naive heuristic)."""
import json, os

SYS = (
    "You are a Token Budget Analyst for an LLM agent studio. You reason about the token "
    "economics of agent dispatches under this cost model (weighted tokens): input ×1, "
    "cache-write ×1.25, cache-read ×0.1, output ×5. Work through the numbers, then give a "
    "short, exact answer."
)
SRC = "/mnt/e/AI/role-os/tools/token-budget-dataset/dataset/v0.1/puzzles/puzzles_train.jsonl"
OUT = "/mnt/e/AI/gpu-container/specialist-training/data/puzzles_train_sft.jsonl"

os.makedirs(os.path.dirname(OUT), exist_ok=True)
n = 0
by_level = {}
with open(SRC) as f, open(OUT, "w") as g:
    for line in f:
        line = line.strip()
        if not line:
            continue
        p = json.loads(line)
        reasoning = str(p["reasoning"]).strip()
        answer = str(p["answer"]).strip()
        assistant = f"<think>\n{reasoning}\n</think>\n\n{answer}"
        rec = {"messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": p["prompt"]},
            {"role": "assistant", "content": assistant},
        ]}
        g.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n += 1
        by_level[p.get("level")] = by_level.get(p.get("level"), 0) + 1

print(f"wrote {n} SFT examples -> {OUT}")
print("by level:", dict(sorted(by_level.items())))
print("--- sample record (level 2 trap if present) ---")
# re-read one example to echo
with open(OUT) as g:
    first = json.loads(g.readline())
print(json.dumps(first, ensure_ascii=False, indent=2)[:1200])
