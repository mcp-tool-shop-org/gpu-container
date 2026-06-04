# Architecture

## Memory Tier Model

Three explicit placement tiers. No magic overflow — every byte has a declared home.

### Tier 0: VRAM (GPU HBM / GDDR)

- Active layer weights during forward pass
- Attention activations
- KV cache working set (hot tokens)
- MoE: always-active shared layers (attention, embeddings, LM head)

Constraints: hard ceiling = physical VRAM. On RTX 5080 = 16 GB. On RTX 5090 = 32 GB.

### Tier 1: Pinned Host RAM (CPU)

- Offloaded weight shards (layer-by-layer or expert-by-expert)
- KV cache spill (evicted pages, reusable prefixes)
- MoE: warm experts (recently activated, likely to fire again)
- Prefetch staging for Tier 0

Transfer: PCIe Gen5 x16 = ~64 GB/s theoretical, ~50 GB/s sustained.

### Tier 2: NVMe / Disk

- Full model shards (mmap'd safetensors)
- Cold MoE experts (rarely activated)
- KV cache archive (long-context cold pages)
- Checkpoint/snapshot storage

Transfer: Gen4 NVMe = ~7 GB/s seq read. Gen5 = ~14 GB/s. Random = much lower.

## Data Flow

```
Request arrives
  → Scheduler checks KV cache hit (Tier 0 → serve immediately)
  → If miss: check Tier 1 (pinned RAM KV) → async copy to Tier 0
  → If cold miss: Tier 2 (NVMe) → stream to Tier 1 → prefetch to Tier 0
  → Forward pass executes entirely in Tier 0
  → KV eviction: Tier 0 overflow → spill to Tier 1 (LRU/ARC policy)
```

## MoE Expert Routing

MoE models (Mixtral, DBRX, DeepSeek-V2/V3, Qwen3-MoE) are the high-leverage case:

- **Shared layers** (attention, embeddings, output head): always Tier 0
- **Hot experts** (top-N most frequently routed): Tier 0 if space, else Tier 1
- **Warm experts** (activated in last K requests): Tier 1
- **Cold experts** (rarely activated): Tier 2

The planner pre-computes expert activation frequency from **workload-representative** calibration traces to generate an **initial** placement plan, then **refines it online** from the receipt's measured routing.

> ⚠️ **Calibration must be workload-representative and adaptive — not a one-time global histogram.** Expert activation is skewed only at the *request* level and aggregates toward *uniform* across diverse prompts ([MoE-Infinity, arXiv:2401.14361](https://arxiv.org/abs/2401.14361)), so a single generic-corpus snapshot mis-tiers out-of-distribution workloads and thrashes the warm tier.
>
> ⚠️ **Expert eviction is staleness/sequence-aware, NOT LRU/LFU.** MoE expert access is deterministic-sequential, not recency-based; a Least-Stale policy cuts collision misses up to 85× vs LRU ([SpecMD, arXiv:2602.03921](https://arxiv.org/abs/2602.03921)). (The LRU/ARC policy used for KV-cache spill is correct *there* — it is wrong for experts.)

See [feasibility.md](feasibility.md) findings #6 and #8 for the evidence.

## Product Boundaries

| Layer | Responsibility | This project owns? |
|-------|---------------|-------------------|
| Docker + NVIDIA Container Toolkit | GPU passthrough, isolation, reproducibility | Config only |
| CUDA / cuDNN / cuBLAS | Compute kernels | No — consumed |
| Inference runtime (vLLM, llama.cpp, etc.) | Execution, scheduling, batching | No — orchestrated |
| **Memory planner** | Decide placement, generate configs, validate | **Yes — core** |
| **Hardware profiler** | Detect capabilities, measure bandwidth | **Yes — core** |
| **Model profiler** | Analyze architecture, estimate memory | **Yes — core** |
| **Receipt system** | Measure and report actual placement | **Yes — core** |

## Container Strategy

```dockerfile
# Base: NVIDIA CUDA runtime (not devel — smaller)
FROM nvidia/cuda:12.8-runtime-ubuntu24.04

# Inference runtimes installed as backends
# Planner runs as orchestration layer above them
```

The container is the packaging boundary. The planner runs inside the container with full visibility into GPU state via `nvidia-smi`, `nvml`, or `pynvml`.
