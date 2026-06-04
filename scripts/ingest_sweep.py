#!/usr/bin/env python3
"""Ingest a llama-bench `--n-cpu-moe` SWEEP into receipts + calibration points (closes the loop
for a whole sweep at once; the single-run path is the `gpu-container-receipt` CLI).

    python scripts/ingest_sweep.py --profile profile.json --bench bench.json \
        --model-name gpt-oss-120b --quant gguf-mxfp4 --calibration-dir ./calib --out-dir ./receipts

For each measured decode (tg) row it re-plans at that N (same profile -> same ceiling), pairs the
measured rate with the forecast, writes a receipt, and appends a CalibrationPoint so the next plan
for this shape is calibrated. Prints a summary table: ceiling vs calibrated-forecast vs measured,
realized efficiency, and whether each landed inside the calibrated band.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gpu_container.planner import (                       # noqa: E402
    CalibrationModel, CalibrationStore, plan_llama_cpp, plan_to_calibration_point,
)
from gpu_container.planner.receipt import build_receipt, parse_llama_bench  # noqa: E402
from gpu_container.profiler import model as model_mod     # noqa: E402
from gpu_container.profiler.schema import Profile         # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ingest a llama-bench --n-cpu-moe sweep -> receipts + calibration")
    ap.add_argument("--profile", required=True, help="profile.json (in-container, with the model side)")
    ap.add_argument("--bench", required=True, help="llama-bench -o json sweep output")
    ap.add_argument("--model-config", help="HF config.json (if the profile lacks the model side)")
    ap.add_argument("--model-name", required=True)
    ap.add_argument("--quant", default="gguf-mxfp4")
    ap.add_argument("--ctx", type=int, default=4096)
    ap.add_argument("--cpu-bw", type=float, help="override CPU RAM bandwidth (GB/s)")
    ap.add_argument("--non-expert-bpw", type=float, help="override non-expert bytes/weight")
    ap.add_argument("--calibration-dir", help="append CalibrationPoints here (the write-back)")
    ap.add_argument("--out-dir", help="write per-N receipt JSON here")
    ap.add_argument("--created", default="2026-06-04")
    ap.add_argument("--rig", default="RTX 5090 (sm_120) WSL2 Docker, driver 610.47, CUDA 12.8")
    args = ap.parse_args(argv)

    with open(args.profile, "r", encoding="utf-8") as f:
        prof = Profile.from_json(f.read())
    if args.model_config:
        with open(args.model_config, "r", encoding="utf-8") as f:
            prof.model = model_mod.analyze_config(json.load(f), name=args.model_name, quant=args.quant)
    elif prof.model is not None:
        prof.model.quant = args.quant
    if prof.model is None:
        print("ERROR: profile has no model side and no --model-config given.", file=sys.stderr)
        return 2

    with open(args.bench, "r", encoding="utf-8") as f:
        rows = parse_llama_bench(f.read())
    if not rows:
        print("ERROR: no parseable llama-bench rows in --bench.", file=sys.stderr)
        return 2

    # pair prefill (pp) + decode (tg) rows by n_cpu_moe
    by_n = defaultdict(dict)
    for r in rows:
        test = str(r.get("test", ""))
        n = r.get("n_cpu_moe")
        if n is None or r.get("avg_ts") is None:
            continue
        if test.startswith("tg"):
            by_n[int(n)]["decode"] = float(r["avg_ts"])
        elif test.startswith("pp"):
            by_n[int(n)]["prefill"] = float(r["avg_ts"])

    if not by_n:
        print("ERROR: no tg/pp rows with n_cpu_moe in --bench.", file=sys.stderr)
        return 2

    calibration = CalibrationModel.from_seed()
    store = CalibrationStore(args.calibration_dir) if args.calibration_dir else None
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)

    print(f"{'N':>3} {'ceiling':>8} {'calib':>7} {'band':>15} {'measured':>9} {'eff%':>5} {'band?':>6} {'floor?':>6}")
    for n in sorted(by_n):
        decode = by_n[n].get("decode")
        if decode is None:
            continue
        plan = plan_llama_cpp(prof, ctx_len=args.ctx, cpu_mem_bw_gbps=args.cpu_bw,
                              non_expert_bpw=args.non_expert_bpw, force_n_cpu_moe=n,
                              calibration=calibration)
        rec = build_receipt(plan, decode_tok_s=decode, prefill_tok_s=by_n[n].get("prefill"),
                            method=f"llama-bench sweep N={n}")
        band = f"[{plan.predicted_band_low_tok_s},{plan.predicted_band_high_tok_s}]" \
            if plan.predicted_band_low_tok_s else "(ceiling)"
        print(f"{n:>3} {plan.ceiling_decode_tok_s:>8.1f} {plan.predicted_decode_tok_s:>7.1f} {band:>15} "
              f"{decode:>9.1f} {rec.realized_efficiency_pct:>5.0f} "
              f"{str(rec.within_band):>6} {str(rec.cleared_floor):>6}")
        if store:
            store.add(plan_to_calibration_point(
                plan, measured_decode_tok_s=decode, model_name=args.model_name, quant=args.quant,
                created=args.created, rig=args.rig, source="llama-bench sweep"))
        if args.out_dir:
            with open(os.path.join(args.out_dir, f"receipt-n{n}.json"), "w", encoding="utf-8") as f:
                f.write(rec.to_json() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
