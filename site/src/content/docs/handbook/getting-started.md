---
title: Getting Started
description: Install gpu-container and run the full profile → plan → launch → receipt loop.
sidebar:
  order: 1
---

The whole product in one arc: **profile → plan → launch (under the watchdog) → receipt → recalibrate.** This walkthrough uses the model the loop is proven on — **Qwen3-30B-A3B-Q4_K_M** — on an RTX 5090 (32 GB) / WSL2 rig.

## Install

```bash
pip install "gpu-container[host]"   # host extra = psutil + numpy (system RAM, CPU-bandwidth probe, watchdog)
# optional: pip install "gpu-container[gpu]"   # pynvml v2 (separates driver-reserved VRAM from used)
# or, zero Python:
npx gpu-container --help
```

## The one safety rule

`gpu-container` was hardened by a real incident — a too-large model drove host memory to 92–98% and throttled the machine. On a single-GPU WSL2 rig:

- **Run every GPU job under the watchdog** — `gpu-container-watchdog run -- <command>`.
- **Keep `.wslconfig` `memory` ≤ ~28 GB** on a 64 GB rig. Don't raise the cap to fit a bigger model — pick the smaller model.
- **Models live on a real drive via a bind mount** (`-v "E:/AI-Models/m:/models"`), never a Docker named volume.
- **Emergency abort = `wsl --shutdown`** (instant), not `docker stop`. The watchdog's `--on-breach wsl-shutdown` does exactly this; `kill-job` stops just the job.

## Step 1 — Profile (inside the container)

Run the profiler **in the target container** so VRAM, PCIe, NVMe, and CPU bandwidth are *measured*, not guessed.

```bash
docker run --rm --gpus all -v "E:/AI-Models:/models" -v "gpc-bench:/bench" \
  gpu-container:latest gpu-container-profile --bench-dir /bench -o /models/profile.json
```

A measurement that couldn't be taken is `None` (never a spec-sheet number), so the planner can refuse honestly.

## Step 2 — Plan

```bash
gpu-container-plan --profile profile.json --model-config qwen3.json \
    --quant gguf-q4_k_m --ctx 4096 --hf unsloth/Qwen3-30B-A3B-GGUF:Q4_K_M -o plan.json
```

For Qwen3-30B-A3B this ships at **N=0** (fits ~19 GB into ~29.6 GB free VRAM). Exit `0` = ship, `3` = refuse. The plan carries the exact `llama_flags` to launch with, a **roofline ceiling**, and a **calibrated band**.

> The ceiling is a *ceiling* — real decode is a fraction of it. The calibrated band is the honest expectation; the ceiling is the upper bound and the refusal floor.

## Step 3 — Launch llama.cpp, under the watchdog

```bash
gpu-container-watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/Qwen3-30B-A3B-Q4_K_M.gguf --n-cpu-moe 0 -fa on -p 512 -n 128 -o json > bench.json
```

On a clean run it exits `0`; on a hard breach it runs `kill-job` (terminates the bench, not the VM) and exits `7`. Run the watchdog **on the Windows host** — `psutil` reads whatever it runs on, and the metric that matters is *host* memory.

## Step 4 — Receipt → recalibrate

```bash
gpu-container-receipt --plan plan.json --bench bench.json --peaks peaks.json \
    --model-name Qwen3-30B-A3B --quant gguf-q4_k_m --calibration-dir ./calib -o receipt.json
```

A real Qwen3-30B-A3B receipt at N=0: **decode 302 tok/s, ~41% of the roofline ceiling, landed inside the calibrated band** — and, with `--peaks`, *"peak host-mem 31%, peak power 41% — stayed within the safety envelope."* Each receipt sharpens the next plan's forecast for that model shape.

## Run the largest useful model SAFELY

1. **Plan on paper first** — read `ram_used_mib`; if it exceeds ~15 GiB, the model is too big for a live run on a 28 GB-VM / 64 GB rig.
2. **Size to ≤ ~40 GB total quant** (VRAM-resident ~26 GB + CPU experts ≤ ~15 GB). `N=0` (all-VRAM) is the proven-safe case.
3. **Run it under the watchdog.** Prefer single-N runs over multi-N sweeps for abort control.

**Refusal is a feature.** Dense weights streamed from NVMe are sub-1 tok/s by physics — NVMe is the cold-MoE-expert lane, not a dense-weight-streaming lane.
