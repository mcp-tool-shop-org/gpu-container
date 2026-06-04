---
title: The MoE Lane
description: The flagship — explicit expert tiering across VRAM, pinned RAM, and NVMe.
sidebar:
  order: 3
---

Mixture-of-Experts models are the high-leverage case: Mixtral-8×7B is 47B params but only 13B active per token; DeepSeek-V3 is 671B with 37B active. Most experts sit cold. Without placement you OOM (all experts in VRAM) or crawl (all in RAM). With placement: hot in VRAM, warm in RAM, cold on NVMe — fits *and* fast.

## The three tiers

| Tier | Holds | Bound by |
|---|---|---|
| **VRAM** | always-active shared/attention layers, hot experts, KV working set | physical VRAM (hard ceiling) |
| **Pinned RAM** | warm experts, KV spill, prefetch staging | PCIe (~50 GB/s sustained, measured) |
| **NVMe** | cold experts (gated), cold KV | random-QD1 (≪ sequential — the number that matters) |

> No magic overflow — every byte has a declared home. CUDA Unified-Memory oversubscription is unavailable on Windows/WSL2 (NVIDIA-confirmed) and the wrong tool for decode even on Linux.

## What ships today: per-layer tiering

llama.cpp `--n-cpu-moe N` keeps attention + shared layers in VRAM and routes the first **N MoE layers' experts to CPU RAM** (computed on CPU, KTransformers-style — not PCIe streaming). Raise N to fit, lower for speed. The planner computes the minimal N that fits VRAM, and refuses if even all-experts-on-CPU won't clear the floor.

**Proven live** on Qwen3-30B-A3B-Q4_K_M (RTX 5090, in-container):

| N | ceiling tok/s | measured decode | realized | floor |
|---|---|---|---|---|
| 0 | 738 | 302.4 | 41% (overhead-bound) | cleared |
| 24 | 69 | 41.9 | 61% (CPU-bw-bound) | cleared |
| 48 | 36 | 20.4 | 56% | cleared |

## The recalibration loop

The closed-form decode estimate is a **roofline ceiling** — peak bandwidth, zero overhead, a true upper bound. Real decode is a fraction of it. So the planner emits a **calibrated forecast with a band**:

```
ceiling (closed form) × realized efficiency (measured) = calibrated forecast ± band
```

A receipt records `measured ÷ ceiling` as a calibration point; the next plan scales its ceiling by the fitted efficiency. The verifier is a real `llama-bench` run — a *different mechanism* than the planner's math.

## Per-expert tiering is gated on a measurement

True hot/warm/cold tiering *within* a layer needs a runtime expert-slot cache, because stock llama.cpp stores a layer's experts as one fused tensor (`-ot` is per-layer only). Before building that cache for a model, the [concentration gate](./derisk/) measures whether the routing is even skewed enough to be worth it. On Qwen3-30B-A3B it isn't (near-uniform) — so the per-layer hot tier ships now, and the per-expert cache waits for a model that passes the gate.
