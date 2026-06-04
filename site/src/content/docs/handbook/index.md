---
title: gpu-container
description: Model-aware inference memory-placement planner for single-GPU rigs.
sidebar:
  order: 0
---

A GPU-enabled container exposes the device. A model-aware runtime decides what lives in **VRAM**, **pinned RAM**, and **NVMe**. `gpu-container` is that runtime's planner: it profiles your rig and model, emits an **explicit placement plan**, proves it with a **measured receipt**, and **refuses** when the plan would thrash.

> **Not "Docker VRAM overflow."** CUDA Unified-Memory oversubscription is unavailable on Windows/WSL2 (NVIDIA-confirmed) and catastrophically slow even on Linux for autoregressive decode. The product is **explicit, declared placement** — that's the moat.

## The pipeline

```
profile ─▶ plan ─▶ (launch under) watchdog ─▶ receipt
                         │                        ▲
   concentration ───────┘ (de-risk the per-expert lane, before you build for it)
```

Five small commands, each doing one thing and returning a verdict-coded exit status:

| Command | Does |
|---|---|
| `gpu-container-profile` | Measure the rig (VRAM, PCIe, NVMe, pinnable RAM, CPU bandwidth) + the model |
| `gpu-container-plan` | Compute explicit placement + a calibrated throughput forecast; ship or refuse |
| `gpu-container-receipt` | Verify a plan against a real `llama-bench` run; write a calibration point back |
| `gpu-container-concentration` | De-risk the per-expert cache — measure routing concentration first |
| `gpu-container-watchdog` | Supervise a GPU job; abort on a host-memory/power/VRAM breach |

## What makes a plan trustworthy

- **Explicit placement** — every byte has a declared home; no runtime demand-paging magic.
- **MoE expert tiering** (flagship) — shared/attention layers in VRAM, experts in CPU RAM via llama.cpp `--n-cpu-moe`.
- **Measured receipts** — a real run verifies the forecast against a roofline *ceiling* and a calibrated *band*; the receipt feeds the next plan (the recalibration loop).
- **Honest refusal** — no plan clears the >1 tok/s floor? It refuses, and explains why.
- **Routing de-risk** — before building per-expert caching, measure whether the routing is even skewed enough to cache.
- **Rig-safety watchdog** — supervise every GPU job so a bad plan can't take the machine down.

## Where to go

- **[Getting Started](./getting-started/)** — install + the end-to-end walkthrough.
- **[CLI Reference](./cli/)** — every command, flag, and exit code.
- **[The MoE Lane](./moe-lane/)** — the flagship expert-tiering architecture.
- **[Routing De-risk](./derisk/)** — the concentration gate and the Qwen3 result.
- **[Rig Safety](./safety/)** — the watchdog and the incident that created it.
- **[Reference](./reference/)** — exit codes, the safety envelope, and FAQs.

> **Status:** beta. The profiler, planner, recalibration loop, routing de-risk gate, and watchdog are built and proven on an RTX 5090 / WSL2 rig. llama.cpp is the integrated backend; the placement math is backend-agnostic.
