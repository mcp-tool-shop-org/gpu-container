#!/usr/bin/env python
"""S4c-2 — warm-start joint training (RUN-PLAN-s4c2.md).

Initializes the LoRA FROM the already-grokked solo budgeter soup (Omnigrok/Grokking-Tickets/
GrokTransfer warm-start rationale), then trains on conformance + 20% budgeter replay. The
proven recipe otherwise (rsLoRA r16/a32, lr 1e-4, wd 0.01 defaults, batch1 x accum16).

Args: <seed> [steps]
Env:  S4C2_INIT_ADAPTER (default budgeter-14b600-soup), S4C2_DATA, S4C2_VERIFY=1 -> load +
      warm-start + report tensor counts + exit WITHOUT training (preflight mechanics check).
"""
import os, sys
os.environ.setdefault("HF_HOME", "/mnt/e/AI-Models/hf-cache")
from backpropagate.config import settings

SEED = int(sys.argv[1])
STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 800
INIT = os.environ.get("S4C2_INIT_ADAPTER", "/mnt/e/AI-Models/adapters/budgeter-14b600-soup")
DATA = os.environ.get("S4C2_DATA", "/mnt/e/AI/gpu-container/specialist-training/data/s4c2_train_sft.jsonl")
VERIFY = os.environ.get("S4C2_VERIFY") == "1"

settings.lora.random_state = SEED
settings.lora.use_gradient_checkpointing = True

from backpropagate import Trainer
from safetensors.torch import load_file

OUT = f"/home/mikey/bp-runs/budgeter-s4c2-seed{SEED}"
t = Trainer(
    model="Qwen/Qwen3-14B",
    lora_r=16, lora_alpha=32, lora_dropout=0.05,
    learning_rate=1e-4, use_rslora=True,
    batch_size=int(os.environ.get("BUDGETER_BATCH", "1")),
    gradient_accumulation=int(os.environ.get("BUDGETER_ACCUM", "16")),
    optim="adamw_8bit", use_unsloth=False,
    packing=False, max_seq_length=1024,
    output_dir=OUT,
)
print(f"[cfg] warm-start from {INIT} | data={DATA} | seed={SEED} steps={STEPS}", flush=True)

t.load_model()

# ── warm-start: copy the grokked soup's A/B into the fresh PEFT adapter ────────────────────
src = load_file(os.path.join(INIT, "adapter_model.safetensors"))
params = dict(t.model.named_parameters())
copied, missed = 0, []
for k, v in src.items():
    if ".lora_" not in k:
        continue
    # source: ...lora_A.weight  ->  peft param: ...lora_A.default.weight
    pk = k.replace(".lora_A.weight", ".lora_A.default.weight").replace(".lora_B.weight", ".lora_B.default.weight")
    p = params.get(pk)
    if p is None or p.shape != v.shape:
        missed.append(k)
        continue
    with __import__("torch").no_grad():
        p.data.copy_(v.to(p.device, p.dtype))
    copied += 1
print(f"[warm-start] copied {copied} adapter tensors from {os.path.basename(INIT)}; missed {len(missed)}", flush=True)
if missed:
    print("[warm-start] FIRST MISSES:", missed[:4], flush=True)
if copied < 500:  # 280 modules x 2 tensors expected
    print("[warm-start] FATAL: too few tensors copied — key mapping wrong, refusing to train", flush=True)
    sys.exit(3)
if VERIFY:
    print("VERIFY_OK — warm-start mechanics confirmed, exiting without training", flush=True)
    sys.exit(0)

t.train(dataset=DATA, steps=STEPS, samples=1000)
saved = t.save(OUT)
print(f"DONE seed={SEED} steps={STEPS} saved={saved}", flush=True)
