# Core Features

Seven features. The profiler, planner, receipt + recalibration loop, routing de-risk gate, and rig-safety watchdog are **built and proven on the dev rig** (RTX 5090 / WSL2); the multi-backend planner and per-expert tiering are **partly built** — llama.cpp `--n-cpu-moe` is the shipping integration, the other runtimes are designed targets, and per-expert tiering is gated behind the de-risk result (see feature 5). Each section notes what's shipping vs designed.

## 1. Hardware Profiler

Detects and benchmarks the host machine's inference capabilities.

**Outputs:**
- GPU: model, VRAM total/free, compute capability, PCIe generation/width
- RAM: total/available, NUMA topology, pinnable ceiling
- Storage: NVMe sequential read bandwidth (measured), available space
- Platform: native Linux vs WSL2 vs Windows, CUDA version, driver version
- Container runtime: Docker GPU support, NVIDIA Container Toolkit version

**Key measurements:**
- GPU↔CPU bandwidth (PCIe): measured via `cudaMemcpy` H2D/D2H timing
- NVMe throughput: sequential read of temp file (bypass page cache)
- VRAM fragmentation: largest contiguous allocation possible

**Why it matters:** The planner cannot generate honest plans without measured (not spec-sheet) numbers.

## 2. Model Profiler

Analyzes a model's architecture and memory requirements before loading.

**Inputs:** HuggingFace model ID, local safetensors path, or GGUF file.

**Outputs:**
- Architecture type: dense, MoE (num experts, top-k), hybrid
- Parameter count and dtype breakdown (by layer group)
- Largest single layer memory requirement
- KV cache growth formula: `bytes_per_token = n_layers × 2 × n_kv_heads × head_dim × dtype_size`
- Expert structure (MoE): shared params vs expert params, routing type
- Quantization: detected quant format (GPTQ, AWQ, GGUF Q-level, FP8, etc.)
- Context length configurations: memory at 2K, 4K, 8K, 16K, 32K, 64K, 128K tokens

**Why it matters:** You can't place what you can't measure.

## 3. Runtime Planner

Generates explicit launch configurations for supported inference runtimes.

**Backends:**
- **llama.cpp** — ✅ **shipping**. The planner emits the exact `--n-cpu-moe N` (+ `-fa on`, `-ngl`, ctx) launch string and verifies it with a real `llama-bench` receipt. This is the integration the closed loop is proven on.
- **vLLM** — designed: `--gpu-memory-utilization`, `--max-model-len`, `--enforce-eager`, `--cpu-offload-gb`, quantization flags.
- **HF Accelerate** — designed: `device_map` dict (layer→device assignment), `max_memory` per device.
- **ExLlamaV2** — designed: GPU split config, cache quantization.
- **TensorRT-LLM** — designed: engine build config with weight streaming.

> The placement *math* (fit, split point, KV budget, roofline ceiling, refusal) is backend-agnostic; each backend needs its own flag-emitter + receipt parser. llama.cpp `--n-cpu-moe` was first because it's the closest match to the MoE lane and ships today.

**Plan generation logic:**
1. Take hardware profile + model profile
2. Compute: do weights fit in VRAM? With KV cache at target context?
3. If yes → full-GPU plan
4. If no → compute split point (which layers CPU, which GPU)
5. For MoE → compute expert placement (hot/warm/cold tiers)
6. Emit: launch command, expected memory map, predicted bottleneck

**Refusal mode:** If no viable plan exists (model too large even with full offload, or throughput would be < 1 tok/s), the planner says "no" and explains why.

## 4. Placement Receipt

Post-launch measurement that proves the plan worked (or didn't) — and feeds the next plan. ✅ **Shipping** (`gpu-container-receipt`), with the recalibration write-back.

**Captures today** (parsed from `llama-bench -o json`, paired with the plan):
- Decode tok/s and prefill tok/s (measured)
- **Realized efficiency** = measured ÷ roofline ceiling — the calibration seed
- **Decode error** vs the plan's *calibrated* forecast, and **within_band** (did measured land inside the calibrated band? — the loop's proof)
- **cleared_floor** — did it beat the >1 tok/s refusal floor?
- Measured VRAM vs predicted (when supplied via `--vram-used-mib`)
- **Routing de-risk verdict** folded in via `--trace` (feature 6)
- **Safety envelope** folded in via `--peaks` — peak power / host-mem / VRAM from a supervised run, and whether it `stayed_within_envelope` (feature 7)

**Format:** JSON receipt + human-readable note lines.

**The recalibration loop:** with `--calibration-dir` + `--model-name`, the receipt appends a `CalibrationPoint`, so the next plan for that model shape is calibrated from real measurements. The verifier is a real GPU run — a *different mechanism* than the planner's closed form (EXTERNAL_VERIFIER).

