#!/usr/bin/env python
"""Prove bitsandbytes 4-bit actually loads + runs the cached base on this cu128/sm_120 stack,
BEFORE committing a training run. Loads unsloth/Qwen3-4B-bnb-4bit (pre-quantized NF4), runs one
short generate, reports VRAM. This is the critical de-risk: bnb importing != bnb 4-bit working."""
import os, time, torch
os.environ.setdefault("HF_HOME", "/mnt/e/AI-Models/hf-cache")
import bitsandbytes as bnb
from transformers import AutoModelForCausalLM, AutoTokenizer

MID = "unsloth/Qwen3-4B-bnb-4bit"
print(f"torch {torch.__version__} cuda={torch.cuda.is_available()} bnb={bnb.__version__}")
print(f"gpu={torch.cuda.get_device_name(0)} cap={torch.cuda.get_device_capability(0)}")

tok = AutoTokenizer.from_pretrained(MID)
t0 = time.time()
model = AutoModelForCausalLM.from_pretrained(MID, device_map="cuda")
print(f"loaded in {time.time()-t0:.1f}s | vram {torch.cuda.memory_allocated()/2**20:.0f} MiB "
      f"| reserved {torch.cuda.memory_reserved()/2**20:.0f} MiB")

enc = tok.apply_chat_template(
    [{"role": "user", "content": "Reply with exactly one word: ok"}],
    add_generation_prompt=True, return_tensors="pt", return_dict=True,
).to("cuda")
t1 = time.time()
with torch.no_grad():
    out = model.generate(**enc, max_new_tokens=8, do_sample=False)
n = enc["input_ids"].shape[1]
print(f"generate ok in {time.time()-t1:.1f}s | out={tok.decode(out[0][n:], skip_special_tokens=True)!r}")
print(f"peak vram {torch.cuda.max_memory_allocated()/2**20:.0f} MiB")
print("BNB_4BIT_OK")
