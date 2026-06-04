# Quickstart

The whole product in one arc: **profile → plan → launch (under the watchdog) → receipt → recalibrate.** You measure the rig, get an explicit placement plan with an honest forecast, run the job safely, and prove it with a receipt that feeds the next plan. This walkthrough uses the model the loop is proven on — **Qwen3-30B-A3B-Q4_K_M** — on an RTX 5090 (32 GB) / WSL2 rig.

## Install

```bash
pip install -e ".[dev,host]"      # host extra = psutil + numpy (system RAM + CPU-bandwidth probe + watchdog)
# optional: pip install -e ".[gpu]"   # pynvml v2, separates driver-reserved VRAM from used
```

Five commands land on your PATH: `gpu-container-profile`, `-plan`, `-receipt`, `-concentration`, `-watchdog`. Full flag/exit-code reference: [cli.md](cli.md).

## The one safety rule (read before any GPU job)

Born from a real incident (a too-large model drove host memory to 92–98% and throttled the machine). On a single-GPU WSL2 rig:

- **Run every GPU job under the watchdog** — `gpu-container-watchdog run -- <command>` (Step 3). It's the net.
- **Keep `.wslconfig` `memory` ≤ ~28 GB** on a 64 GB rig. Don't raise the cap to fit a bigger model — pick the smaller model.
- **Models live on a real drive via a bind mount** (`-v "E:/AI-Models/m:/models"`), **never a Docker named volume** (those quietly fill the system drive's `docker_data.vhdx`).
- **Emergency abort = `wsl --shutdown`** (instant — dumps the whole VM in ~5s), not `docker stop`. The watchdog's `--on-breach wsl-shutdown` does exactly this; `kill-job` stops just the job.

Sizing, before you download anything: a live run must fit **VRAM-resident (~26 GB) + CPU experts (≤ ~15 GB) = ≤ ~40 GB total**. The all-VRAM case (`N=0`) is the proven-safe one. Bigger models (gpt-oss-120b, GLM-4.5-Air, Qwen3-235B) are **paper-only** here — the planner validates them, you don't run them live. More: [the preflight](#run-the-largest-useful-model-safely).

## Step 1 — Profile (inside the container)

Run the profiler **in the target container** so VRAM, PCIe, NVMe, and CPU bandwidth are *measured*, not guessed. The prebuilt `ghcr.io/ggml-org/llama.cpp:full-cuda` image (CUDA 12.8, sm_120) works, or build the repo's profiler image.

```bash
docker run --rm --gpus all \
  -v "E:/AI-Models:/models" \
  -v "gpc-bench:/bench" \
  gpu-container:latest \
  gpu-container-profile --bench-dir /bench -o /models/profile.json
```

The result is `profile.json` — the contract the planner reads. A measurement that couldn't be taken is `None` (never a spec-sheet number), so the planner can refuse honestly.

## Step 2 — Plan

Feed the profile + the model's HF `config.json` to the planner. It computes the minimal `--n-cpu-moe N` that fits VRAM, a **roofline ceiling** and a **calibrated forecast band**, and a ship/refuse verdict against the >1 tok/s floor.

```bash
gpu-container-plan --profile profile.json --model-config qwen3.json \
    --quant gguf-q4_k_m --ctx 4096 \
    --hf unsloth/Qwen3-30B-A3B-GGUF:Q4_K_M -o plan.json
```

For Qwen3-30B-A3B this ships at **N=0** (fits ~19 GB into ~29.6 GB free VRAM) with a ceiling around 738 tok/s. Exit `0` = ship, `3` = refuse. The plan carries the exact `llama_flags` to launch with.

> **The ceiling is a CEILING.** Real decode is a fraction of it (in-VRAM is overhead-bound, offload is CPU-bandwidth-bound). The plan's *calibrated band* is the honest expectation; the ceiling is the upper bound and the refusal floor. See [architecture.md](architecture.md#throughput-calibration--the-recalibration-loop).

## Step 3 — Launch llama.cpp, *under the watchdog*

This is the load-bearing step. Don't run the bench bare — run it as a child of the watchdog, which polls GPU + host metrics in parallel and kills the job if it crosses a hard threshold. `--peaks-out` records the run's safety envelope for the receipt.

```bash
gpu-container-watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" \
    ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/Qwen3-30B-A3B-Q4_K_M.gguf \
      --n-cpu-moe 0 -fa on -p 512 -n 128 -o json > bench.json
```

- On a clean run it exits `0`; on a hard breach it runs `kill-job` (terminates the bench, not the VM) and exits `7`.
- Run the watchdog **on the Windows host** — `psutil` reads whatever it runs on, and the metric that matters is *host* memory. (In-container, `psutil` only sees the WSL2 VM, which can sit calm while the host starves. The sample's `mem_source` tells you which vantage you got.)
- `peaks.json` now holds peak power / host-mem / VRAM and `stayed_within_envelope`.

## Step 4 — Receipt → recalibrate

Pair the measured run with the plan's forecast. Fold in the safety envelope (`--peaks`). Write a calibration point back (`--calibration-dir` + `--model-name`) so the *next* plan for this shape is calibrated. The verifier is a real GPU run — a different mechanism than the planner's math.

```bash
gpu-container-receipt --plan plan.json --bench bench.json --peaks peaks.json \
    --model-name Qwen3-30B-A3B --quant gguf-q4_k_m --calibration-dir ./calib -o receipt.json
```

A real Qwen3-30B-A3B receipt at N=0: **decode 302 tok/s, ~41% of the roofline ceiling, landed inside the calibrated band (loop closed)** — and, with `--peaks`, *"peak host-mem 31%, peak power 41% — stayed within the safety envelope."* Exit `0` = cleared the floor at/below ceiling; `3` = below the floor; `4` = *exceeded* the ceiling (the bandwidth model is wrong — halt and fix assumptions, don't just recalibrate).

That's the loop. Each receipt sharpens the next plan's forecast for that model shape.

## Optional — de-risk the per-expert lane first

Before investing in per-expert caching for a model, ask whether its routing is even skewed enough to cache. One N=0 `imatrix` pass answers it:

```bash
# in the llama.cpp container:
llama-imatrix -m /models/Qwen3-30B-A3B-Q4_K_M.gguf -f corpus.txt -ngl 99 --no-ppl -o imatrix.gguf
gpu-container-concentration --imatrix imatrix.gguf --model-name Qwen3-30B-A3B
```

Exit `0` = routing too uniform, a per-expert cache wouldn't help (the common "hold"); `5` = it could help, weigh it. For Qwen3-30B-A3B the answer is **hold** — routing is near-uniform (load-balancing aux-losses train the skew away). Full method + the real numbers: [derisk-concentration.md](derisk-concentration.md).

## Run the largest useful model SAFELY

The planner's reason for being is to find the *largest model your rig can honestly run* — and to say **no** when there isn't one.

1. **Plan on paper first.** Profile, then `gpu-container-plan`, and read `ram_used_mib` (predicted CPU-expert RAM). If it exceeds ~15 GiB, the model is too big for a live run on a 28 GB-VM / 64 GB rig — stop, pick smaller, or accept on-paper validation.
2. **Size to ≤ ~40 GB total quant** (VRAM-resident ~26 GB + CPU experts ≤ ~15 GB) for a live offload run. `N=0` (all-VRAM) is the proven-safe case.
3. **Download to a bind-mounted real drive**, watch disk during the pull.
4. **Run it under the watchdog** (Step 3). Prefer single-N runs over multi-N sweeps for abort control.

**Refusal is a feature.** If no placement clears >1 tok/s, the planner refuses and explains why — dense weights streamed from NVMe are sub-1 tok/s by physics (NVMe is the *cold-MoE-expert* lane, not a dense-weight-streaming lane). A plan that would thrash is not a plan.

## Where to go next

- [cli.md](cli.md) — every flag and exit code.
- [architecture.md](architecture.md) — the memory-tier model and the recalibration loop.
- [moe-lane-architecture.md](moe-lane-architecture.md) — the flagship MoE lane in depth.
- [derisk-concentration.md](derisk-concentration.md) — the per-expert de-risk gate.
- [feasibility.md](feasibility.md) — the research grounding and what's been confirmed live.
