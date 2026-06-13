#!/usr/bin/env python
"""Capture vector-caliper ModelState records for a list of LoRA adapter checkpoints (LLM form).

Same probe protocol as calibrate_cat.py — 24 held-out TRAIN probes (12/task, seed 42), the
certification exams are never touched. Per adapter: last-token hidden-state cloud geometry
(participation-ratio effDim, anisotropy, spread, density), native uncertainty (first answer
token entropy/margin), teacher-forced answer-token accuracy + CE. PEFT applies the adapters'
own rsLoRA scaling (use_rslora in adapter_config), so each checkpoint runs at trained
semantics.

Usage: python capture_llm_states.py <out_states.json> <label:adapter_dir> [<label:adapter_dir> ...]
  label is the caliper time axis: pass step numbers (e.g. 300:/path/ckpt-300).
"""
import json, os, random, sys
os.environ.setdefault("HF_HOME", "/mnt/e/AI-Models/hf-cache")
import numpy as np
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

TRAIN_A = "/mnt/e/AI/gpu-container/specialist-training/data/puzzles_train_sft.jsonl"
TRAIN_B = "/mnt/e/AI/role-os/tools/conformance-dataset/conformance_train_sft.jsonl"
N_PROBE_PER_TASK = 12
SEED = 42
SEQ = 1024

OUT = sys.argv[1]
CKPTS = [a.split(":", 1) for a in sys.argv[2:]]
assert CKPTS, "pass at least one label:adapter_dir"

random.seed(SEED)
dev = "cuda"
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-14B")
base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3-14B",
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                                           bnb_4bit_quant_type="nf4"),
    device_map={"": 0}, attn_implementation="sdpa",
)
base.eval()

def load_sft(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line)["messages"])
    return rows

dsA, dsB = load_sft(TRAIN_A), load_sft(TRAIN_B)
random.shuffle(dsA); random.shuffle(dsB)
probes = dsA[:N_PROBE_PER_TASK] + dsB[:N_PROBE_PER_TASK]

def encode(msgs):
    prompt_txt = tok.apply_chat_template(msgs[:-1], add_generation_prompt=True, tokenize=False)
    full_txt = tok.apply_chat_template(msgs, add_generation_prompt=False, tokenize=False)
    prompt_ids = tok(prompt_txt, add_special_tokens=False).input_ids
    full_ids = tok(full_txt, add_special_tokens=False).input_ids[:SEQ]
    labels = [-100] * len(full_ids)
    for i in range(min(len(prompt_ids), len(full_ids)), len(full_ids)):
        labels[i] = full_ids[i]
    return full_ids, labels

@torch.no_grad()
def capture(model, label):
    feats, accs, ents, margins, losses = [], [], [], [], []
    for m in probes:
        f, l = encode(m)
        out = model(input_ids=torch.tensor([f], device=dev),
                    labels=torch.tensor([l], device=dev), output_hidden_states=True)
        losses.append(out.loss.float().item())
        feats.append(out.hidden_states[-1][0, -1].float().cpu())
        logits = out.logits[0].float()
        ans_idx = [i for i, t in enumerate(l) if t != -100]
        if ans_idx:
            pred = logits[[i - 1 for i in ans_idx]].argmax(-1)
            gold = torch.tensor([l[i] for i in ans_idx])
            accs.append((pred.cpu() == gold).float().mean().item())
            p = torch.softmax(logits[ans_idx[0] - 1], -1)
            top2 = torch.topk(p, 2).values
            ents.append(float(-(p * (p + 1e-12).log2()).sum()))
            margins.append(float(top2[0] - top2[1]))
    X = torch.stack(feats).numpy()
    Xc = X - X.mean(0)
    ev = np.linalg.eigvalsh(np.cov(Xc.T))[::-1]
    ev = ev[ev > 1e-9]
    dists = np.sqrt(((X[:, None] - X[None, :]) ** 2).sum(-1))
    nn = np.partition(dists + np.eye(len(X)) * 1e9, 0, axis=1)[:, 0]
    return {
        "id": f"joint-step-{label}", "time": int(label),
        "geometry": {"effectiveDimension": float(ev.sum() ** 2 / (ev ** 2).sum()),
                     "anisotropy": float(ev[0] / ev[-1]) if len(ev) > 1 else 1.0,
                     "spread": float(dists[np.triu_indices(len(X), 1)].mean()),
                     "density": float(len(X) / (1 + nn.mean()))},
        "uncertainty": {"entropy": float(np.mean(ents)), "margin": float(np.mean(margins)),
                        "calibration": float(np.std(accs))},
        "performance": {"accuracy": float(np.mean(accs)), "loss": float(np.mean(losses))},
        "metadata": {"source": "budgeter-conformance JOINT data-mixed retrain (Qwen3-14B 4-bit, RTX 5090)",
                     "version": "1.0.0",
                     "tags": [f"n={len(X)}", "last-token-hidden", "native-uncertainty", "peft-rslora-scaling"]},
    }

states = []
for label, path in CKPTS:
    model = PeftModel.from_pretrained(base, path)
    model.eval()
    st = capture(model, label)
    states.append(st)
    print(f"[{label}] acc={st['performance']['accuracy']:.3f} ce={st['performance']['loss']:.3f} "
          f"effDim={st['geometry']['effectiveDimension']:.2f} spread={st['geometry']['spread']:.2f}", flush=True)
    model = model.unload()  # strip adapter, keep base for the next checkpoint

with open(OUT, "w") as f:
    json.dump(states, f, indent=1)
print(f"states -> {OUT}", flush=True)
