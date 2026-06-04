# Core Features

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

**Supported backends:**
- **llama.cpp** (`llama-server`): `--n-gpu-layers`, `--mlock`, `--mmap`, `--ctx-size`
- **vLLM**: `--gpu-memory-utilization`, `--max-model-len`, `--enforce-eager`, `--cpu-offload-gb`, quantization flags
- **HF Accelerate**: `device_map` dict (layer→device assignment), `max_memory` per device
- **ExLlamaV2**: GPU split config, cache quantization
- **TensorRT-LLM**: engine build config with weight streaming

**Plan generation logic:**
1. Take hardware profile + model profile
2. Compute: do weights fit in VRAM? With KV cache at target context?
3. If yes → full-GPU plan
4. If no → compute split point (which layers CPU, which GPU)
5. For MoE → compute expert placement (hot/warm/cold tiers)
6. Emit: launch command, expected memory map, predicted bottleneck

**Refusal mode:** If no viable plan exists (model too large even with full offload, or throughput would be < 1 tok/s), the planner says "no" and explains why.

## 4. Placement Receipt

Post-launch measurement that proves the plan worked (or didn't).

**Captures:**
- Actual VRAM usage (via NVML) vs planned
- Actual RAM usage (RSS, pinned) vs planned
- Actual disk I/O during inference (if any)
- Token generation speed: prefill tok/s, decode tok/s
- Time-to-first-token (TTFT)
- KV cache utilization and eviction rate
- Thermal throttle events (if GPU clock dropped)

**Format:** JSON receipt + human-readable summary.

**Comparison mode:** Run receipt against plan → flag deviations > 10%.

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
