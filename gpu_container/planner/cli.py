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

from ..errors import GpuContainerError, guard
from ..profiler import model as model_mod
from ..profiler.schema import Profile
from .calibration import CalibrationModel, CalibrationStore
from .placement import plan_llama_cpp


def _main(argv: Optional[List[str]] = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        prog="gpu-container-plan",
        description="Plan an MoE placement (llama.cpp --n-cpu-moe) from a rig+model profile.",
    )
    ap.add_argument("--debug", action="store_true", help="show the full traceback on an unexpected error")
    ap.add_argument("--profile", required=True, help="profile.json from gpu-container-profile")
    ap.add_argument("--model-config", help="HF config.json to (re)profile the model side into the plan")
    ap.add_argument("--model-name", help="override the model name")
    ap.add_argument("--quant", help="quant tag, e.g. gguf-q4_k_m (drives bytes/weight + footprint)")
    ap.add_argument("--ctx", type=int, default=4096, help="context length for the KV-cache budget")
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--cpu-bw", type=float, help="override CPU RAM bandwidth (GB/s)")
    ap.add_argument("--non-expert-bpw", type=float,
                    help="bytes/weight for always-resident weights (auto: f16 for mxfp4, else the quant bpw)")
    ap.add_argument("--floor", type=float, default=1.0, help="refuse below this decode tok/s")
    ap.add_argument("--hf", help="model ref for the launch command, e.g. unsloth/Qwen3-30B-A3B-GGUF:Q4_K_M")
    ap.add_argument("--calibration-dir", help="extra calibration receipts to fold in (atop the bundled seed)")
    ap.add_argument("--no-calibration", action="store_true",
                    help="forecast the raw roofline ceiling only (skip the calibrated band)")
    ap.add_argument("-o", "--out", help="write the plan JSON here (default: stdout)")
    args = ap.parse_args(argv)

    try:
        with open(args.profile, "r", encoding="utf-8") as f:
            prof = Profile.from_json(f.read())
    except FileNotFoundError:
        raise GpuContainerError("IO_PROFILE_NOT_FOUND", f"profile not found: {args.profile}",
                                hint="run `gpu-container-profile -o profile.json` first (in-container)")
    except (ValueError, OSError) as e:
        raise GpuContainerError("INPUT_BAD_PROFILE", f"could not read {args.profile}",
                                hint="expected a profile.json from gpu-container-profile", cause=str(e))

    if args.model_config:
        try:
            with open(args.model_config, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError) as e:
            raise GpuContainerError("INPUT_BAD_MODEL_CONFIG", f"could not read {args.model_config}",
                                    hint="expected a HuggingFace config.json", cause=str(e))
        prof.model = model_mod.analyze_config(cfg, name=args.model_name, quant=args.quant or "gguf-q4_k_m")
    elif args.quant and prof.model is not None:
        prof.model.quant = args.quant

    # Calibration: bundled seed + any extra receipts, unless disabled. With no data for the shape's
    # regime the planner falls back to the raw ceiling on its own.
    calibration = None
    if not args.no_calibration:
        extra = CalibrationStore(args.calibration_dir).points() if args.calibration_dir else None
        calibration = CalibrationModel.from_seed(extra=extra)

    plan = plan_llama_cpp(
        prof, ctx_len=args.ctx, batch=args.batch,
        cpu_mem_bw_gbps=args.cpu_bw, non_expert_bpw=args.non_expert_bpw,
        floor_tok_s=args.floor, model_ref=args.hf, calibration=calibration,
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


def main(argv: Optional[List[str]] = None) -> int:
    return guard(_main, argv)


if __name__ == "__main__":
    raise SystemExit(main())
