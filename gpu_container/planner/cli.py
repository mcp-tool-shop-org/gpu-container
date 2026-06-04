"""`gpu-container-plan` — turn a profile (+ model) into a llama.cpp `--n-cpu-moe` placement plan.

  gpu-container-plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m --ctx 4096

Exit code is verdict-coded (ANDON): 0 = ship, 3 = refuse. The profile.json comes from
`gpu-container-profile` (run in-container for honest VRAM/CPU-bandwidth inputs).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from ..profiler import model as model_mod
from ..profiler.schema import Profile
from .placement import plan_llama_cpp


def main(argv: Optional[List[str]] = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        prog="gpu-container-plan",
        description="Plan an MoE placement (llama.cpp --n-cpu-moe) from a rig+model profile.",
    )
    ap.add_argument("--profile", required=True, help="profile.json from gpu-container-profile")
    ap.add_argument("--model-config", help="HF config.json to (re)profile the model side into the plan")
    ap.add_argument("--model-name", help="override the model name")
    ap.add_argument("--quant", help="quant tag, e.g. gguf-q4_k_m (drives bytes/weight + footprint)")
    ap.add_argument("--ctx", type=int, default=4096, help="context length for the KV-cache budget")
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--cpu-bw", type=float, help="override CPU RAM bandwidth (GB/s)")
    ap.add_argument("--floor", type=float, default=1.0, help="refuse below this decode tok/s")
    ap.add_argument("--hf", help="model ref for the launch command, e.g. unsloth/Qwen3-30B-A3B-GGUF:Q4_K_M")
    ap.add_argument("-o", "--out", help="write the plan JSON here (default: stdout)")
    args = ap.parse_args(argv)

    with open(args.profile, "r", encoding="utf-8") as f:
        prof = Profile.from_json(f.read())

    if args.model_config:
        with open(args.model_config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        prof.model = model_mod.analyze_config(cfg, name=args.model_name, quant=args.quant or "gguf-q4_k_m")
    elif args.quant and prof.model is not None:
        prof.model.quant = args.quant

    plan = plan_llama_cpp(
        prof, ctx_len=args.ctx, batch=args.batch,
        cpu_mem_bw_gbps=args.cpu_bw, floor_tok_s=args.floor, model_ref=args.hf,
    )

    js = plan.to_json()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(js + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(js)
    print(plan.message, file=sys.stderr)
    return 0 if plan.verdict == "ship" else 3


if __name__ == "__main__":
    raise SystemExit(main())
