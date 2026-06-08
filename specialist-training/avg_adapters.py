#!/usr/bin/env python
"""Model-soup: average the two seed adapters' tensors (Wortsman ICML 2022 / AdapterSoup EACL 2023).
No retrain — should land between the seeds and pull the phase-boundary rung (L5 0.54) up. The two
adapters share config (r16, all-linear) so tensors align 1:1."""
import os, shutil
from safetensors.torch import load_file, save_file

A = "/home/mikey/bp-runs/budgeter-v0.1-seed42"
B = "/home/mikey/bp-runs/budgeter-v0.1-seed1337"
OUT = "/mnt/e/AI-Models/adapters/budgeter-v0.1-soup"

a = load_file(f"{A}/adapter_model.safetensors")
b = load_file(f"{B}/adapter_model.safetensors")
assert set(a) == set(b), "adapter tensor keys differ — not soup-able"
soup = {k: (a[k] + b[k]) / 2 for k in a}

os.makedirs(OUT, exist_ok=True)
shutil.copy(f"{A}/adapter_config.json", f"{OUT}/adapter_config.json")
save_file(soup, f"{OUT}/adapter_model.safetensors")
print(f"souped {len(soup)} tensors (seed42 + seed1337)/2 -> {OUT}")
