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
1. `eval-callback` trace harness → L×E activation matrix (<1% overhead).
2. Per-layer calibrated placement via `-ot` + the shared/attention-in-VRAM hot tier.
3. The recalibration loop + receipt, against per-layer placement.

## Revisit trigger

Build the per-**expert** tier (engaging `#20757` per this decision) when, for a target model, per-**layer** placement leaves decode **below the calibrated band** or the warm tier **thrashes at layer granularity**. Until then, per-layer is sufficient and the cache is premature.
