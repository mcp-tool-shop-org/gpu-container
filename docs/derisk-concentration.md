# De-risking the per-expert cache: the concentration gate

The flagship MoE lane has a deep half — **per-expert** tiering: keep the hottest experts in VRAM, the warm ones in pinned RAM, the cold ones on NVMe. It's the highest-leverage idea in the product *if the routing is skewed enough to exploit*. If a model's routing is near-uniform, a hot-expert cache buys almost nothing — you'd build a runtime cache, a slot map, and an eviction policy to win a few percent.

So before building anything, we measure. The **concentration gate** turns "should we build the per-expert cache?" into a number. This doc is the method; the decision it backs is [ADR-0001](decisions/0001-per-expert-cache-build-vs-upstream.md); the code is [`gpu_container/planner/activation.py`](../gpu_container/planner/activation.py); the command is [`gpu-container-concentration`](cli.md#gpu-container-concentration).

## Why *per-expert*, and why it's a separate question

Stock llama.cpp stores a layer's experts as **one fused tensor** (`blk.N.ffn_*_exps.weight`), so `--override-tensor` / `-ot` places at **per-layer** grain only — it can put *all* of a layer's experts on CPU or *all* in VRAM, never "expert 7 but not expert 12." Per-expert hot/warm/cold tiering therefore needs a **runtime expert-slot cache** (the llama.cpp [#20757](https://github.com/ggml-org/llama.cpp/issues/20757) mechanism: an `expert_id → slot` GPU buffer), not a launch flag. See [moe-lane-architecture.md](moe-lane-architecture.md).

That matters for what to measure. Per-**layer** *total* activation is ~uniform — every token hits every layer's top-k experts, so "which layer is hot" carries no signal. The exploitable signal is **per-expert concentration *within* a layer**: across a workload, do a few experts in each layer capture most of the routing? Only the runtime cache can act on that.

## Two measures

The gate reports two numbers per layer and aggregates them. Both, deliberately — one is actionable, one is threshold-free.

### `hot_frac_for_coverage` — the actionable number

The fraction of a layer's experts that must be **resident (hottest-first)** to capture `coverage_target` (default 90%) of that layer's routing mass.

```
sort experts by count, descending
walk down accumulating mass until you've covered `target` of the total
hot_frac = (experts walked) / (total experts)
```

- **Low** (say 0.10) ⇒ concentrated: a cache holding 10% of experts covers 90% of routing — build it.
- **≈ target** (say 0.90 at a 0.90 target) ⇒ uniform: you need almost every expert resident to cover the mass — a cache wins nothing.

This maps straight to a cache size (`#20757`'s `--moe-expert-cache-size`). The report's headline `hot_frac_for_coverage` is the **median over layers**.

### `concentration_score` — the threshold-free number

```
concentration_score = 1 − normalized_entropy
normalized_entropy = Shannon_entropy(routing distribution) / log(E)
```

- `0.0` = perfectly uniform (every expert equally used).
- `1.0` = all mass on a single expert.

Entropy doesn't depend on the arbitrary 90% coverage target, so it's a robust cross-check on `hot_frac` (which does). The report's `concentration_score` is the **mean over layers**; `top1_share` (the single hottest expert's routing share, median over layers) is reported too as a sanity anchor.

### The boolean is a convenience, never the output

`cache_helps = (median hot_frac < threshold)` (default threshold `0.50`). It's a one-glance gate. **The numbers are the output** — `cache_helps` collapses them to a yes/no at one tunable cut point, and the report always carries the underlying `hot_frac`, `concentration_score`, and `top1_share` so you can re-decide at your own threshold.

## The capture path

The gate consumes an L×E count matrix (`ActivationTrace`). On this rig the working capture path is **`llama-imatrix`**:

```bash
# in the prebuilt llama.cpp:full-cuda container, N=0 (all experts in VRAM — the safe config):
llama-imatrix -m model.gguf -f corpus.txt -ngl 99 --no-ppl -o imatrix.gguf
```

`llama-imatrix` records, per MoE layer, a `blk.N.ffn_down_exps.weight.counts` array — exactly the per-expert selection counts the gate needs. `gpu-container-concentration --imatrix` reads them directly (via the optional `gguf` package):

```bash
gpu-container-concentration --imatrix imatrix.gguf --model-name Qwen3-30B-A3B
```

> The originally-planned `eval-callback` harness (an in-process L×E matrix) needs llama.cpp headers that the runtime image doesn't ship — so `imatrix` → `.counts` is the path that actually works here. If you have a trace from another source, hand it in as `--trace trace.json` (dependency-free).

`--coverage` (the mass target) and `--threshold` (the `cache_helps` cut) are both tunable; the numbers move predictably with them, the verdict is just a cut on the numbers.

## The real result — Qwen3-30B-A3B routes near-uniform

We ran the gate on the real model: a per-expert trace from **Qwen3-30B-A3B-Q4_K_M**, captured at N=0 in-container on the RTX 5090 (the first GPU run after the 2026-06-04 incident — memory never above ~1.6 GB used / 26+ GB free throughout; the safe envelope held), scored at a 90% coverage target.

| workload | tokens | experts for 90% coverage | concentration (1 − norm. entropy) | top expert | `cache_helps` |
|---|---|---|---|---|---|
| diverse (prose / code / math) | ~1k | 65/128 (**51%**) | 0.111 | 4.3% | no |
| narrow (single-domain Python) | ~8k | 58/128 (**45%**) | 0.154 | 6.3% | barely |

**Verdict: the per-expert cache is NOT worth building for Qwen3-30B-A3B.** Even the narrow, single-domain workload needs ~45% of experts resident to cover 90% of routing, with no dominant expert (top expert 6.3%). Request-level skew is real but **modest** — narrow is measurably more concentrated than diverse, exactly as theory predicts — and the signal is trustworthy: the narrow trace was *better*-sampled (8k vs 1k tokens) yet *more* concentrated, and more sampling can only *reduce* apparent concentration. So "diverse is near-uniform" is robust (under-sampling can only *exaggerate* concentration, never hide it).

**The likely cause is by design.** Modern MoEs train with **load-balancing auxiliary losses** that deliberately spread routing evenly across experts — training away the very skew a hot-expert cache would exploit. A cache fights the model's own training objective.

This is the gate doing its job: it converted a tempting build into a measured **hold**, saving the work. The cache pays off only for a model/workload that passes with a **low** `hot_frac` (≈ < 0.25), which Qwen3 does not approach.

## The caveat that travels with every verdict

**Concentration is workload-dependent.** Request-level expert skew flattens toward uniform across diverse prompts ([MoE-Infinity, Xue et al. 2024, arXiv:2401.14361](https://arxiv.org/abs/2401.14361)) — so a trace is only valid for the workload it was cut from. A diverse-prompt trace reads *less* concentrated than a narrow one (you can see it in the table above). The report states this on every run. If your production workload is narrow and repetitive, cut your trace from *that* — don't inherit a verdict from a generic corpus.

The gate also sanity-checks the trace: per-layer totals should be ~uniform (every token hits every layer's top-k), so a >20% spread across layers flags a malformed trace or a wrong `experts_per_token` / `n_tokens`.

## When to revisit (the trigger)

Build the per-**expert** tier (engaging `#20757` per ADR-0001) only when **both** hold:

1. A target model/workload **passes the gate with a low `hot_frac`** (≈ < 0.25 of experts for 90% coverage) — routing actually skewed enough to exploit. Qwen3-30B-A3B is not close; **re-run the gate per target model** (it's cheap — one N=0 `imatrix` pass).
2. Per-**layer** placement (via `-ot` + the shared/attention-in-VRAM hot tier) leaves decode **below the calibrated band** or **thrashes the warm tier** — i.e. you've actually run out of per-layer headroom.

Until both hold, per-layer placement is sufficient and the cache is premature. The decision is logged, with evidence, in [ADR-0001](decisions/0001-per-expert-cache-build-vs-upstream.md).
