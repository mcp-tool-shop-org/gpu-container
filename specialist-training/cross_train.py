#!/usr/bin/env python
"""Cross-train two LoRA specialists (role-os specialists layer S4, design/specialists-layer.md).

Two stages, run in order, both receipt-emitting:

1. COMPATIBILITY READOUT (always runs first — design finding 11, TIES interference):
   per-module ΔW = B·A for each parent; trim each to its top-k% magnitude entries
   (TIES trim, k=20); report sign-agreement on the surviving intersection, overlap,
   Frobenius norms, and global cosine. A real number BEFORE any merge.

2. TIES MERGE (skill UNION — finding 12: A-and-B, never novel-C):
   elementwise on trimmed values: elect sign by summed magnitude, disjoint-mean the
   values matching the elected sign; SVD-truncate the merged ΔW back to rank r
   (same merged-space discipline as soup_adapters.py — never average A/B factors);
   report the SVD truncation residual honestly.

The EXAM gates the birth, not this script: the merged adapter must clear the
preregistered bars on BOTH parents' exams before it may be registered
(findings 13, 16 — failure is a designed outcome; every attempt is recorded).

Usage: python cross_train.py <out_dir> <adapterA_dir> <adapterB_dir> [--trim 0.20] [--rank 16]
       [--report <report.json>] [--readout-only]
"""
import argparse, json, os, shutil, sys
import torch
from safetensors.torch import load_file, save_file

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("adapter_a")
ap.add_argument("adapter_b")
ap.add_argument("--trim", type=float, default=0.20, help="keep top fraction by |magnitude| per task vector (TIES)")
ap.add_argument("--rank", type=int, default=16)
ap.add_argument("--method", choices=["ties", "add"], default="ties",
                help="'add' = plain task-vector addition (Ilharco) — the right operation in the "
                     "orthogonal/low-interference regime the readout detects; preserves rank<=2r "
                     "exactly. 'ties' = trim/sign-elect/disjoint-mean — for high-interference pairs.")
ap.add_argument("--alpha", type=float, default=None,
                help="lora_alpha to write into the output adapter_config (serving-scale parity); "
                     "default keeps parent config untouched")
ap.add_argument("--report", default=None)
ap.add_argument("--readout-only", action="store_true")
args = ap.parse_args()

dev = "cuda" if torch.cuda.is_available() else "cpu"
sa = load_file(os.path.join(args.adapter_a, "adapter_model.safetensors"))
sb = load_file(os.path.join(args.adapter_b, "adapter_model.safetensors"))
assert set(sa) == set(sb), "adapter key mismatch — cross-train requires identical module sets"
prefixes = sorted({k.rsplit(".lora_", 1)[0] for k in sa if ".lora_" in k})

def delta(state, p):
    A = state[f"{p}.lora_A.weight"].to(dev, torch.float32)
    B = state[f"{p}.lora_B.weight"].to(dev, torch.float32)
    return B @ A

def trim_mask(dw, keep):
    flat = dw.abs().flatten()
    k = max(1, int(flat.numel() * keep))
    thresh = torch.kthvalue(flat, flat.numel() - k + 1).values
    return dw.abs() >= thresh

per_module = []
out_state = {}
agree_n = agree_hit = 0
sq_res_num = sq_norm_den = 0.0

