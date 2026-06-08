#!/usr/bin/env python
"""Model-soup N LoRA adapters the CORRECT way (study-swarm recipe; AdapterHub lora_delta_w_svd /
Compress-then-Serve arXiv:2407.00066): average the per-layer update ΔW = B·A in MERGED weight space,
NEVER the A/B factors (averaging factors injects A_i·B_j cross-terms that are meaningless). Then
SVD-truncate the averaged ΔW back to rank r. Served at the same rsLoRA scale, the soup applies the
mean update — variance-reducing across seeds (Wortsman 2022 model soups).

Args: <out_dir> <adapterA_dir> <adapterB_dir> [<adapterC_dir> ...]   (>=2 inputs)
"""
import sys, os, shutil
import torch
from safetensors.torch import load_file, save_file

OUT = sys.argv[1]
IN_DIRS = sys.argv[2:]
assert len(IN_DIRS) >= 2, "need >=2 input adapters to soup"
R = 16
dev = "cuda" if torch.cuda.is_available() else "cpu"

states = [load_file(os.path.join(d, "adapter_model.safetensors")) for d in IN_DIRS]
keys0 = set(states[0])
for s in states[1:]:
    assert set(s) == keys0, "adapter key mismatch — soup requires identical module sets"
prefixes = sorted({k.rsplit(".lora_", 1)[0] for k in keys0 if ".lora_" in k})

out = {}
for p in prefixes:
    ak, bk = f"{p}.lora_A.weight", f"{p}.lora_B.weight"
    dtype = states[0][bk].dtype
    dW = None
    for s in states:
        A = s[ak].to(dev, torch.float32)          # [r, in]
        B = s[bk].to(dev, torch.float32)          # [out, r]
        d = B @ A                                  # [out, in]
        dW = d if dW is None else dW + d
    dW /= len(states)                              # mean update
    U, S, Vh = torch.linalg.svd(dW, full_matrices=False)
    U, S, Vh = U[:, :R], S[:R], Vh[:R, :]
    sq = torch.sqrt(S)
    out[bk] = (U * sq).to(dtype).cpu().contiguous()          # [out, R]
    out[ak] = (sq.unsqueeze(1) * Vh).to(dtype).cpu().contiguous()  # [R, in]
    del dW

for k in keys0:                                    # carry any non-lora tensors unchanged
    if ".lora_" not in k and k not in out:
        out[k] = states[0][k]

os.makedirs(OUT, exist_ok=True)
save_file(out, os.path.join(OUT, "adapter_model.safetensors"))
shutil.copy(os.path.join(IN_DIRS[0], "adapter_config.json"), os.path.join(OUT, "adapter_config.json"))
print(f"SOUP {len(prefixes)} layers from {len(IN_DIRS)} adapters, dev={dev} -> {OUT}", flush=True)
