#!/usr/bin/env python3
"""Regenerate the bundled calibration seed from the milestone 2-3 live receipt.

The seed pairs MEASURED decode tok/s (llama-bench ground truth, Qwen3-30B-A3B Q4_K_M on the
RTX 5090 in-container, driver 610.47) with the planner's roofline CEILING at each N -> the
realized efficiency the recalibration loop keys off. Re-run this whenever the planner's
bandwidth model changes, so the seed's stored ceilings stay self-consistent with current code:

    python scripts/gen_calibration_seed.py
    python scripts/gen_calibration_seed.py --check   # verify the committed seed matches (CI guard)

The MEASURED numbers are immutable ground truth; only the ceilings are recomputed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gpu_container.planner import plan_llama_cpp                      # noqa: E402
from gpu_container.planner.calibration import _SEED_PATH, CalibrationPoint  # noqa: E402
from gpu_container.profiler import model as m                         # noqa: E402
from gpu_container.profiler.schema import (                           # noqa: E402
    GpuInfo, HardwareProfile, MemoryInfo, PlatformInfo, Profile,
)

# Qwen3-30B-A3B (~30.5B): 48 layers, hidden 2048, moe FFN 768, 128 experts top-8.
QWEN3_MOE = {
    "model_type": "qwen3_moe", "num_hidden_layers": 48, "hidden_size": 2048,
    "moe_intermediate_size": 768, "intermediate_size": 768, "num_attention_heads": 32,
    "num_key_value_heads": 4, "head_dim": 128, "num_experts": 128, "num_experts_per_tok": 8,
    "vocab_size": 151936, "torch_dtype": "bfloat16",
}

# Live profile inputs from the milestone 2-3 in-container run (memory/gpu-container.md).
VRAM_FREE_MIB = 29613
CPU_BW_GBPS = 40.7                # measured numpy-copy bandwidth (NOT the 80 default)
CTX_LEN = 4096

# Measured llama-bench decode (tg128), Qwen3-30B-A3B Q4_K_M, `--n-cpu-moe 0,24,48 -p 512 -n 128`.
MEASURED_TG = {0: 302.4, 24: 41.9, 48: 20.4}

CREATED = "2026-06-04"
RIG = "RTX 5090 (sm_120) WSL2 Docker, driver 610.47, CUDA 12.8"
SOURCE = "milestone 2-3 live receipt: Qwen3-30B-A3B Q4_K_M, llama-bench -p 512 -n 128"


def build_seed_points():
    prof = Profile(
        schema_version="0.1.0", created=CREATED,
        hardware=HardwareProfile(
            gpu=GpuInfo(name="RTX 5090", vram_total_mib=32607, vram_free_mib=VRAM_FREE_MIB),
            platform=PlatformInfo(os="linux", in_container=True, wsl2=True),
            memory=MemoryInfo(ram_total_gib=60.0, ram_available_gib=60.0, cpu_mem_bw_gbps=CPU_BW_GBPS),
        ),
    )
    prof.model = m.analyze_config(QWEN3_MOE, name="Qwen3-30B-A3B", quant="gguf-q4_k_m")
    points = []
    for n, measured in MEASURED_TG.items():
        plan = plan_llama_cpp(prof, ctx_len=CTX_LEN, force_n_cpu_moe=n)
        points.append(CalibrationPoint(
            model="Qwen3-30B-A3B", quant="gguf-q4_k_m",
            n_cpu_moe=n, n_moe_layers=prof.model.n_moe_layers,
            ceiling_tok_s=round(plan.predicted_decode_tok_s, 2), measured_tok_s=measured,
            cpu_bw_gbps=CPU_BW_GBPS, vram_bw_gbps=plan.assumptions["vram_bw_gbps"],
            ctx_len=CTX_LEN, created=CREATED, rig=RIG, source=SOURCE,
        ))
    return points


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="(re)generate the bundled calibration seed")
    ap.add_argument("--check", action="store_true", help="verify the committed seed matches (exit 1 if drifted)")
    args = ap.parse_args(argv)

    payload = [p.to_dict() for p in build_seed_points()]
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.check:
        with open(_SEED_PATH, "r", encoding="utf-8") as f:
            current = f.read().strip()
        if current != rendered.strip():
            print("DRIFT: committed calibration_seed.json differs from regenerated. Re-run without --check.",
                  file=sys.stderr)
            return 1
        print("ok: calibration seed is consistent with the planner.")
        return 0

    with open(_SEED_PATH, "w", encoding="utf-8") as f:
        f.write(rendered + "\n")
    for p in build_seed_points():
        print(f"  N={p.n_cpu_moe:>2}  ceiling={p.ceiling_tok_s:>7.2f}  measured={p.measured_tok_s:>6.1f}  "
              f"efficiency={p.efficiency * 100:>4.1f}%  ({p.regime})")
    print(f"wrote {_SEED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
