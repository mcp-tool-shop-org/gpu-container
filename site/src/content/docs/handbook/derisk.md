---
title: Routing De-risk
description: Measure whether a model's MoE routing is skewed enough to cache — before building for it.
sidebar:
  order: 4
---

The per-expert cache is the highest-leverage idea in the product *if the routing is skewed enough to exploit*. If routing is near-uniform, a hot-expert cache buys almost nothing. So before building anything, **measure**. The concentration gate turns "should we build the per-expert cache?" into a number.

```bash
gpu-container-concentration --imatrix imatrix.gguf --model-name Qwen3-30B-A3B
```

## Two measures

Given an activation trace (which experts fired, per layer, over a representative workload):

- **`hot_frac_for_coverage`** — the fraction of a layer's experts that must be resident (hottest-first) to capture 90% of its routing mass. The actionable number; maps to a cache size. **Low** = concentrated (build it); **≈ 0.90** = uniform (a cache wins nothing).
- **`concentration_score = 1 − normalized_entropy`** — a threshold-free [0,1] skew measure (0 = uniform, 1 = one expert). A robust cross-check on `hot_frac`.

`cache_helps` is a convenience gate (`median hot_frac < threshold`); the **numbers are the output**.

## The capture path

```bash
# in the prebuilt llama.cpp container, N=0 (all experts in VRAM — the safe config):
llama-imatrix -m model.gguf -f corpus.txt -ngl 99 --no-ppl -o imatrix.gguf
```

`llama-imatrix` records a per-MoE-layer `ffn_down_exps.weight.counts` array — exactly the per-expert selection counts the gate needs. `--imatrix` reads them directly (via the optional `gguf` package); `--trace` accepts a hand-built L×E counts JSON (dependency-free).

## The real result — Qwen3 routes near-uniform

| workload | tokens | experts for 90% coverage | concentration | top expert | `cache_helps` |
|---|---|---|---|---|---|
| diverse (prose/code/math) | ~1k | 65/128 (**51%**) | 0.111 | 4.3% | no |
| narrow (single-domain Python) | ~8k | 58/128 (**45%**) | 0.154 | 6.3% | barely |

**Verdict: the per-expert cache is NOT worth building for Qwen3-30B-A3B.** Even the narrow workload needs ~45% of experts resident, with no dominant expert. The likely cause is by design — modern MoEs train with **load-balancing auxiliary losses** that spread routing evenly, training away the very skew a cache would exploit.

## The caveat that travels with every verdict

**Concentration is workload-dependent.** Request-level skew flattens toward uniform across diverse prompts (MoE-Infinity, [arXiv:2401.14361](https://arxiv.org/abs/2401.14361)) — so a trace is only valid for the workload it was cut from. If your production workload is narrow and repetitive, cut your trace from *that*.

## When to revisit

Build the per-expert tier only when **both** hold: (1) a model/workload passes with a **low `hot_frac`** (≈ < 0.25), and (2) per-layer placement leaves decode below the calibrated band. Re-run the gate per target model — it's cheap (one N=0 imatrix pass).