for p in prefixes:
    dA, dB = delta(sa, p), delta(sb, p)
    mA, mB = trim_mask(dA, args.trim), trim_mask(dB, args.trim)
    tA, tB = dA * mA, dB * mB

    inter = mA & mB
    n_inter = int(inter.sum())
    n_union = int((mA | mB).sum())
    agree = int(((torch.sign(dA) == torch.sign(dB)) & inter).sum())
    cos = torch.nn.functional.cosine_similarity(dA.flatten(), dB.flatten(), dim=0).item()
    row = {
        "module": p.split("base_model.model.")[-1],
        "sign_agreement_on_overlap": round(agree / n_inter, 4) if n_inter else None,
        "overlap_jaccard": round(n_inter / n_union, 4) if n_union else 0.0,
        "cosine": round(cos, 4),
        "fro_a": round(dA.norm().item(), 3),
        "fro_b": round(dB.norm().item(), 3),
    }
    agree_n += n_inter; agree_hit += agree
    per_module.append(row)

    if not args.readout_only:
        if args.method == "add":
            # Task-vector addition: both updates at trained strength. Exact union for
            # orthogonal pairs; rank(merged) <= rank_a + rank_b, so SVD at that rank is lossless.
            merged = dA + dB
        else:
            # TIES: elected sign = sign of summed trimmed values; disjoint mean over matching values.
            total = tA + tB
            elected = torch.sign(total)
            keepA = (torch.sign(tA) == elected) & mA
            keepB = (torch.sign(tB) == elected) & mB
            contrib = keepA.to(torch.float32) + keepB.to(torch.float32)
            merged = (tA * keepA + tB * keepB) / contrib.clamp(min=1.0)

        U, S, Vh = torch.linalg.svd(merged, full_matrices=False)
        r = args.rank
        Ur, Sr, Vhr = U[:, :r], S[:r], Vh[:r, :]
        approx = (Ur * Sr) @ Vhr
        sq_res_num += (merged - approx).norm().item() ** 2
        sq_norm_den += merged.norm().item() ** 2

        dtype = sa[f"{p}.lora_B.weight"].dtype
        sqv = torch.sqrt(Sr)
        out_state[f"{p}.lora_B.weight"] = (Ur * sqv).to(dtype).cpu().contiguous()
        out_state[f"{p}.lora_A.weight"] = (sqv.unsqueeze(1) * Vhr).to(dtype).cpu().contiguous()
    del dA, dB

aggregate = {
    "parents": {"a": os.path.basename(args.adapter_a.rstrip("/\\")), "b": os.path.basename(args.adapter_b.rstrip("/\\"))},
    "method": (f"add-r{args.rank}" if args.method == "add" else f"ties-trim{int(args.trim * 100)}-r{args.rank}"),
    "modules": len(prefixes),
    "sign_agreement_on_overlap": round(agree_hit / agree_n, 4) if agree_n else None,
    "mean_cosine": round(sum(m["cosine"] for m in per_module) / len(per_module), 4),
    "mean_overlap_jaccard": round(sum(m["overlap_jaccard"] for m in per_module) / len(per_module), 4),
}
if not args.readout_only:
    aggregate["svd_truncation_residual"] = round((sq_res_num ** 0.5) / (sq_norm_den ** 0.5), 4) if sq_norm_den else None

print("COMPATIBILITY READOUT")
print(json.dumps(aggregate, indent=1))

if not args.readout_only:
    os.makedirs(args.out, exist_ok=True)
    for k in sa:
        if ".lora_" not in k and k not in out_state:
            out_state[k] = sa[k]
    save_file(out_state, os.path.join(args.out, "adapter_model.safetensors"))
    with open(os.path.join(args.adapter_a, "adapter_config.json")) as f:
        cfg = json.load(f)
    cfg["r"] = args.rank
    if args.alpha is not None:
        # Serving-scale parity note: convert_lora_to_gguf bakes alpha/r; with alpha = 2*rank the
        # baked factor stays 2 and the fleet-standard llama.cpp `--lora` scale 4.0 reproduces the
        # parents' trained rsLoRA strength (alpha/sqrt(16) = 8). PEFT-resume semantics differ at
        # this alpha — rescale before any continued training.
        cfg["lora_alpha"] = args.alpha
    with open(os.path.join(args.out, "adapter_config.json"), "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"MERGED -> {args.out} (r={cfg['r']}, alpha={cfg.get('lora_alpha')})")

if args.report:
    with open(args.report, "w") as f:
        json.dump({"aggregate": aggregate, "per_module": per_module}, f, indent=1)
    print(f"REPORT -> {args.report}")
