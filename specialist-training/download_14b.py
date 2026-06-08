#!/usr/bin/env python
"""Pull the Qwen3-14B HF base into the shared hf-cache for QLoRA training (serving uses the Q4 GGUF
already on disk; training needs the full bf16 safetensors)."""
import os
os.environ.setdefault("HF_HOME", "/mnt/e/AI-Models/hf-cache")
from huggingface_hub import snapshot_download
p = snapshot_download("Qwen/Qwen3-14B")
print("SNAP", p, flush=True)
