"""llama.cpp `--n-cpu-moe` placement planner.

Closed-form, deterministic, reversible (a plan is a file). The math:

  VRAM_used(N) = non_expert_bytes + (per_moe_layer_expert_bytes · (L_moe − N)) + KV_bytes + overhead

`--n-cpu-moe N` moves the first N MoE layers' experts to CPU RAM, so raising N lowers VRAM use
(more experts off the GPU) and lowers throughput (CPU computes them at RAM bandwidth, far below
the GPU's). We pick the SMALLEST N that fits — maximal GPU residency, maximal speed — and refuse
if even N = L_moe (all experts on CPU) cannot fit the always-resident footprint.

Decode is bandwidth-bound at batch 1 (feasibility #10): per token the GPU reads its resident
weights + active experts at VRAM bandwidth while the CPU reads its N layers' active experts at
RAM bandwidth. Throughput ≈ 1 / (t_gpu + t_cpu). This is an ESTIMATE for N>0 (heavy-offload
prediction misses up to ~2-3× — feasibility #11), labelled and confirmed by the receipt; the
N=0 in-VRAM case is the ±10% regime.
"""
from __future__ import annotations

from typing import Optional

from ..profiler import model as model_mod
from ..profiler.schema import PlacementPlan, Profile

_MIB = 1024 * 1024
_GB = 1e9

# Labelled defaults when the profile hasn't measured them (the planner flags the assumption).
DEFAULT_CPU_BW_GBPS = 80.0      # DDR5 dual-channel, conservative (measure via the profiler to override)
DEFAULT_VRAM_BW_GBPS = 1790.0  # RTX 5090 GDDR7 512-bit (~1.79 TB/s)


