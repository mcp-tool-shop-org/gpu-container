# ADR-0001 — Per-expert cache: consume the mechanism, contribute the policy

**Status:** Accepted · 2026-06-04
**Context source:** docker-knowledge wave-4 (moe-placement lane); [llama.cpp #20757](https://github.com/ggml-org/llama.cpp/issues/20757)
**Supersedes:** the "open decision" noted in [`moe-lane-architecture.md`](../moe-lane-architecture.md) Phase-2 block.

## Context

Per-expert hot/warm/cold tiering needs a runtime expert-slot cache: stock llama.cpp stores a layer's experts as one fused tensor, so `-ot` places at per-layer grain only (wave-4, verified). llama.cpp `#20757` is an active upstream feature request for exactly that cache (`--moe-expert-cache-size N`, `expert_id→slot` map, PoC 12–14 tok/s vs 0.5–1) — but its proposed eviction set is LRU/SLRU/LFU/FIFO, and it includes **no** Least-Stale eviction and **no** cross-layer-gate prefetch. Those two policies are the research-backed differentiators wave-4 identified.

gpu-container's moat is the **placement policy + calibration + receipt + refusal** ("owns: planner, profiler, receipt; consumes: the runtimes"). A kernel-level slot copy is plumbing, not placement intelligence.

## Decision

**Option B — consume the mechanism, contribute the policy.**

- **Consume** `#20757`'s slot-cache *mechanism* (the `expert_id→slot` GPU buffer + persistence) rather than reimplementing it.
- **Own + contribute the *policy*:** Least-Stale eviction (SpecMD) and cross-layer-gate prefetch (Fate/AdapMoE), offered to `#20757` as a pluggable policy.
- **Keep in-product:** the `eval-callback` trace harness, the calibration/recalibration loop, the receipt, and the refusal — the moat.

Rejected:
- **A (pure consumer)** — if upstream ships LRU-only, our per-expert tier has no differentiation; and we'd be blocked on a merge we don't control.
- **C (fork/own the cache)** — a patch on fast-moving llama.cpp is a maintenance treadmill for a 1-human studio, and it sits *outside* the moat (kernel memory-copy, not placement intelligence).

## Consequences

**Positive** — plumbing stays community-maintained (no rebase treadmill); effort concentrates on the differentiators; the decision is *decoupled* from near-term work (below).

**Risks / mitigations** — dependence on `#20757`'s interface shape and merge timeline; upstream may decline a niche eviction policy. *Mitigation:* if the policy can't land upstream, hold it in a **thin adapter above the stock byte-offset copy** (the `#20757` hook point) — still not a full fork.

## Near-term plan (unblocked — needs no cache, no upstream change)

Build and prove against **per-layer** granularity first; the per-expert cache is an increment, not a prerequisite:
1. ✅ **Trace capture (built):** `llama-imatrix` → per-expert `.counts` → L×E `ActivationTrace` (`gpu_container/planner/activation.py`). This is the prebuilt path; the originally-planned `eval-callback` harness needs llama.cpp headers absent from the runtime image.
2. Per-layer calibrated placement via `-ot` + the shared/attention-in-VRAM hot tier.
3. The recalibration loop + receipt, against per-layer placement.

## Empirical de-risk result (2026-06-04)

Before building anything, we ran the gate on the real model. Captured a per-expert activation trace from **Qwen3-30B-A3B-Q4_K_M** with `llama-imatrix` (the per-expert `.counts` in `imatrix.gguf`), at **N=0** (all experts in VRAM — the safe config), in-container on the RTX 5090; parsed to an `ActivationTrace`; scored with `analyze_concentration` (90% coverage target).

| workload | tokens | experts for 90% coverage | concentration (1−norm. entropy) | top expert | `cache_helps` |
|---|---|---|---|---|---|
| diverse (prose/code/math) | ~1k | 65/128 (51%) | 0.111 | 4.3% | no |
| narrow (single-domain Python) | ~8k | 58/128 (45%) | 0.154 | 6.3% | barely |

**Verdict: the per-expert cache is NOT worth building for Qwen3-30B-A3B.** Routing is **near-uniform** — even the narrow, single-domain workload needs ~45% of experts resident to cover 90% of routing, with no dominant expert. Request-level skew is real but **modest**: narrow is measurably more concentrated than diverse, and that signal is trustworthy because narrow was *better*-sampled (8k vs 1k tokens) yet *more* concentrated, and more sampling *reduces* concentration bias. The likely cause is by design — modern MoEs train with **load-balancing auxiliary losses** that spread routing evenly, training away the very skew a hot-expert cache would exploit.

This is the gate doing its job: it turns "should we build `#20757`?" into a number, and for this model the number says **hold** — the build would buy ~nothing here. The cache pays off only for a model/workload scoring `cache_helps` with a **low** `hot_frac` (≈ < 0.25), which Qwen3 does not approach.

**Caveats:** one model, two workloads; the diverse trace is under-sampled (but under-sampling can only *exaggerate* concentration, so "diverse is uniform" is robust); 90%/50% are tunable — the *numbers*, not the boolean, are the output. Reproducible: `llama-imatrix -m <gguf> -f <corpus> -ngl 99 --no-ppl -o imatrix.gguf` → per-layer `ffn_down_exps.weight.counts` → `analyze_concentration`.

## Revisit trigger

Build the per-**expert** tier (engaging `#20757` per this decision) when **both** hold: (a) a target model/workload **passes the concentration gate with a low `hot_frac`** (≈ < 0.25 of experts for 90% coverage) — the routing is actually skewed enough to exploit, which **Qwen3-30B-A3B is not** (see the de-risk above); **and** (b) per-**layer** placement leaves decode **below the calibrated band** or **thrashes the warm tier**. Re-run the gate per target model — it is cheap (one N=0 `imatrix` pass). Until both hold, per-layer is sufficient and the cache is premature.
