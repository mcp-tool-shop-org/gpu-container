---
title: Reference
description: Exit codes, the safety envelope, the watchdog config, and FAQs.
sidebar:
  order: 6
---

## Exit codes

| Command | `0` | Non-zero |
|---|---|---|
| `gpu-container-profile` | profiled | `2` emit-baseline failed |
| `gpu-container-plan` | ship | `3` refuse |
| `gpu-container-receipt` | cleared floor, ≤ ceiling | `3` below floor · `4` exceeded ceiling (bandwidth model wrong) · `2` bad input |
| `gpu-container-concentration` | cache not justified | `5` cache could help · `2` bad input |
| `gpu-container-watchdog` (monitor) | ok | `5` warn · `7` abort |
| `gpu-container-watchdog run` | job clean, no breach | `7` breach aborted the job · `2` no command · *else* job's own code |

Structured errors render as `ERROR [CODE]: message` + a `hint` (and `cause` when known); `--debug` shows the full traceback.

## The safety envelope (receipt `--peaks`)

`gpu-container-watchdog run --peaks-out peaks.json` writes:

| Field | Meaning |
|---|---|
| `samples` | watchdog polls during the run |
| `peak_gpu_power_pct` / `peak_gpu_temp_c` / `peak_gpu_vram_used_mib` | worst GPU readings |
| `peak_host_mem_pct` / `min_host_avail_mib` | worst host-memory readings (the incident metric) |
| `breached` / `stayed_within_envelope` | did any hard threshold trip during the run? |
| `thresholds` | the limits in force |

`gpu-container-receipt --peaks peaks.json` folds these into the receipt, so it can state: *"decode 302 tok/s; peak host-mem 31%, peak power 41% — stayed within the safety envelope."*

## watchdog.json

Ships as `watchdog.example.json`. Any unrecognized key (like `_comment`) is ignored.

```json
{
  "power_pct_max": 95.0,
  "gpu_temp_c_max": 87.0,
  "vram_pct_max": 98.0,
  "host_mem_pct_max": 90.0,
  "host_avail_mib_min": 2000.0,
  "warn_fraction": 0.9
}
```

## FAQ

**Why not just use CUDA Unified Memory / let it overflow to RAM?**
On Windows/WSL2 it's unavailable (NVIDIA-confirmed: `cudaDevAttrConcurrentManagedAccess == 0`). Even on Linux, on-demand migration collapses bandwidth up to 100× — the wrong tool for bandwidth-bound decode. Explicit declared placement is the moat.

**Why does it refuse some models?**
A plan that can't clear ~1 tok/s isn't a plan. Dense weights streamed from NVMe are sub-1 tok/s by physics; NVMe is the cold-MoE-*expert* lane, not a dense-weight-streaming lane.

**Why is the predicted throughput a band, not a number?**
The closed-form estimate is a roofline *ceiling* (upper bound). Real decode is a fraction of it, regime-dependent. The plan reports a calibrated band learned from receipts; the ceiling stays the bound and the refusal floor.

**Which runtimes are supported?**
llama.cpp (`--n-cpu-moe`) is the integrated backend today. The placement math is backend-agnostic; vLLM / HF Accelerate / ExLlamaV2 / TensorRT-LLM are designed targets.

**Is anything sent over the network?**
No. The package makes no outbound network calls and collects no telemetry. The only subprocesses are local rig tools (`nvidia-smi`, `fio`, `llama-bench`/`llama-imatrix`, and — only when you opt in — `wsl`/`docker`).
