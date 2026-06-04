"""`gpu-container-receipt` — close the loop: measure a plan, write the receipt, recalibrate.

    gpu-container-receipt --plan plan.json --bench bench.json \
        --model-name Qwen3-30B-A3B --quant gguf-q4_k_m --calibration-dir ./calib -o receipt.json

It pairs a llama-bench run (`-o json`, via --bench file or stdin) with the plan's forecast, emits a
Receipt (realized efficiency, calibrated-forecast error, within-band), and — when --calibration-dir
is given — appends a CalibrationPoint so the NEXT plan for this shape is calibrated. That write-back
is the recalibration loop. The verifier is a real GPU run, a DIFFERENT mechanism than the planner's
closed form (EXTERNAL_VERIFIER).

Exit code (ANDON): 0 = measured cleared the floor and sat at/below the ceiling; 3 = measured fell
below the >1 tok/s floor (the plan's ship was optimistic); 4 = measured EXCEEDED the ceiling (the
bandwidth model itself is wrong — halt and fix assumptions, don't just recalibrate efficiency).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import List, Optional

from ..profiler.schema import PlacementPlan
from .calibration import CalibrationStore
from .receipt import build_receipt, parse_llama_bench, plan_to_calibration_point
from .receipt import _pick  # decode/prefill row selector


def _read(path: Optional[str]) -> str:
    if path in (None, "-"):
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main(argv: Optional[List[str]] = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        prog="gpu-container-receipt",
        description="Measure a plan against a llama-bench run -> receipt + recalibration write-back.",
    )
    ap.add_argument("--plan", required=True, help="plan.json from gpu-container-plan")
    ap.add_argument("--bench", help="llama-bench -o json output (file or '-' for stdin)")
    ap.add_argument("--decode-tok-s", type=float, help="measured decode tok/s (instead of --bench)")
    ap.add_argument("--prefill-tok-s", type=float, help="measured prefill tok/s (optional)")
    ap.add_argument("--vram-used-mib", type=float, help="measured VRAM use (optional)")
    ap.add_argument("--model-name", help="model name for the calibration point (e.g. Qwen3-30B-A3B)")
    ap.add_argument("--quant", help="quant tag for the calibration point (e.g. gguf-q4_k_m)")
    ap.add_argument("--calibration-dir", help="append a CalibrationPoint here (the recalibration write-back)")
    ap.add_argument("--created", default=date.today().isoformat(), help="ISO date stamp (default: today)")
    ap.add_argument("--rig", help="rig provenance for the calibration point")
    ap.add_argument("--source", help="free-text provenance (which run)")
    ap.add_argument("-o", "--out", help="write the receipt JSON here (default: stdout)")
    args = ap.parse_args(argv)

    plan = PlacementPlan.from_json(_read(args.plan))

    decode = args.decode_tok_s
    prefill = args.prefill_tok_s
    if args.bench is not None:
        rows = parse_llama_bench(_read(args.bench))
        if not rows:
            print("ERROR: --bench produced no parseable llama-bench rows.", file=sys.stderr)
            return 2
        decode = _pick(rows, "tg") if decode is None else decode
        prefill = _pick(rows, "pp") if prefill is None else prefill
    if decode is None:
        print("ERROR: need a measured decode rate (--bench with a tg row, or --decode-tok-s).", file=sys.stderr)
        return 2

    receipt = build_receipt(plan, decode_tok_s=decode, prefill_tok_s=prefill,
                            vram_used_mib=args.vram_used_mib, method=args.source or "llama-bench")

    # The write-back: append this measurement to the calibration store so the next plan is calibrated.
    if args.calibration_dir and args.model_name:
        point = plan_to_calibration_point(
            plan, measured_decode_tok_s=decode, model_name=args.model_name, quant=args.quant,
            created=args.created, rig=args.rig, source=args.source or "gpu-container-receipt",
        )
        dest = CalibrationStore(args.calibration_dir).add(point)
        receipt.notes.append(f"recalibration: appended a CalibrationPoint to {dest} "
                             f"(efficiency {point.efficiency * 100:.0f}% at N={point.n_cpu_moe}).")
    elif args.calibration_dir:
        receipt.notes.append("note: --calibration-dir given but no --model-name; skipped the write-back.")

    js = receipt.to_json()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(js + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(js)
    for note in receipt.notes:
        print(note, file=sys.stderr)

    if receipt.ceiling_decode_tok_s and decode > receipt.ceiling_decode_tok_s:
        return 4  # ANDON: measured beat the ceiling — the bandwidth model is wrong
    if receipt.cleared_floor is False:
        return 3  # below the >1 tok/s floor — the ship was optimistic
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
