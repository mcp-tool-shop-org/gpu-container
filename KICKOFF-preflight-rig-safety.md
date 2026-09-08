# PREFLIGHT — Rig-Safety Diagnostic (prepend to the next gpu-container kickoff; run BEFORE anything heavy)

**Why this exists.** On 2026-06-04 a `gpt-oss-120b` (63 GB) live benchmark filled the WSL2 VM to its
cap and drove the 64 GB host to **92–98% memory**, throttling the machine for over a minute. The model
was simply too large to offload safely on this rig, and the `.wslconfig` cap had been raised too high.
No hardware was harmed and nothing was lost, but it must not repeat. This preflight sizes every
workload to the rig's **actual safe headroom** before any model is chosen or any GPU job is launched.

## Hard constraints (non-negotiable on this rig — 64 GB RAM, RTX 5090 32 GB, Win11 + WSL2)
1. **`.wslconfig` `memory` cap = 28 GB. Never raise it.** A full 28 GB VM + ~16 GB Windows ≈ 56% of
   64 GB — safe. Raising it to 48 GB is what caused the incident. The "raise `.wslconfig` OR pick a
   smaller model" choice is **always resolved by picking the smaller model.**
2. **Models live on `E:\AI-Models`** (the designated drive), via a **bind mount**
   (`-v "E:/AI-Models/<model>:/models"`) — **never a Docker named volume.** Docker volumes sit in
   `docker_data.vhdx` on **C:** and silently consumed 63 GB of the system drive.
3. **Emergency abort = `wsl --shutdown`** (instant; dumps the whole VM, returns all RAM in ~5 s).
   **NOT `docker stop`** (10 s grace period + leaves page cache pinned). `VmmemWSL` cannot be killed
   from Task Manager — `wsl --shutdown` is the only kill switch.
4. **Honor a memory/throttle warning from the user INSTANTLY** — `wsl --shutdown` immediately, do not
   finish the in-flight step.

## Preflight steps — do these first, report the numbers, THEN choose a model
1. **Confirm the safe envelope (don't assume):**
   - `Get-PSDrive` (disk), `docker run --rm alpine free -m` (VM RAM cap — must read ~28 GB), host
     memory headroom (Task Manager / `Get-Counter '\Memory\Available MBytes'`).
   - Usable CPU-resident-expert budget ≈ 28 GB VM − ~3 GB (VM OS/process) − ~5 GB (transient mmap)
     = **target ≤ 15 GB of offloaded experts.**
2. **Size the model to the rig — a live must-offload proof needs total quant ≈ (VRAM-resident ~26 GB)
   + (CPU experts ≤ 15 GB) = ≤ ~40 GB total:**
   - ✅ Safe to run live: MoEs ≤ ~40 GB whose offloaded experts are ≤ ~15 GB (e.g. a ~38 GB
     Mixtral-8x7B-class quant; a mid Qwen3-MoE quant).
   - ❌ **Too big — do NOT run live here:** `gpt-oss-120b` (63 GB / ~38 GB experts), GLM-4.5-Air,
     Qwen3-235B. These are validated by the planner **on paper only.**
3. **Plan on paper before downloading:** profile → `gpu-container-plan` and read
   `ram_used_mib` (predicted CPU-expert RAM). **If it exceeds ~15 GiB, the model is too big for a live
   run here — stop and pick smaller, or accept on-paper validation.**
4. **Download to `E:\AI-Models` (bind mount), not a Docker volume.** Watch disk during the pull.
5. **During any bench, monitor `free -m` / `VmmemWSL`. Abort with `wsl --shutdown` if VM `available`
   < ~3 GB or host memory exceeds ~80%.** Prefer single-N runs over multi-N sweeps for abort control.

## Already proven — do not redo unsafely
- **Milestone 1 — throughput recalibration loop:** DONE (34 tests; calibrated tok/s band; full
  `plan → receipt → write-back` CLI loop). Code uncommitted on disk.
- **Offload mechanism:** proven LIVE on Qwen3-30B-A3B at N=24 / N=48 (real receipts, experts on CPU).
- **Must-offload headline:** validated ON PAPER (planner picks N=21 for gpt-oss-120b, predicts
  ~19 tok/s). The only open item is a **safe** live can't-fit receipt on a ≤ 40 GB model.

## Standing process fix
The kickoff author must not suggest a model without checking it against step 2 above. "Use
gpt-oss-120b / a 235B quant" is a planning-only suggestion on this rig, never a live-bench target.
