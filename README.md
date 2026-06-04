# gpu-container

> **A GPU-enabled container exposes the device. A model-aware runtime decides what lives in VRAM, pinned RAM, and NVMe.**

Run the largest useful local model your machine can honestly support, with explicit placement plans, benchmark receipts, and refusal when the plan would thrash.

## Architecture

```
Windows / WSL2 / Linux host
  └─ GPU-enabled Docker container
      └─ Inference runtime
          ├─ VRAM: hot weights, active layers, activations, KV working set
          ├─ pinned RAM: CPU-offloaded weights, MoE experts, KV spill/reuse
          └─ NVMe: mmap shards, disk offload, cold experts, cold KV
```

## Product Boundary

```
Docker         = packaging + GPU exposure
CUDA/runtime   = compute backend
Planner        = memory law
Inference engine = execution
```

## Core Features

1. **Hardware profiler** — Detect VRAM, RAM, GPU type, WSL/native Linux, NVMe speed, CUDA availability
2. **Model profiler** — Detect dense vs MoE, largest layer, total weights, quantization, KV growth by context length
3. **Runtime planner** — Generate launch plans for llama.cpp, vLLM, Accelerate, TensorRT-LLM, or DeepSpeed-style offload
4. **Placement receipt** — Show what is in VRAM, what is in RAM, what is on disk, expected bottleneck, measured tokens/sec
5. **MoE-specialized path** — Keep always-active layers on GPU, route experts to CPU/RAM, NVMe for cold fallback

## Key Constraint

On Windows/WSL, CUDA Unified Memory oversubscription is **not the path**. CUDA treats Windows/WSL as limited unified-memory support — no fine-grained GPU page-fault migration, no GPU-memory oversubscription beyond physical VRAM. This product is **explicit inference memory placement**, not "Docker VRAM overflow."

## Status

Phase 0 — product definition and research.
