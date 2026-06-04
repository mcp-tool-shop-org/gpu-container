"""The receipt — a DIFFERENT mechanism (measurement) verifying the planner's forecast.

llama-bench emits per-test rows (`pp###` = prefill, `tg###` = token-generation/decode) with an
`avg_ts` tokens/sec. We parse that, pair it with the plan's predicted CEILING, and record the
realized efficiency (measured ÷ ceiling) + whether the >1 tok/s floor actually cleared. That
efficiency is the calibration seed that closes the static-prediction gap (the architecture's loop).
The model never grades its own forecast: the generator is the planner's closed form; the verifier
is a real run on the GPU.
"""
from __future__ import annotations

import json
from typing import List, Optional

from ..profiler.schema import PlacementPlan, Receipt


def parse_llama_bench(stdout: str) -> List[dict]:
    """Parse `llama-bench -o json` output into [{test, n_cpu_moe, n_gpu_layers, avg_ts}, ...]."""
    # The JSON array may be embedded in other log lines; extract the outermost [...] span.
    s, e = stdout.find("["), stdout.rfind("]")
    if s < 0 or e < 0 or e <= s:
        return []
    try:
        rows = json.loads(stdout[s:e + 1])
    except ValueError:
        return []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append({
            "test": r.get("test") or r.get("n_prompt") or "?",
            "n_cpu_moe": r.get("n_cpu_moe"),
            "n_gpu_layers": r.get("n_gpu_layers"),
            "avg_ts": r.get("avg_ts"),
            "model": r.get("model_filename") or r.get("model_type"),
        })
    return out


def _pick(rows: List[dict], prefix: str) -> Optional[float]:
    """Average tok/s for the first row whose `test` starts with `prefix` (tg=decode, pp=prefill)."""
    for r in rows:
        t = str(r.get("test", ""))
        if t.startswith(prefix) and r.get("avg_ts") is not None:
            return float(r["avg_ts"])
    return None


def build_receipt(
    plan: PlacementPlan,
    decode_tok_s: Optional[float],
    prefill_tok_s: Optional[float] = None,
    vram_used_mib: Optional[float] = None,
    method: Optional[str] = None,
) -> Receipt:
    """Pair a measured run with the plan's forecast -> a Receipt (error, efficiency, floor)."""
    pred = plan.predicted_decode_tok_s
    err = round(100.0 * (decode_tok_s - pred) / pred, 1) if (decode_tok_s and pred) else None
    notes: List[str] = []
    if decode_tok_s and pred:
        eff = 100.0 * decode_tok_s / pred
        notes.append(f"realized {eff:.0f}% of the roofline ceiling ({decode_tok_s:.1f} of {pred:.0f} tok/s) "
                     f"— this efficiency is the calibration seed for the next plan.")
        if decode_tok_s > pred:
            notes.append("ANDON: measured EXCEEDS the ceiling — the bandwidth model is wrong (check "
                         "vram_bw / bytes_per_weight assumptions), not just inefficient.")
    if plan.vram_used_mib and vram_used_mib:
        dv = 100.0 * (vram_used_mib - plan.vram_used_mib) / plan.vram_used_mib
        notes.append(f"VRAM predicted {plan.vram_used_mib:.0f} MiB vs measured {vram_used_mib:.0f} MiB ({dv:+.0f}%).")
    return Receipt(
        runtime=plan.runtime, n_cpu_moe=plan.n_cpu_moe,
        measured_decode_tok_s=round(decode_tok_s, 2) if decode_tok_s else None,
        measured_prefill_tok_s=round(prefill_tok_s, 2) if prefill_tok_s else None,
        measured_vram_used_mib=round(vram_used_mib, 1) if vram_used_mib else None,
        predicted_decode_tok_s=pred, decode_error_pct=err,
        cleared_floor=(decode_tok_s >= plan.floor_tok_s) if decode_tok_s else None,
        method=method, notes=notes,
    )
