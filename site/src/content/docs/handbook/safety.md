---
title: Rig Safety
description: The watchdog control plane, and the incident that created it.
sidebar:
  order: 5
---

`gpu-container` exists to run big models on a *personal* rig — which means it must never take that rig down. The watchdog is the net.

## The incident

A too-large MoE benchmark drove host memory to **92–98%** and throttled the machine for over a minute. The lesson, institutionalized: **size + watch every GPU run, and abort the instant a hard threshold is crossed.** On a WSL2 rig the abort of record is `wsl --shutdown` (instant; frees all VM RAM in ~5s).

## Two modes

### Monitor — poll, get a verdict

```bash
gpu-container-watchdog --json                              # one-shot, machine-readable
gpu-container-watchdog --watch --on-breach wsl-shutdown    # autonomous abort (opt-in)
```

Reads GPU power/temp/VRAM (`nvidia-smi`, **worst-case across all GPUs**) + host memory (`psutil`). Emits `ok` / `warn` / `abort` → exit `0` / `5` / `7`. The default action is **`alert`** — it surfaces a breach, it never auto-kills.

### Supervisor — run a job *under* the watchdog

```bash
gpu-container-watchdog run --on-breach kill-job --peaks-out peaks.json -- <command...>
```

Launches the command as a child, polls metrics **in parallel**, and on a hard breach takes the action. `kill-job` terminates just the child (a soft abort); `wsl-shutdown` is the catastrophic case. This makes "run a GPU job safely" one self-monitoring command — **the recommended way to run any GPU job.**

`--peaks-out` records the run's peak envelope (peak power / host-mem / VRAM, `stayed_within_envelope`), which `gpu-container-receipt --peaks` folds into the receipt — proof a run stayed inside the limits.

## Honest by construction

- **A missing metric is `None`, never `0`** — the watchdog never invents a safe-looking reading.
- **`mem_source` tags the vantage** — `windows-host` vs `wsl2-vm`/`linux`. The incident metric is the *host*; run the watchdog **on the Windows host** for true coverage (in a container, `psutil` only sees the VM, which can sit calm while the host starves).
- **Conservative VRAM source** — the watchdog reads `nvidia-smi memory.used` (includes driver-reserved), so it over-counts rather than under-counts. The profiler uses pynvml v2 (separates `reserved`); they agree on `total`.
- **Stable exit codes** — `0/5/7` are a scriptable contract.

## Thresholds

Defaults (tuned for an RTX 5090 / 64 GB / WSL2 28 GB rig), overridable via flags or `--config watchdog.json`:

| Threshold | Default | Aborts when |
|---|---|---|
| `--power-max` | 95% | GPU power ≥ this % of the board limit |
| `--temp-max` | 87°C | GPU temperature ≥ this |
| `--vram-max` | 98% | VRAM ≥ this % |
| `--host-mem-max` | 90% | host memory ≥ this % (**the incident metric**) |
| `--host-avail-min` | 2000 MiB | free host/VM RAM below this |

## Sizing a safe run

A live offload run must fit **VRAM-resident (~26 GB) + CPU experts (≤ ~15 GB) = ≤ ~40 GB total**. `N=0` (all-VRAM) is the proven-safe case. Bigger models (gpt-oss-120b, GLM-4.5-Air, Qwen3-235B) are **paper-only** — the planner validates them, you don't run them live on a 64 GB rig.
