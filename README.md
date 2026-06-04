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
6. **Routing de-risk** — Measure whether a model's MoE routing is skewed enough that a per-expert cache would help, before building for it (`gpu-container-concentration`)
7. **Rig-safety watchdog** — Poll GPU power/temperature/VRAM + host memory against configurable thresholds; an AI agent or an autonomous loop aborts a run before it endangers the machine (`gpu-container-watchdog`)

## Key Constraint

On Windows/WSL, CUDA Unified Memory oversubscription is **not the path**. CUDA treats Windows/WSL as limited unified-memory support — no fine-grained GPU page-fault migration, no GPU-memory oversubscription beyond physical VRAM. This product is **explicit inference memory placement**, not "Docker VRAM overflow."

## Status

Built and working today: `gpu-container-profile`, `gpu-container-plan`, `gpu-container-receipt` (with the recalibration loop), `gpu-container-concentration` (routing de-risk), and `gpu-container-watchdog` (supervise a GPU job safely). llama.cpp is the integrated backend; the placement math is backend-agnostic. Start with the [quickstart](docs/quickstart.md).

## Documentation

- [`docs/quickstart.md`](docs/quickstart.md) — end-to-end walkthrough: profile → plan → launch under the watchdog → receipt → recalibrate
- [`docs/cli.md`](docs/cli.md) — the five commands: synopsis, flags, exit codes, worked examples
- [`docs/architecture.md`](docs/architecture.md) — memory-tier model, data flow, MoE expert routing, the recalibration loop
- [`docs/features.md`](docs/features.md) — the seven core features in depth
- [`docs/moe-lane-architecture.md`](docs/moe-lane-architecture.md) — the flagship MoE lane in depth
- [`docs/derisk-concentration.md`](docs/derisk-concentration.md) — the per-expert-cache de-risk gate (routing concentration)
- [`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`](docs/decisions/0001-per-expert-cache-build-vs-upstream.md) — ADR-0001: consume the cache mechanism, contribute the policy
- [`docs/constraints.md`](docs/constraints.md) — non-goals + the Windows/WSL CUDA Unified-Memory correction
- [`docs/prior-art.md`](docs/prior-art.md) — runtimes we orchestrate, and the gap this product fills
- [`docs/feasibility.md`](docs/feasibility.md) — feasibility assessment, research grounding, and what's confirmed live