**ANDON exit codes:** `0` cleared the floor at/below ceiling · `3` below the floor · `4` *exceeded* the ceiling (the bandwidth model is wrong — halt, don't just recalibrate).

*Designed, not yet captured:* RSS/pinned RAM, disk I/O during inference, TTFT, KV utilization/eviction rate, and thermal-throttle events. (Peak GPU temperature is already captured by the watchdog envelope.)

## 5. MoE-Specialized Path

The highest-leverage optimization target. MoE models waste VRAM on cold experts.

**Strategy:**
- Identify shared layers (always GPU): attention blocks, embeddings, LM head, router
- Profile expert activation patterns (from calibration prompts or published statistics)
- Generate tiered expert placement:
  - Tier 0 (VRAM): top-N most activated experts
  - Tier 1 (pinned RAM): next-M experts with async prefetch on route prediction
  - Tier 2 (NVMe): remaining cold experts, loaded on demand

**Expert prefetch:**
- Router output predicts next-layer expert selection
- Prefetch candidate experts from Tier 1→Tier 0 during current-layer compute
- Overlaps data movement with compute (hides latency when bandwidth allows)

**Calibration (must be workload-representative + adaptive):**
- Run N **workload-representative** prompts — not a generic corpus. Request-level skew aggregates toward uniform across diverse prompts ([MoE-Infinity, arXiv:2401.14361](https://arxiv.org/abs/2401.14361)), so one generic snapshot mis-tiers out-of-distribution workloads. Support per-workload activation-pattern profiles.
- Record per-expert activation frequency per layer
- Generate an **initial** placement map from the histogram, then **refine online** from the receipt's measured routing (closes the calibrate → receipt → recalibrate loop)
- **Eviction:** staleness/sequence-aware (e.g. Least-Stale), **not** LRU/LFU — expert access is deterministic-sequential, not recency-based ([SpecMD, arXiv:2602.03921](https://arxiv.org/abs/2602.03921))

**Why MoE is the product's highest-value lane:**
- Mixtral 8x7B: 47B params but only 13B active per token. 34B of experts sit cold.
- DeepSeek-V3: 671B params, 37B active. Most experts are rarely touched.
- Without placement: all experts in VRAM → OOM or all in RAM → slow.
- With placement: hot experts in VRAM, warm in RAM, cold on disk → fits + fast.

**Built today vs gated:** the **per-layer** hot tier ships now — llama.cpp `--n-cpu-moe` / `-ot` keep attention/shared layers in VRAM and route a layer's experts to CPU RAM (proven live on Qwen3-30B-A3B). True **per-expert** tiering (Tier 0/1/2 *within* a layer) needs a runtime expert-slot cache, because stock llama.cpp stores a layer's experts as one fused tensor — so it's **gated behind the de-risk gate** (feature 6) and the upstream [#20757](https://github.com/ggml-org/llama.cpp/issues/20757) mechanism, per [ADR-0001](decisions/0001-per-expert-cache-build-vs-upstream.md). Don't build the cache until a model's routing is measured skewed enough to exploit.

## 6. Routing De-risk Gate

✅ **Shipping** (`gpu-container-concentration`). Before building per-expert caching for a model, measure whether its routing is even skewed enough to cache.

**What it measures** (from an activation trace — which experts fired, per layer):
- `hot_frac_for_coverage` — fraction of a layer's experts that must be resident to capture 90% of its routing (the actionable cache-size number)
- `concentration_score = 1 − normalized_entropy` — a threshold-free [0,1] skew measure (0 = uniform, 1 = one expert)
- `cache_helps` — a convenience gate on the numbers (never a substitute for them)

**Capture path:** `llama-imatrix` → per-expert `.counts` → L×E trace → the gate. Exit `0` = a per-expert cache is NOT justified (the common "hold"); `5` = it could help.

**The real result:** Qwen3-30B-A3B routes **near-uniform** (needs ~45–51% of experts for 90% coverage, no dominant expert) → the cache is **on hold with evidence** for that model. Load-balancing auxiliary losses train the skew away. Concentration is **workload-dependent** — a trace is only valid for the workload it was cut from. Full method + numbers: [derisk-concentration.md](derisk-concentration.md).

## 7. Rig-safety Watchdog

✅ **Shipping** (`gpu-container-watchdog`). The safety control plane, born from a real incident (a too-large model drove host memory to 92–98% and throttled the machine). It has two modes.

**Monitor** — poll GPU power/temp/VRAM (worst-case across all GPUs) + **host memory** (the incident metric) against configurable thresholds; emit `ok` / `warn` / `abort` (exit `0` / `5` / `7`, JSON) for an AI or an autonomous `--watch` loop. Default action is `alert` (surface, never auto-kill); `--on-breach wsl-shutdown` opts into autonomous abort.

**Supervisor** — `gpu-container-watchdog run -- <command>` launches a GPU job as a child, polls in parallel, and on a hard breach runs `kill-job` (terminate just the child — a soft abort) or the catastrophic `wsl-shutdown`. This is the recommended way to run any GPU job: one self-monitoring command. `--peaks-out` records the run's peak envelope, which `gpu-container-receipt --peaks` folds into the receipt — proof a run stayed inside the rig's limits.

**Honest by construction:** a missing metric is `None`, never `0`; `mem_source` tags whether `psutil` read the Windows host or a WSL2 VM (the incident metric is the *host* — run the watchdog on Windows); exit codes are a stable scriptable contract. Defaults ship in [`watchdog.example.json`](../watchdog.example.json).