def plan_llama_cpp(
    profile: Profile,
    ctx_len: int = 4096,
    batch: int = 1,
    cpu_mem_bw_gbps: Optional[float] = None,
    vram_bw_gbps: Optional[float] = None,
    overhead_mib: float = 1024.0,
    floor_tok_s: float = 1.0,
    model_ref: Optional[str] = None,
    force_n_cpu_moe: Optional[int] = None,
) -> PlacementPlan:
    """Plan an MoE placement for llama.cpp `--n-cpu-moe`. Honest verdict, never raises."""
    hw, model = profile.hardware, profile.model

    if model is None or not model.expert.is_moe:
        return PlacementPlan(fits=False, verdict="refuse",
                             message="Not an MoE model (or no model profiled) — the --n-cpu-moe lane "
                                     "is MoE-only. Dense offload is a separate (refusal-prone) lane.")
    if model.expert_params_total is None or model.non_expert_params is None or not model.n_moe_layers:
        return PlacementPlan(fits=False, verdict="refuse",
                             message="model profile lacks the closed-form param split — re-run the "
                                     "profiler with --model-config <config.json>.")
    vram_budget = hw.gpu.vram_free_mib or hw.gpu.vram_total_mib
    if not vram_budget:
        return PlacementPlan(fits=False, verdict="refuse",
                             message="VRAM unknown (profiler returned None) — cannot place honestly.")

    bpw = model_mod.bytes_per_weight(model.quant, model.dtype_bytes)
    cpu_bw = (cpu_mem_bw_gbps or getattr(hw.memory, "cpu_mem_bw_gbps", None) or DEFAULT_CPU_BW_GBPS) * _GB
    vram_bw = (vram_bw_gbps or DEFAULT_VRAM_BW_GBPS) * _GB
    cpu_bw_measured = bool(cpu_mem_bw_gbps or getattr(hw.memory, "cpu_mem_bw_gbps", None))

    Lm = model.n_moe_layers
    expert_total_bytes = model.expert_params_total * bpw
    non_expert_bytes = model.non_expert_params * bpw
    per_layer_expert_bytes = expert_total_bytes / Lm
    kv_bytes = model.kv_bytes_at(ctx_len, batch) or 0

    def vram_used_mib(n: int) -> float:
        gpu_expert_bytes = per_layer_expert_bytes * (Lm - n)
        return (non_expert_bytes + gpu_expert_bytes + kv_bytes) / _MIB + overhead_mib

    assumptions = {
        "cpu_mem_bw_gbps": round(cpu_bw / _GB, 1), "cpu_bw_measured": cpu_bw_measured,
        "vram_bw_gbps": round(vram_bw / _GB, 1), "bytes_per_weight": round(bpw, 3),
        "ctx_len": ctx_len, "batch": batch, "overhead_mib": overhead_mib,
        "kv_dtype": "f16", "model_total_b": model.total_params,
        "forced_n": force_n_cpu_moe,
    }

    if force_n_cpu_moe is not None:
        # explore a specific N (what-if / receipt scoring) instead of the auto-minimal one
        N = max(0, min(int(force_n_cpu_moe), Lm))
        if vram_used_mib(N) > vram_budget:
            return PlacementPlan(
                fits=False, verdict="refuse", n_cpu_moe=N, n_moe_layers=Lm,
                vram_budget_mib=round(vram_budget, 1), vram_used_mib=round(vram_used_mib(N), 1),
                assumptions=assumptions, floor_tok_s=floor_tok_s,
                message=f"REFUSE: forced --n-cpu-moe {N} still needs ~{vram_used_mib(N):.0f} MiB "
                        f"> {vram_budget:.0f} MiB free VRAM.")
    else:
        # smallest N in [0, Lm] that fits — maximal GPU residency, maximal speed
        n_fit = next((n for n in range(0, Lm + 1) if vram_used_mib(n) <= vram_budget), None)
        if n_fit is None:
            floor_vram = vram_used_mib(Lm)
            return PlacementPlan(
                fits=False, verdict="refuse", n_cpu_moe=Lm, n_moe_layers=Lm,
                vram_budget_mib=round(vram_budget, 1), vram_used_mib=round(floor_vram, 1),
                assumptions=assumptions, floor_tok_s=floor_tok_s,
                message=(f"REFUSE: even with ALL experts on CPU (--cpu-moe), the always-resident footprint "
                         f"(attention + router + embeddings + output head + {ctx_len}-tok KV) needs "
                         f"~{floor_vram:.0f} MiB > {vram_budget:.0f} MiB free VRAM. You probably expected "
                         f"{model.name} to fit; it cannot, because the non-expert weights alone exceed VRAM. "
                         f"Options: shorter --ctx, q8_0 KV cache, a smaller/more-quantized model, or more VRAM."),
            )
        N = n_fit
    ram_used_mib = per_layer_expert_bytes * N / _MIB
    ram_avail_mib = (hw.memory.ram_available_gib or hw.memory.ram_total_gib or 0) * 1024
    ram_ok = (ram_used_mib <= ram_avail_mib) if ram_avail_mib else True

    # bandwidth-bound decode estimate
    topk = model.expert.experts_per_token or 0
    active_each = (model.expert.expert_params_each or 0) * bpw
    gpu_active_expert = active_each * topk * (Lm - N)
    cpu_active_expert = active_each * topk * N
    # per-token GPU read ≈ all non-expert weights (attention/router/head) + GPU-resident active
    # experts + the KV cache (attention reads it every decode step). CPU reads its active experts.
    # This is a ROOFLINE CEILING (peak bandwidth, no kernel/launch/attention-compute overhead): a
    # true UPPER BOUND on decode tok/s. Real decode runs at a fraction of it; the receipt measures
    # the actual efficiency and closes the gap. Refusal is conservative — it fires only when even
    # this optimistic ceiling cannot clear the floor.
    t_gpu = (non_expert_bytes + gpu_active_expert + kv_bytes) / vram_bw
    t_cpu = cpu_active_expert / cpu_bw
    decode_tok_s = (1.0 / (t_gpu + t_cpu)) if (t_gpu + t_cpu) > 0 else None
    basis = ("roofline ceiling, in-VRAM (active-weight bandwidth; real decode is a fraction of this -- "
             "small-active MoE is largely overhead-bound -- confirmed by receipt)" if N == 0
             else "roofline ceiling, CPU-offload (real well below; heavy-offload can miss 2-3x -- confirmed by receipt)")

    below_floor = decode_tok_s is not None and decode_tok_s < floor_tok_s
    verdict = "refuse" if (below_floor or not ram_ok) else "ship"
    vu = vram_used_mib(N)

    flags = f"-ngl 99 --n-cpu-moe {N} -c {ctx_len} -fa"
    cmd_model = f"-hf {model_ref}" if model_ref else "-m <model.gguf>"

    if verdict == "refuse" and below_floor:
        msg = (f"REFUSE: even the roofline CEILING for the best plan (--n-cpu-moe {N}) is "
               f"~{decode_tok_s:.2f} tok/s < {floor_tok_s} floor — real decode is lower still. "
               f"You probably expected {model.name} to be usable; with {N}/{Lm} expert layers on CPU "
               f"(RAM bandwidth ~{cpu_bw/_GB:.0f} GB/s) it cannot clear the floor. "
               f"Options: a smaller model, fewer active experts, or more VRAM to keep N low.")
    elif verdict == "refuse":
        msg = (f"REFUSE: plan needs {ram_used_mib/1024:.1f} GiB CPU RAM for {N} expert layers but only "
               f"~{ram_avail_mib/1024:.1f} GiB available.")
    else:
        tier = "fully in VRAM" if N == 0 else f"{N}/{Lm} expert layers on CPU RAM"
        msg = (f"SHIP: {model.name} {tier}. Decode ceiling <={decode_tok_s:.0f} tok/s "
               f"({basis}). VRAM ~{vu:.0f}/{vram_budget:.0f} MiB, CPU-expert RAM ~{ram_used_mib/1024:.1f} GiB. "
               f"Launch: llama-cli {cmd_model} {flags}")

    return PlacementPlan(
        fits=True, verdict=verdict, n_cpu_moe=N, n_moe_layers=Lm, llama_flags=flags,
        vram_budget_mib=round(vram_budget, 1), vram_used_mib=round(vu, 1),
        ram_used_mib=round(ram_used_mib, 1),
        predicted_decode_tok_s=round(decode_tok_s, 2) if decode_tok_s else None,
        throughput_basis=basis, floor_tok_s=floor_tok_s, message=msg, assumptions=assumptions,
    )
