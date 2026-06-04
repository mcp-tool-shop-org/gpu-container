# Phase 1 Architecture — The MoE Lane

> The highest-leverage path, built first: a single consumer GPU + pinned host RAM (+ *gated* NVMe) running MoE models too large for VRAM, via explicit tiered expert placement, a measured receipt, and an adaptive calibration loop. Grounded in [`feasibility.md`](feasibility.md). Dense-model offload and multi-GPU are out of Phase-1 scope.

**Why MoE first:** warm-tier MoE offload is already shipping in Fiddler / KTransformers / llama.cpp `--n-cpu-moe` (feasibility #1–3). Our contribution is the **planner + profiler + receipt** wrapper those tools lack. Dense offload is mostly a refusal-generator on consumer rigs (feasibility #12), so it earns less Phase-1 attention.

**Dev rig of record:** RTX 5090, 32 GB VRAM — Docker Desktop / WSL2 Linux backend / NVIDIA Container Toolkit (GPU-in-container passthrough smoke-tested green).

## The closed loop

```
Hardware profile ┐
                 ├─► Calibrate ──► Placement plan ──► Launch ──► Receipt ──┐
Model profile  ──┘   (adaptive)    (tiers + prefetch   (llama.cpp  (measured │
                                    + eviction)         first)      VRAM/RAM/ │
                                                                    NVMe+tok/s)│
                      ▲                                                       │
                      │            refuse if < floor (ANDON) ◄───────────────┤
                      └──────────── recalibrate from measured routing ◄───────┘
```

Every step here is reversible: a placement plan is a file, a launch is a process, and a rejected plan reverts to the last receipt-validated one.

## Tier model & the bandwidth budget

| Tier | Holds | Bandwidth (5090 rig) |
|---|---|---|
| **VRAM (hot)** | shared/attention layers, router, top-N experts, KV working set | ~1 TB/s |
| **Pinned RAM (warm)** | next-M experts (router-prefetched), KV spill | PCIe Gen5 ~50 GB/s sustained |
| **NVMe (cold, gated)** | rarely-routed experts — *admitted only if prefetch clears the floor* | Gen4/5 ~7–14 GB/s seq; **far less at random QD1–4** |

Per-token latency floor ≈ (expert bytes touched ÷ tier bandwidth). Because batch-1 decode is bandwidth-bound (feasibility #10), the slowest tier on the critical path sets the ceiling — which is why cold-NVMe is gated, not free.

## 1. Profiling (extends the Phase-0 profilers)
- **Hardware:** VRAM, **measured** PCIe H2D/D2H (consumer cards are PCIe-bound — feasibility #4), pinnable-RAM ceiling, NVMe **sequential _and_ random QD1–4** (the gap that breaks naive prediction — feasibility #11), CUDA/driver/WSL.
- **Model:** experts, top-k, shared-vs-expert params, per-expert bytes, KV-growth (closed-form).

## 2. Adaptive calibration *(the load-bearing correction)*
- Run **workload-representative** traces — not a generic corpus. Request-level skew aggregates to uniform across diverse prompts (feasibility #6); support per-workload activation-pattern profiles.
- Emit an **initial** hot/warm/cold assignment from the activation histogram, then **refine online** from the receipt's measured routing.
- Persist the calibration as a **pinned artifact** (replayable).

## 3. Placement plan
- **Hot** = top-N most-activated experts + all shared/attention/router layers (VRAM).
- **Warm** = next-M experts in pinned RAM with **router-lookahead prefetch**: predict the next layer's experts during current-layer compute and overlap the RAM→VRAM transfer (Pre-gated / Fate — feasibility #7).
- **Cold** = remaining experts on NVMe, **admitted only** if predicted prefetch hit-rate keeps decode > floor; otherwise demote to RAM or refuse (energy penalty — feasibility #5).
- **Eviction = staleness/sequence-aware (Least-Stale), NOT LRU for experts** (feasibility #8). (LRU/ARC stays for KV spill.)

## 4. Launch — runtime targeting
- **First target: llama.cpp `--n-cpu-moe` / `-ot '…exps=CPU'`** — closest match, shipping, ~12–14 tok/s field-reported (feasibility #3). The planner emits the exact flag set + the predicted memory map.
- **Later:** vLLM (`--cpu-offload-gb`, expert parallel), HF Accelerate (`device_map`). Cross-runtime config-gen lives behind a thin adapter interface (the volatile module).

## 5. Receipt + refusal (the verifier)
- Measure actual VRAM/RAM/NVMe (NVML/pynvml), prefill + decode tok/s, TTFT, **per-expert routing trace**, prefetch hit-rate, eviction rate, thermal throttle.
- **ANDON:** refuse pre-launch if no plan clears **>1 tok/s**; flag post-launch if the receipt deviates from plan beyond threshold.
- **Receipt-accuracy scoping (feasibility #11):** ±10% guaranteed only for in-VRAM/light-offload; heavy-NVMe plans are labelled *"estimated — confirmed by receipt"*; refusal carries a conservative margin (best predictors still miss ~20%).
- The receipt's measured routing **feeds back into calibration** — this empirical loop is what closes the static-prediction gap.

## Alignment with the six workflow standards
- **PIN_PER_STEP** — the calibration artifact + launch plan are pinned and replayable.
- **ANDON_AUTHORITY** — the >1 tok/s refusal + receipt-deviation flag halt a bad plan before it ships.
- **NAMED_COMPENSATORS** — a rejected/withdrawn plan reverts to the last receipt-validated plan; cold-tier admission is reversible (demote to RAM / refuse).
- **DECOMPOSE_BY_SECRETS** — profiler / calibrator / planner / launcher / receipt are separate modules; runtime-specific flag-gen is the isolated volatile part.
- **UNCERTAINTY_GATED_HUMANS** — refusal surfaces a contrastive frame: *"you expected model X to run; it won't clear 1 tok/s because cold-expert NVMe streaming caps decode at ~Y — options: smaller quant / more RAM / a different model."*
- **EXTERNAL_VERIFIER** — the **measured receipt** is a *different mechanism* (measurement) verifying the **planner's prediction**; the model never grades its own forecast.

## Phase-1 milestones
1. ✅ Profiler emits a hardware+model profile JSON (incl. measured PCIe + NVMe random QD1–4).
2. Calibrator produces an initial placement + a per-workload activation trace. *(per-expert; see Phase-2 study-swarm)*
3. ✅ Planner emits a llama.cpp `--n-cpu-moe` launch plan + predicted memory/throughput.
4. ✅ Receipt captures measured placement + tok/s; refusal fires correctly on an over-large model.
5. **Recalibration — two halves:**
   - ✅ **Throughput** (built): the receipt's `measured ÷ ceiling` efficiency feeds a regime-keyed model; the next plan emits a calibrated tok/s **band** instead of the raw ceiling. Proven: a second plan for a measured shape predicts within the band (Qwen3-30B-A3B, in-sample + leave-one-out). See [architecture.md § Throughput calibration](architecture.md#throughput-calibration--the-recalibration-loop).
   - ◻ **Routing** (Phase-2, per-expert): a second run consumes the receipt's per-expert routing and demonstrates a warm-tier hit-rate improvement — needs finer-than-layer placement (`-ot`/`--override-tensor`) + activation traces; gated on the study-swarm.

## Risks / open questions
- Prefetch hit-rate on *your* workloads vs the papers' benchmarks — the ~5–12% miss tail still pays full NVMe latency.
- llama.cpp expert-tensor placement granularity vs the per-expert control the planner wants.
- Calibration cost (trace runs) vs benefit; recalibration cadence.
- Cold-tier energy (feasibility #5) — likely default cold-NVMe experts to **off** unless explicitly opted in.

## First integration target — why llama.cpp
It already implements the hot/warm split (`--n-cpu-moe` / `-ot '…exps=CPU'`), is the lightest dependency, has the widest quant/GGUF coverage, and gives per-tensor placement hooks. The planner's job for v0 is narrow and verifiable: **turn a profile + model into the correct flag string + a predicted memory map, launch, then prove it with a receipt.** vLLM and Accelerate adapters come after the loop is closed once.
