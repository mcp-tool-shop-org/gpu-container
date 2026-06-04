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
from .activation import ConcentrationReport
from .calibration import CalibrationPoint


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
    concentration: Optional[ConcentrationReport] = None,
    peaks: Optional[dict] = None,
) -> Receipt:
    """Pair a measured run with the plan's forecast(s) -> a Receipt.

    The plan now carries two forecasts, so the receipt makes two comparisons:
      - realized efficiency = measured / CEILING  -> the calibration seed for the next plan,
      - decode error        = (measured - CALIBRATED) / CALIBRATED -> was the calibrated forecast right?,
      - within_band         = measured inside the plan's calibrated band -> the loop's proof.
    `ceiling` falls back to the calibrated field for plans predating the ceiling split.

    `peaks` (a dict from `gpu-container-watchdog run --peaks-out`) folds the run's SAFETY ENVELOPE
    into the receipt — peak power / host-mem / VRAM — proving the run stayed inside the rig's limits.
    """
    pred = plan.predicted_decode_tok_s                                    # calibrated forecast
    ceiling = plan.ceiling_decode_tok_s or plan.predicted_decode_tok_s    # roofline upper bound
    err = round(100.0 * (decode_tok_s - pred) / pred, 1) if (decode_tok_s and pred) else None
    eff_pct = round(100.0 * decode_tok_s / ceiling, 1) if (decode_tok_s and ceiling) else None
    lo, hi = plan.predicted_band_low_tok_s, plan.predicted_band_high_tok_s
    within = (lo <= decode_tok_s <= hi) if (decode_tok_s and lo is not None and hi is not None) else None

    notes: List[str] = []
    if eff_pct is not None:
        notes.append(f"realized {eff_pct:.0f}% of the roofline ceiling ({decode_tok_s:.1f} of {ceiling:.0f} tok/s) "
                     f"— this efficiency is the calibration seed for the next plan.")
        if decode_tok_s > ceiling:
            notes.append("ANDON: measured EXCEEDS the ceiling — the bandwidth model is wrong (check "
                         "vram_bw / bytes_per_weight assumptions), not just inefficient.")
    if within is not None:
        notes.append(f"calibrated forecast {pred:.1f} tok/s, band [{lo:.1f}, {hi:.1f}] — measured "
                     f"{decode_tok_s:.1f} {'LANDED INSIDE' if within else 'FELL OUTSIDE'} the band "
                     f"({'loop closed' if within else 'recalibrate: ingest this receipt and refit'}).")
    if plan.vram_used_mib and vram_used_mib:
        dv = 100.0 * (vram_used_mib - plan.vram_used_mib) / plan.vram_used_mib
        notes.append(f"VRAM predicted {plan.vram_used_mib:.0f} MiB vs measured {vram_used_mib:.0f} MiB ({dv:+.0f}%).")
    if concentration is not None:
        helps = ("a per-expert cache COULD help this workload" if concentration.cache_helps
                 else "routing is near-uniform — a per-expert cache would NOT help this workload")
        notes.append(f"routing de-risk: {helps} (need {concentration.hot_frac_for_coverage:.0%} of experts for "
                     f"{concentration.coverage_target:.0%} coverage; concentration {concentration.concentration_score:.2f}, "
                     f"top expert {concentration.top1_share:.1%}).")
    if peaks:
        env = []
        if peaks.get("peak_host_mem_pct") is not None:
            env.append(f"peak host-mem {peaks['peak_host_mem_pct']:.0f}%")
        if peaks.get("peak_gpu_power_pct") is not None:
            env.append(f"peak power {peaks['peak_gpu_power_pct']:.0f}%")
        if peaks.get("peak_gpu_vram_used_mib") is not None:
            env.append(f"peak VRAM {peaks['peak_gpu_vram_used_mib'] / 1024:.1f} GiB")
        stayed = peaks.get("stayed_within_envelope")
        tail = ("stayed within the safety envelope" if stayed else
                "BREACHED the safety envelope — aborted mid-run") if stayed is not None else "envelope recorded"
        notes.append(f"safety: {', '.join(env) or 'no peaks'} over {peaks.get('samples', 0)} watchdog polls "
                     f"— {tail}.")
    return Receipt(
        runtime=plan.runtime, n_cpu_moe=plan.n_cpu_moe,
        measured_decode_tok_s=round(decode_tok_s, 2) if decode_tok_s else None,
        measured_prefill_tok_s=round(prefill_tok_s, 2) if prefill_tok_s else None,
        measured_vram_used_mib=round(vram_used_mib, 1) if vram_used_mib else None,
        predicted_decode_tok_s=pred, ceiling_decode_tok_s=round(ceiling, 2) if ceiling else None,
        decode_error_pct=err, realized_efficiency_pct=eff_pct, within_band=within,
        cleared_floor=(decode_tok_s >= plan.floor_tok_s) if decode_tok_s else None,
        routing_cache_helps=concentration.cache_helps if concentration else None,
        routing_hot_frac_for_coverage=round(concentration.hot_frac_for_coverage, 3) if concentration else None,
        routing_concentration=round(concentration.concentration_score, 3) if concentration else None,
        peak_gpu_power_pct=(peaks or {}).get("peak_gpu_power_pct"),
        peak_gpu_temp_c=(peaks or {}).get("peak_gpu_temp_c"),
        peak_gpu_vram_used_mib=(peaks or {}).get("peak_gpu_vram_used_mib"),
        peak_host_mem_pct=(peaks or {}).get("peak_host_mem_pct"),
        min_host_avail_mib=(peaks or {}).get("min_host_avail_mib"),
        safety_samples=(peaks or {}).get("samples"),
        stayed_within_envelope=(peaks or {}).get("stayed_within_envelope"),
        method=method, notes=notes,
    )


def plan_to_calibration_point(
    plan: PlacementPlan,
    measured_decode_tok_s: float,
    model_name: str,
    quant: Optional[str] = None,
    created: Optional[str] = None,
    rig: Optional[str] = None,
    source: Optional[str] = None,
) -> CalibrationPoint:
    """Distill a (plan, measured-decode) pair into a CalibrationPoint for the store — the loop's
    write-back. The ceiling comes from the plan (so efficiency is measured/ceiling); the bandwidth
    assumptions ride along as provenance so the point stays auditable."""
    a = plan.assumptions or {}
    return CalibrationPoint(
        model=model_name, quant=quant,
        n_cpu_moe=plan.n_cpu_moe or 0, n_moe_layers=plan.n_moe_layers or 0,
        ceiling_tok_s=plan.ceiling_decode_tok_s or plan.predicted_decode_tok_s or 0.0,
        measured_tok_s=measured_decode_tok_s,
        cpu_bw_gbps=a.get("cpu_mem_bw_gbps"), vram_bw_gbps=a.get("vram_bw_gbps"),
        ctx_len=a.get("ctx_len"), created=created, rig=rig, source=source,
    )
