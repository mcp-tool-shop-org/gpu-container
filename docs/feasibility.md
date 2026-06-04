# Feasibility Assessment

**Status:** Phase 0 feasibility — **PASS (build it)**, with three required calibrations.
**Date:** 2026-06-04
**Method:** research-grounded *study-swarm* (run `wf_965f110f-e24`): 5 parallel research agents over the load-bearing feasibility questions, then a 3-lens external-verification pass (retrieval oracle + two non-Claude model families, reasoning-stripped) across all 35 citations. **0 fabrications.**
**Dev rig of record:** RTX 5090 (32 GB) · Docker Desktop on the WSL2 (Linux-container) backend · NVIDIA Container Toolkit (`nvidia` runtime registered). GPU-in-container passthrough smoke-tested green (`nvidia-smi` reports the 5090 from inside `nvidia/cuda`).

> **Verdict:** technically sound and well-positioned. The evidence *strengthens* the three most distinctive choices — explicit placement over CUDA Unified Memory, the `>1 tok/s` refusal floor, and the measured receipt — and the flagship MoE lane is already shipping in adjacent tools (Fiddler, KTransformers, llama.cpp `--n-cpu-moe`). The product's contribution is the **planner + profiler + receipt** wrapper those tools lack. Three calibrations are required before Phase 1; one corrects a line in `architecture.md`.

## Verdict by load-bearing claim

| Claim | Status | One-line basis |
|---|---|---|
| MoE tiered offload hits usable decode | 🟢 proven (warm) · 🟡 guard-railed (cold-NVMe) | Fiddler / KTransformers / llama.cpp already exceed the floor |
| Expert skew + prefetch beats uniform | 🟢 premise holds · 🟡 spec change required | skew is *request-level*; access is *not* recency-based |
| "No UVM oversubscription on Windows/WSL" | 🟢 confirmed — the moat | NVIDIA's own docs state it verbatim |
| ±10% receipt + honest refusal | 🟡 feasible only if scoped | tight in-VRAM; static prediction misses 2–3× under heavy NVMe |
| `>1 tok/s` refusal floor is correct | 🟢 correct — will refuse dense+NVMe often | sub-1 tok/s is the documented norm there |

## Research grounding (the empirical floor)

Each finding is connected to a design implication. Citations were retrieval-verified for existence and cross-checked by two different model families for groundedness.

