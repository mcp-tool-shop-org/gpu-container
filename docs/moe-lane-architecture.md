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
- **Trace capture (wave-4):** llama.cpp has no built-in per-expert trace; in practice **`llama-imatrix` per-expert `.counts`** give the **L×E activation matrix** (the `eval-callback` route needs headers absent from the prebuilt image). SGLang/vLLM expert-distribution recorders are the cross-engine fallback.
- **Cadence (wave-4):** recalibrate on **drift, not a timer** — a warm-tier miss-rate change detector (ADWIN/DDM) confirmed by JS/χ² divergence between calibrated and live expert histograms; EWMA/ghost-list self-tuning between re-traces; an anti-thrash guard (tiered-JIT pattern).
- Persist the calibration as a **pinned artifact** (replayable).

## 3. Placement plan
- **Hot** = top-N most-activated experts + all shared/attention/router layers (VRAM).
- **Warm** = next-M experts in pinned RAM with **router-lookahead prefetch via a cross-layer gate** — run the *next* layer's existing router on the current layer's hidden state one step early to predict its experts and overlap the RAM→VRAM transfer (Fate ~99% hit / AdapMoE 1.35×, **stock model, no retrain** — wave-4). Pre-gated is **excluded** (needs a fine-tuned model); MoE-Beyond is **deferred** (needs a trained predictor).
- **Cold** = remaining experts on NVMe, **admitted only** if predicted prefetch hit-rate keeps decode > floor; otherwise demote to RAM or refuse (energy penalty — feasibility #5).
- **Eviction = Least-Stale** (stale/current-queue partition, evict stale first, key `(stale-flag, layer-index)`), NOT LRU for experts (wave-4; feasibility #8). (LRU/ARC stays for KV spill.)
- ⚠ **Granularity reality (wave-4):** stock llama.cpp stores a layer's experts as **one fused tensor**, so `-ot`/`--override-tensor` places at **per-layer** grain — it **cannot** statically place an individual expert. The **shared/attention-in-VRAM** hot tier ships as `-ot` today; the **per-expert** top-N/next-M split is a **runtime expert-slot cache** built at llama.cpp's [`#20757`](https://github.com/ggml-org/llama.cpp/issues/20757) hook (byte-offset expert copy; no persistence today), **not** a launch flag. See the Phase-2 block below.

## 4. Launch — runtime targeting
- **First target: llama.cpp `--n-cpu-moe` / `-ot '…exps=CPU'`** — closest match, shipping, ~12–14 tok/s field-reported (feasibility #3). The planner emits the exact flag set + the predicted memory map. **Note (wave-4):** these flags place at **per-layer** grain; **per-expert** tiering is the runtime cache (§3 granularity callout), a Phase-2 build.
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
   - ◻ **Routing** (Phase-2, per-expert): a second run consumes the receipt's per-expert routing and demonstrates a warm-tier hit-rate improvement. **Study-swarm resolved (wave-4):** `-ot` is per-layer only, so this is **not** a flag — it is a **runtime expert-slot cache** (llama.cpp `#20757` hook) with Least-Stale eviction + cross-layer-gate prefetch, fed by an `eval-callback` L×E trace, recalibrated on drift. See the **Phase-2 block** below + docker-knowledge wave-4 (moe-placement).

## Phase 2 — per-expert tiering (wave-4 study-swarm)

The flagship's deep half, grounded by docker-knowledge **wave-4** (moe-placement lane; 12 findings, 3-lens verified, 0 fabrications). The design that survived verification:

- **Placement atom = the runtime expert-slot cache, not `-ot`.** A layer's experts are one fused tensor (`blk.N.ffn_*_exps.weight {n_embd, n_ff, n_expert}`), so `-ot` is per-layer. Per-expert hot/warm/cold tiering is a persistent GPU-slot cache (`expert_id→slot` map) built at llama.cpp's [`#20757`](https://github.com/ggml-org/llama.cpp/issues/20757) hook (the byte-offset expert copy that today has *no* persistence). **Decision ([ADR-0001](decisions/0001-per-expert-cache-build-vs-upstream.md), 2026-06-04): Option B — consume `#20757`'s cache *mechanism*, contribute the *policy*** (Least-Stale + cross-layer-gate); keep calibration/trace/receipt in-product. The near-term trace + per-layer-calibration work is unblocked and decoupled from this.
- **Trace = `llama-imatrix` per-expert `.counts` → L×E matrix** (the prebuilt, working path; `eval-callback` was the original plan but needs llama.cpp headers absent from the image). SGLang/vLLM recorders are the cross-engine fallback. **Shipped as `gpu-container-concentration --trace|--imatrix`** — scores routing concentration → whether the cache is worth building (ADR-0001's empirical run used it: Qwen3 → near-uniform → hold).
- **Eviction = Least-Stale** (stale/current queue, key `(stale-flag, layer-index)`) — stock model, no surgery.
- **Prefetch = cross-layer gate** (next layer's existing router on the current hidden state; Fate ~99% hit, AdapMoE 1.35×) — stock model, no retrain. Pre-gated excluded (needs fine-tune); MoE-Beyond deferred (needs a trained predictor).
- **Cadence = drift-gated** (miss-rate detector + histogram divergence; EWMA/ghost-list self-tuning between; anti-thrash guard).

Sources + per-citation verification: `readouts/docker-knowledge/waves/wave-04-per-expert/`.

## Risks / open questions
- Prefetch hit-rate on *your* workloads vs the papers' benchmarks — the ~5–12% miss tail still pays full NVMe latency.
- ✅ **Resolved (wave-4 + [ADR-0001](decisions/0001-per-expert-cache-build-vs-upstream.md)):** llama.cpp `-ot` granularity is **per-layer** (fused expert tensor); per-expert control requires the runtime cache (`#20757` hook). **Decided: Option B** — consume the `#20757` mechanism, contribute the policy (Least-Stale + cross-layer-gate), keep calibration/receipt in-product.
- ✅ **Resolved (wave-4):** recalibration cadence is **drift-gated** (miss-rate detector + histogram divergence), not fixed-interval; trace cost is bounded by the <1% eval-callback probe.
- Cold-tier energy (feasibility #5) — likely default cold-NVMe experts to **off** unless explicitly opted in.

## First integration target — why llama.cpp
It already implements the hot/warm split (`--n-cpu-moe` / `-ot '…exps=CPU'`), is the lightest dependency, has the widest quant/GGUF coverage, and gives per-tensor placement hooks. The planner's job for v0 is narrow and verifiable: **turn a profile + model into the correct flag string + a predicted memory map, launch, then prove it with a receipt.** vLLM and Accelerate adapters come after the loop is closed once.
