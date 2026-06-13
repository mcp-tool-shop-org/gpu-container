#!/usr/bin/env python
"""Token Budget Analyst — Python Trainer API. Model-parametric: 4B baseline, or 14B for the
quantitative rungs (L1/L2) where a 4B is at chance. Args: <seed> [steps].
Env: BUDGETER_BASE (default Qwen/Qwen3-4B), BUDGETER_TAG (default v0.1), BUDGETER_CKPT=1 to force
gradient checkpointing (sqrt(L) activations) if a config-test shows VRAM is tight.

14B at batch_size=1 + gradient_accumulation=16 keeps the effective batch at 16 (matching the 4B run)
while bounding peak VRAM to one sequence's activations (~18GB est on a 4-bit base) — safe in 32GB.
(backpropagate's pydantic env-var override for nested config is broken — alpha/seed/ckpt set via
direct mutation + Trainer kwargs, the reliable path.)
"""
import os, sys
os.environ.setdefault("HF_HOME", "/mnt/e/AI-Models/hf-cache")
from backpropagate.config import settings

SEED = int(sys.argv[1])
STEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 300
MODEL = os.environ.get("BUDGETER_BASE", "Qwen/Qwen3-4B")
TAG = os.environ.get("BUDGETER_TAG", "v0.1")
BIG = "14B" in MODEL or "14b" in MODEL

settings.lora.random_state = SEED  # seed knob (direct mutation; env override is broken)
if BIG or os.environ.get("BUDGETER_CKPT") == "1":
    settings.lora.use_gradient_checkpointing = True  # 14B at batch4 needs sqrt(L) activations to fit
# study-swarm flagged weight-decay as the grokking lever — but bumping it to 0.05 (+ ~10% warmup)
# OVER-regularized the computation rungs: L5 flip fell 1.0→~0.4 and L2 flip dropped, on BOTH seeds.
# The 600-step run at backpropagate's defaults (wd 0.01, warmup 10) was the sweet spot — MORE STEPS,
# not more wd, is what crossed L2's grokking transition (the diagnostic: seed1337 0.944/0.866). Defaults.

from backpropagate import Trainer

OUT = (f"/home/mikey/bp-runs/budgeter-{TAG}-seed{SEED}" if STEPS > 5
       else f"/home/mikey/bp-runs/cfgtest-{TAG}-seed{SEED}")
# Data-parametric (kickoff assumed this; it was hardcoded). BUDGETER_DATA points the same proven recipe
# at any SFT (e.g. the Verifier groundedness SFT). Default = the budgeter puzzles (backward-compatible).
DATA = os.environ.get(
    "BUDGETER_DATA",
    "/mnt/e/AI/gpu-container/specialist-training/data/puzzles_train_sft.jsonl",
)

t = Trainer(
    model=MODEL,
    lora_r=16, lora_alpha=32, lora_dropout=0.05,   # alpha=32 = 2r
    learning_rate=1e-4,                # study-swarm: 2e-4 was too high for a 4B
    use_rslora=True,                   # Kalajdzievski 2023: rank-stable scale at r16 (serve @ scale 4)
    batch_size=int(os.environ.get("BUDGETER_BATCH", "4")),        # eff batch held at 16 via accum; 14B
    gradient_accumulation=int(os.environ.get("BUDGETER_ACCUM", "4")),  # fits batch4 (short seq) — drop to
    # BUDGETER_BATCH=2 BUDGETER_ACCUM=8 when sequences are long & VRAM is tight (e.g. conformance schemas).
    optim="adamw_8bit", use_unsloth=False,
    packing=False, max_seq_length=1024,
    output_dir=OUT,
)
print(f"[cfg] model={MODEL} r={t.lora_r} alpha={t.lora_alpha} batch={t.batch_size} "
      f"accum={t.gradient_accumulation} ckpt={settings.lora.use_gradient_checkpointing} "
      f"seq={t.max_seq_length} seed={settings.lora.random_state} steps={STEPS} out={OUT}", flush=True)
t.train(dataset=DATA, steps=STEPS, samples=int(os.environ.get("BUDGETER_SAMPLES", "2000")))
saved = t.save(OUT)  # train() only writes checkpoints; save() writes the final adapter
print(f"DONE seed={SEED} steps={STEPS} saved={saved}", flush=True)