### MoE tiered offload — the flagship lane
1. **Warm-tier MoE offload is production-proven, not a research bet.** Fiddler (Kamahori et al. 2024, [arXiv:2402.07033](https://arxiv.org/abs/2402.07033)) runs uncompressed Mixtral-8×7B (90 GB+) at **>3 tok/s on one 24 GB GPU** by computing cold experts on CPU rather than moving weights over PCIe. → the hot/warm tier is a safe throughput claim.
2. **Heterogeneous placement scales to 671B.** KTransformers runs DeepSeek-V3/R1 671B at **~8.7–10 tok/s decode** on a single 4090D (24 GB) + 382 GB RAM, CPU-bound. → the architecture holds at the extreme; the 5090's 32 GB only widens the hot tier.
3. **The runtime you orchestrate already exposes your exact knob.** llama.cpp `--n-cpu-moe` / `-ot '…exps=CPU'` keeps attention/shared layers in VRAM and routes expert FFN to RAM — your hot/warm tiering — with field reports of **~12–14 tok/s** on huge MoEs. → **first integration target.**
4. **Consumer cards are host-to-device bandwidth bound.** Mixtral-offloading (Eliseev & Mazur 2023, [arXiv:2312.17238](https://arxiv.org/abs/2312.17238)): 2–3 tok/s, with an RTX 3060 ≈ 3080 Mobile because both saturate PCIe. → the profiler must *measure* PCIe, not trust the spec sheet.
5. **Cold-NVMe streaming is the danger zone — gate it.** "SSD Offloading … Considered Harmful" (Kyung, Yun & Ahn 2025, [arXiv:2508.06978](https://arxiv.org/abs/2508.06978)): cold-expert SSD streaming raises per-token energy **~12×**; prefetch hides latency but **not** energy. PowerInfer-2 ([arXiv:2406.06282](https://arxiv.org/abs/2406.06282)) reaches 9.96 tok/s with 50% of FFN on flash — but only with a *sparsified* model. → cold-NVMe is conditional on accurate prefetch + sparsity; default it off for experts unless the floor is cleared.

### Skew + prefetch — the premise under the flagship
6. **Skew is real but request-level.** MoE-Infinity (Xue et al. 2024, [arXiv:2401.14361](https://arxiv.org/abs/2401.14361)): <5% of experts active per request, **but skew aggregates toward uniform across diverse prompts.** → **calibration must be workload-representative + adaptive, not a one-time global histogram** (Calibration #1).
7. **Router lookahead hides the transfer.** Pre-gated MoE (Hwang et al. 2024, [arXiv:2308.12066](https://arxiv.org/abs/2308.12066)) selects the *next* layer's experts during the current layer, landing within **19% of GPU-only** latency; Fate ([arXiv:2502.12224](https://arxiv.org/abs/2502.12224)) ~99% hit; MoE-Beyond ([arXiv:2508.17137](https://arxiv.org/abs/2508.17137)) lifts cache hit 17%→72% at 10% experts resident. → a small VRAM hot tier + prefetch is sufficient.
8. **Eviction must be staleness-aware, not LRU.** SpecMD (Apple, 2026, [arXiv:2602.03921](https://arxiv.org/abs/2602.03921)): expert access is deterministic-sequential; a Least-Stale policy cuts misses **85× vs LRU**, >88% hit at 5% VRAM. → **use sequence/staleness eviction for experts** (Calibration #1).

### The Windows/WSL UVM premise — the positioning (and the moat)
9. **The premise is NVIDIA-documented, verbatim.** CUDA-on-WSL guide: *Full Managed Memory is unavailable on Windows native and WSL2 "for the foreseeable future."* CUDA C++ Programming Guide: Linux allows managed-memory oversubscription; **Windows/WSL/Tegra do not** (`cudaDevAttrConcurrentManagedAccess == 0`). → explicit placement is the *only* route on the target platform.
10. **Even where UVM exists (Linux), it's the wrong tool for decode.** NVIDIA's oversubscription blog: performance varies **up to 100×**; on-demand migration collapses ~8–10 GB/s → ~1 GB/s at 2× oversubscription, random access to *hundreds of KB/s*. Decode is bandwidth-bound ("AI and Memory Wall", Gholami et al. 2024, [arXiv:2403.14123](https://arxiv.org/abs/2403.14123)). → explicit declared placement beats blind demand-paging decisively.

### Prediction & receipt honesty
11. **Memory is exact; throughput splits.** KV-cache is closed-form/linear in context (NVIDIA). Fully in-VRAM, Vidur ([arXiv:2405.05465](https://arxiv.org/abs/2405.05465)) predicts P95 within **3.33%** → a ±10% receipt is realistic. Under heavy offload, static analytical prediction is documented as *insufficient*: roofline over-predicts and needs measured calibration (Imai et al. 2024); FlexGen's own LP "can run out of memory" and is "beaten by tuning manually" ([arXiv:2303.06865](https://arxiv.org/abs/2303.06865)); LLM-Pilot (a *learned* predictor) meets its target only **80%** of the time ([arXiv:2410.02425](https://arxiv.org/abs/2410.02425)); NVMe random QD1–4 ≪ sequential. → **scope ±10% to light offload; heavy-NVMe = "estimated, receipt-confirmed"; conservative refusal margin; recalibration loop load-bearing** (Calibration #2).

### Dense envelope & the refusal floor
12. **The floor is correct and will refuse dense+NVMe often — by design.** Single-stream offload tiers off a cliff: ~150 tok/s in-VRAM → ~60–70% at 20/32 layers on GPU → ~3–6 tok/s for 70B on DDR5 partial offload → **sub-1 tok/s once dense weights stream from NVMe** (AirLLM: 0.7 tok/s → ~1 token/*hour*). The seminal offload wins are throughput-at-large-batch, explicitly *"not suitable for latency sensitive"* (FlexGen 1 tok/s at batch 144; ZeRO-Inference 43/30 tok/s CPU/NVMe). → RAM-offload partial is the serviceable dense envelope; **reserve NVMe for cold MoE experts, not dense weights** (Calibration #3).

## The three required calibrations (before Phase 1 code)
1. **Adaptive + staleness-aware MoE calibration** — workload-representative traces, online refinement from the receipt, Least-Stale (not LRU) expert eviction. *Corrects `architecture.md` and `features.md`.* [#6, #8]
2. **Scope the ±10% receipt** to in-VRAM/light offload; heavy-NVMe plans are "estimated + receipt-confirmed"; refusal carries a conservative margin; the recalibration loop is load-bearing. [#11]
3. **Frame dense+NVMe as expected (correct) refusal**; position NVMe as the cold-MoE-expert lane, not a dense-weight-streaming lane. [#12]

## Verification receipt (Step 4 integrity)
- **Run** `wf_965f110f-e24` · 11 agents · 161 web tool-calls · 37 findings → 35 unique · **0 dropped to parametric recall** (every finding retrieval-backed at source).
- **Ensemble (≥3 decorrelated lenses):** WebFetch retrieval oracle + `mistral-small:24b` (Mistral) + `granite4.1:30b` (IBM Granite), reasoning-stripped.
- **Existence:** 35/35 resolved, **0 fabricated.** Both LLM families false-flagged real 2025–26 papers as nonexistent — discarded per the documented no-retrieval blind spot; the oracle governs existence.
- **Groundedness actions (none changed a verdict):**
  - **Dropped** 1 misattribution: "Auxiliary-Loss-Free Load Balancing" ([arXiv:2408.15664](https://arxiv.org/abs/2408.15664)) is a real, correctly-attributed paper, but the *inference-skew* claim is not in it (it is training-only). The skew premise survives on #6 (MoE-Infinity) + MoE-Beyond + SpecMD.
  - **Dropped** 1 source for unsupported numbers: a `localllm.in` page that was actually about different models.
  - **Corrected** ~8 sub-figures (KTransformers 10.3 → ~8.7 tok/s drift; ExpertFlow's "95%" unsupported; FlexGen "9 vars" → 11; a Pre-gated SQuAD misread; attribution fixes on the NVIDIA blog, the SSD-hierarchy outlet, and the MoE-Beyond year).
  - **Flagged:** SpecMoEOff is speculative *decoding* (more tokens verified per transfer), not predictive *prefetch* — do not cite it as prefetch evidence.

*Swarm script (replayable):* `…/workflows/scripts/gpu-container-feasibility-study-swarm-wf_965f110f-e24.js`
