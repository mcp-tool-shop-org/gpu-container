"""`gpu-container-profile` — profile this rig (and optionally a model) -> profile.json.

The profile JSON is the contract the planner reads. Run it INSIDE the target container
for an honest hardware vantage (docker-knowledge `hw-measurement`); running on the host
still works and reports the host platform.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import model as model_mod
from .hardware import profile_hardware
from .schema import SCHEMA_VERSION, Profile


def _today() -> str:
    from datetime import date  # host clock is fine for an interactive CLI
    return date.today().isoformat()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="gpu-container-profile",
        description="Profile the rig (and optionally a model) into the placement-planner contract.",
    )
    ap.add_argument("--model-config", help="path to a HuggingFace config.json to profile the model side")
    ap.add_argument("--model-name", help="override the model name")
    ap.add_argument("--quant", help="quant tag, e.g. gguf-q4_k_m")
    ap.add_argument("--date", default=None, help="ISO date stamp (default: today)")
    ap.add_argument("-o", "--out", help="write the profile JSON here (default: stdout)")
    args = ap.parse_args(argv)

    created = args.date or _today()
    hw = profile_hardware(created)

    mp = None
    if args.model_config:
        with open(args.model_config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        mp = model_mod.analyze_config(cfg, name=args.model_name, quant=args.quant)

    notes: List[str] = []
    if hw.bandwidth.pcie_h2d_gbps is None or hw.bandwidth.nvme_rand_qd1_read_iops is None:
        notes.append(
            "bandwidth unmeasured (pending docker-knowledge wave-2): the planner MUST treat "
            "None as unknown, never zero or spec-sheet."
        )
    if hw.platform.uvm_oversubscription is False:
        notes.append(
            "UVM oversubscription unavailable on this platform -> explicit placement only "
            "(docker-knowledge container-runtime)."
        )

    prof = Profile(schema_version=SCHEMA_VERSION, created=created, hardware=hw, model=mp, notes=notes)
    js = prof.to_json()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(js + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(js)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
