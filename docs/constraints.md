# Constraints — What We Don't Do

## The Windows/WSL CUDA Unified Memory Correction

**This is the load-bearing constraint that shapes the entire product.**

CUDA Unified Memory (managed memory via `cudaMallocManaged`) on Windows and WSL2:
- Does NOT support GPU memory oversubscription beyond physical VRAM
- Does NOT provide fine-grained GPU page-fault migration (demand paging)
- Does NOT allow transparent "spill to system RAM on OOM" at the CUDA level
- Treats the GPU memory as a hard ceiling, not an elastic pool

This means the following product pitches are **wrong**:
- ❌ "Docker VRAM overflow" — there is no overflow mechanism to exploit
- ❌ "Graphics API spillover" — WDDM doesn't provide this for compute workloads
- ❌ "Transparent memory expansion" — nothing transparently expands VRAM on Windows/WSL
- ❌ "Unified memory lets you run bigger models" — not on this platform

On Linux bare-metal with recent drivers, CUDA UVM *does* support oversubscription via page migration. But:
1. Our primary target is Windows/WSL2 users (consumer GPUs, gaming rigs repurposed for AI)
2. Even on Linux, UVM page-fault migration has severe throughput penalties for inference
3. Thrashing a page-fault path during autoregressive decode is catastrophically slow

## What We ARE

**Explicit inference memory placement.**

Every byte has a declared tier. The planner decides placement *before* loading. The receipt proves it worked *after* loading. There is no runtime magic — just honest math.

## Non-Goals

| Temptation | Why we refuse |
|-----------|---------------|
| Custom CUDA memory allocator | Too deep in runtime internals, maintenance nightmare |
| Kernel-level memory hooks | Platform-specific, fragile, security risk |
| Modify inference runtimes | We orchestrate them, we don't fork them |
| GPU virtualization / MIG | Enterprise-only, not consumer GPUs |
| Multi-GPU coordination | Future scope — single GPU first |
| Training / fine-tuning | Inference only |
| Windows native (no Docker) | Docker is the isolation boundary; no bare-metal mode |

## Honest Refusal

The planner MUST refuse when:
- No placement plan achieves > 1 tok/s decode
- Required offload exceeds available RAM + NVMe
- Model's minimum context (for coherent output) can't fit in available KV budget
- Quantization required would drop below the model's known quality floor

Refusal message includes:
- What's missing (e.g., "need 8 GB more RAM" or "need a GPU with 24 GB VRAM")
- What model *would* work on this hardware
- What hardware upgrade would unlock this model

## Platform Support Matrix

| Platform | GPU Passthrough | CUDA UVM Oversub | Our Approach |
|----------|----------------|-------------------|-------------|
| Linux bare-metal | Native | Yes (but slow) | Explicit placement (faster) |
| WSL2 | Via NVIDIA driver | No | Explicit placement (only option) |
| Docker on Linux | NVIDIA Container Toolkit | Inherited from host | Explicit placement |
| Docker on WSL2 | NVIDIA Container Toolkit | No | Explicit placement |
| macOS (Apple Silicon) | N/A (Metal) | N/A | Out of scope |
| Windows native (no WSL) | N/A (no CUDA in Docker) | N/A | Not supported |
