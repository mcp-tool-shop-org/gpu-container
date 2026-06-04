"""`gpu-container-profile` — profile this rig (and optionally a model) -> profile.json.

The profile JSON is the contract the planner reads. Run it INSIDE the target container for
an honest hardware vantage (docker-knowledge `hw-measurement`); the PCIe/NVMe/pinnable
benchmarks need the CUDA runtime + fio + an ext4 bench volume that the container provides.

Two modes:
  * MEASURE (default): detect + benchmark the rig now. `--no-bench` skips the benchmarks
    (identity detection only); `--bench-dir` points the NVMe test at a mounted ext4 volume.
  * EMIT (`--from-profile X.json --emit-baseline`): take a profile measured in-container and
    record its readouts into the docker-knowledge KB (runs on the host, where the KB lives).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from ..errors import GpuContainerError, guard
from . import baseline as baseline_mod
from . import model as model_mod
from .hardware import profile_hardware
from .schema import SCHEMA_VERSION, Profile

# Conventional KB location on this rig (overridable via --baseline-db / $GPU_CONTAINER_KB_DB).
_DEFAULT_KB_DB = os.environ.get("GPU_CONTAINER_KB_DB") or r"E:\AI\readouts\docker-knowledge\findings.db"


def _today() -> str:
    from datetime import date  # host clock is fine for an interactive CLI
    return date.today().isoformat()


def _build_notes(prof: Profile) -> List[str]:
    notes: List[str] = []
    bw = prof.hardware.bandwidth
    if bw.pcie_h2d_gbps is None or bw.nvme_rand_qd1_read_iops is None:
        notes.append(
            "bandwidth partially/un-measured: the planner MUST treat None as unknown, "
            "never zero or spec-sheet. See bandwidth.method/details for why."
        )
    if prof.hardware.platform.uvm_oversubscription is False:
        notes.append(
            "UVM oversubscription unavailable on this platform -> explicit placement only "
            "(docker-knowledge container-runtime)."
        )
    mem = prof.hardware.memory
    if mem.pinnable_ceiling_gib is not None:
        c = mem.pinnable_ceiling_gib
        if c < 1.0:
            notes.append(
                f"pinnable host-RAM ceiling measured at {c} GiB — small (the historical WSL2 "
                "collapse); tightly caps the warm-tier KV/prefetch staging budget."
            )
        else:
            bound = ">=" if mem.pinnable_capped else "~"
            extra = " (probe safety-capped; true ceiling may be higher)" if mem.pinnable_capped else ""
            notes.append(
                f"pinnable host-RAM ceiling MEASURED at {bound}{c} GiB{extra} — ample warm-tier "
                f"staging budget, well above the historical WSL2 ~300-500 MB cap (driver "
                f"{prof.hardware.gpu.driver_version} appears to lift it). Measured, not assumed."
            )
    return notes


def _main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="gpu-container-profile",
        description="Profile the rig (and optionally a model) into the placement-planner contract.",
    )
    ap.add_argument("--debug", action="store_true", help="show the full traceback on an unexpected error")
    ap.add_argument("--model-config", help="path to a HuggingFace config.json to profile the model side")
    ap.add_argument("--model-name", help="override the model name")
    ap.add_argument("--quant", help="quant tag, e.g. gguf-q4_k_m")
    ap.add_argument("--date", default=None, help="ISO date stamp (default: today)")
    ap.add_argument("--no-bench", action="store_true",
                    help="skip the PCIe/NVMe/pinnable benchmarks (identity detection only)")
    ap.add_argument("--bench-dir", help="directory for the fio NVMe test (an ext4-backed mounted volume; "
                                        "default $GPU_CONTAINER_BENCH_DIR or /bench)")
    ap.add_argument("-o", "--out", help="write the profile JSON here (default: stdout)")
    # emit / close-the-loop
    ap.add_argument("--from-profile", help="load an existing profile.json instead of detecting (for --emit-baseline)")
    ap.add_argument("--emit-baseline", action="store_true",
                    help="write the profile's measured readouts into the docker-knowledge KB")
    ap.add_argument("--baseline-db", default=_DEFAULT_KB_DB, help="path to docker-knowledge findings.db")
    ap.add_argument("--baseline-context", help="override the measurement context label (e.g. the image tag)")
    args = ap.parse_args(argv)

    # Windows consoles default to cp1252; the profile JSON (ensure_ascii=False) can carry
    # non-ASCII (e.g. accented model names) — make stdout utf-8 so printing never crashes.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    created = args.date or _today()

    # --- obtain the profile (load or measure) -------------------------------------------
    if args.from_profile:
        try:
            with open(args.from_profile, "r", encoding="utf-8") as f:
                prof = Profile.from_json(f.read())
        except (OSError, ValueError) as e:
            raise GpuContainerError("INPUT_BAD_PROFILE", f"could not read {args.from_profile}",
                                    hint="expected a profile.json from a prior `gpu-container-profile` run",
                                    cause=str(e))
    else:
        hw = profile_hardware(created, run_benches=not args.no_bench, bench_dir=args.bench_dir)
        mp = None
        if args.model_config:
            try:
                with open(args.model_config, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except (OSError, ValueError) as e:
                raise GpuContainerError("INPUT_BAD_MODEL_CONFIG", f"could not read {args.model_config}",
                                        hint="expected a HuggingFace config.json", cause=str(e))
            mp = model_mod.analyze_config(cfg, name=args.model_name, quant=args.quant)
        prof = Profile(schema_version=SCHEMA_VERSION, created=created, hardware=hw, model=mp, notes=[])
        prof.notes = _build_notes(prof)

    # --- emit to the KB (close the loop) ------------------------------------------------
    if args.emit_baseline:
        summary = baseline_mod.emit_baseline(
            prof, db_path=args.baseline_db, context=args.baseline_context, measured_date=created,
        )
        if "error" in summary:
            raise GpuContainerError("RUNTIME_EMIT_BASELINE_FAILED", str(summary["error"]),
                                    hint="check --baseline-db path and that the docker-knowledge KB is reachable")
        print(f"emit-baseline: wrote {summary['written']} rows "
              f"({', '.join(summary['metrics'])}) -> {summary['source_file']} "
              f"[context: {summary['context']}] in {summary['db']}", file=sys.stderr)

    # --- write/print the profile JSON ---------------------------------------------------
    js = prof.to_json()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(js + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(js)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    return guard(_main, argv)


if __name__ == "__main__":
    raise SystemExit(main())
