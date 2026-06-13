#!/usr/bin/env python
"""L2 proxy gate (S4c-2 inter-seed ANDON) — score adapters on TRAIN-split L2 puzzles only.

The certification exam stays sealed. This scores accuracy + flip-consistency on the L2 rung's
TRAIN items (contrast-paired), giving the basin-held / basin-broken verdict for the warm-started
adapter against its source. Reference scale: the warm-start source (budgeter-14b600-soup) is the
ceiling; a fresh base would sit at chance.

Usage: python l2_proxy.py <n_pairs> <label:adapter_dir> [<label:adapter_dir> ...]
"""
import json, os, random, re, sys
os.environ.setdefault("HF_HOME", "/mnt/e/AI-Models/hf-cache")
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

TRAIN = "/mnt/e/AI/role-os/tools/token-budget-dataset/dataset/v0.1/puzzles/puzzles_train.jsonl"
SYS = ("You are a Token Budget Analyst for an LLM agent studio. You reason about the token "
       "economics of agent dispatches under this cost model (weighted tokens): input ×1, "
       "cache-write ×1.25, cache-read ×0.1, output ×5. Work through the numbers, then "
       "give a short, exact answer.")

N_PAIRS = int(sys.argv[1])
CKPTS = [a.split(":", 1) for a in sys.argv[2:]]

rows = [json.loads(l) for l in open(TRAIN) if l.strip()]
l2 = [r for r in rows if int(r.get("level", 0)) == 2 and r.get("split") == "train" and r.get("pair_id")]
by_pair = {}
for r in l2:
    by_pair.setdefault(r["pair_id"], []).append(r)
pairs = [v for v in by_pair.values() if len(v) >= 2]
random.Random(7).shuffle(pairs)
pairs = pairs[:N_PAIRS]
items = [r for p in pairs for r in p]
print(f"[data] {len(pairs)} L2 contrast pairs ({len(items)} items) from TRAIN split", flush=True)

dev = "cuda"
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-14B")
base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-14B",
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                                           bnb_4bit_quant_type="nf4"),
    device_map={"": 0}, attn_implementation="sdpa",
)
base.eval()

def answer(model, prompt):
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": prompt}]
    # thinking stays ENABLED — certify.py's harness lets the model reason then splits on
    # </think>; gagging it cratered the reference's L2 score (caught by the control 2026-06-12)
    text = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    ids = tok(text, return_tensors="pt").to(dev)
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=320, do_sample=False, temperature=None, top_p=None,
                             pad_token_id=tok.eos_token_id)
    full = tok.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True)
    if "</think>" in full:
        full = full.split("</think>")[-1]
    return full.strip()

def correct(pred, gold):
    p = re.sub(r"[^a-z0-9 ]", " ", pred.lower())
    m = re.search(r"\b([ab])\b", p)
    return bool(m) and m.group(1) == str(gold).strip().lower()

for label, path in CKPTS:
    model = PeftModel.from_pretrained(base, path)
    model.eval()
    hits = {}
    for r in items:
        hits[r["id"]] = correct(answer(model, r["prompt"]), r["answer"])
    acc = sum(hits.values()) / len(hits)
    flip = sum(all(hits[r["id"]] for r in p) for p in pairs) / len(pairs)
    print(f"[{label}] L2-train acc={acc:.3f} flip-consistency={flip:.3f} (n={len(items)}, pairs={len(pairs)})", flush=True)
    model = model.unload()
