# Kickoff — gpu-container Phase 2: receipt-driven recalibration → must-offload case → per-expert calibration

## Mission
Continue building **gpu-container** — a model-aware inference memory-placement *planner* for single-GPU rigs. It profiles the rig + model, emits an explicit VRAM / pinned-RAM / NVMe **placement plan** across runtimes, proves it with a **measured receipt**, and **refuses** below ~1 tok/s. NOT "Docker VRAM overflow" — CUDA UVM oversubscription is unavailable on Windows/WSL2; explicit declared placement is the moat. The flagship lane is **MoE expert tiering** (hot VRAM / warm RAM / cold NVMe-gated). Director: Mike — a 1-human + LLM-crew studio; warm, fast, high standards. He is NOT a traditional solo dev; don't propose RPG-Maker-scale shortcuts or "scaffolding that replaces the work."

## Rig & paths (load-bearing)
- **RTX 5090** (Blackwell sm_120, 32 GB VRAM), 64 GB RAM (the WSL2 VM sees ~31 GB), Windows 11 + WSL2, driver **610.47**. Drives **C and E only — no D:/F:/G:**. Every `F:/AI/...` in memory/skills means `E:/AI/...`; the `F--AI` folder under `C:/Users/mikey/.claude/projects/` is a project hash — leave it.
- Docker = **Linux containers** (`desktop-linux`), WSL2 backend, `nvidia` runtime. **Never switch to Windows containers.**
- **CUDA 12.8 for sm_120 — NOT 13.x** (13.x crashes sm_120 MMQ/MXFP4 kernels, llama.cpp issue #19662).
- Python 3.14; `pytest` installed; `gpu-container` is `pip install -e ".[dev]"`. `numpy` is installed on host (CPU-bw probe).
- **Ollama** verifiers (for study-swarm): `mistral-small:24b`, `granite4.1:30b`. May be down → `ollama serve`.
- **⚠ Bash-tool docker mounts of Windows paths need `MSYS_NO_PATHCONV=1`** (Git Bash mangles `/work` → `C:/Program Files/Git/work`). Verified fix.

## State (all committed + pushed)
- **gpu-container** (public, MIT) — github.com/mcp-tool-shop-org/gpu-container · `E:\AI\gpu-container` · `main` · HEAD **`339aaed`**. Layout: `gpu_container/profiler/` (schema, hardware, model, cuda_bench, nvme_bench, baseline, cli) + `gpu_container/planner/` (placement, receipt, cli). **19 tests green.** Dockerfile = `nvidia/cuda:12.8.1-runtime-ubuntu24.04` + fio + pkg. CLIs: `gpu-container-profile`, `gpu-container-plan` (verdict-coded exit 0 ship / 3 refuse).
- **readouts KB** — `E:\AI\readouts` (github.com/mcp-tool-shop-org/readouts) · `main` · HEAD **`e3099c0`**. `docker-knowledge/` (findings.db: waves 1/2/3; lanes incl. `moe-placement` = category 3, currently sparse) + **`tensor-engine-knowledge/`** (engines — **consult, do NOT re-research**; catalog/{runtime-foundations,llm-inference,llm-serving,quantization}.md) + `model-knowledge/`.
- **Memory:** `C:/Users/mikey/.claude/projects/F--AI/memory/gpu-container.md` — the "Milestone 2-3" section has the full planner state + the live numbers.

## Assets already on the rig (don't rebuild)
- **Prebuilt llama.cpp:** `ghcr.io/ggml-org/llama.cpp:full-cuda` — runs sm_120 fine, **no build needed**. Dispatcher: `--run`/`--run-legacy`/`--bench`/`--server`. `llama-bench` supports `-ngl`, `-ncmoe`/`--n-cpu-moe` (comma-sweepable, e.g. `0,24,48`), `-o json`. **`-hf` HANGS in background** (stdin/TTY wait) — use a direct `curl` to a volume + `-m /models/<file>` instead.
- **Named volumes:** `gpc-models` (has `Qwen3-30B-A3B-Q4_K_M.gguf`, 17.4 GB) · `gpc-bench` (ext4, for fio).
- **Image:** `gpu-container:latest` (the profiler, current code). llama.cpp source at `E:\AI\llama.cpp-src` (`35c9b1f`, unbuilt — not needed).
- **Measured baselines (driver 610.47):** PCIe H2D 48 / D2H 37 GB/s; NVMe seq 7.1 GB/s / QD1 ~10k IOPS / 97 µs; pinnable ≥22.5 GiB; **CPU RAM bw 40.7 GB/s** (in-container numpy copy); **Qwen3-30B-A3B Q4** decode **302 / 42 / 20 tok/s** at N=0/24/48 (realized 41% in-VRAM, 56-61% offload of the roofline ceiling).
- **Engine fact (settled):** `--n-cpu-moe N` puts the **first N MoE layers' experts in CPU RAM, computed on CPU** (KTransformers-style; not PCIe streaming). Raise N to fit, lower for speed. It is **coarse, per-layer** — no per-expert control.

## Milestone — close the recalibration loop, validate the headline, then go per-expert
**(1) Receipt-driven recalibration — design milestone 5, the load-bearing one.** Today the planner emits a roofline CEILING and the receipt records realized efficiency (41% in-VRAM, 56-61% offload). Build the feedback: persist receipts (a small store — JSON dir or a table), fit a **calibrated** efficiency model (efficiency as a function of regime / N / active-bytes), and have the planner emit a **calibrated predicted tok/s with a band** (aim ±20-30%) instead of the raw ceiling — falling back to the ceiling when no calibration data exists for that shape. Keep the ceiling as the honest upper bound and the >1 tok/s refusal floor. **Prove it:** a second plan for a seen config predicts within the band (the empirical loop closing the static-prediction gap).

**(2) The must-offload case — validate where it matters.** Qwen3-30B-A3B fit at N=0, so it proved the model but not the headline. Run the full loop (profile → plan → llama-bench sweep → receipt) on a MoE that **cannot fit VRAM** and genuinely requires offload — e.g. **GLM-4.5-Air (~110B-A12B)**, a big **Qwen3-235B-A22B** quant, or **gpt-oss-120b** (MXFP4 ~63 GB). The planner must pick **N>0**, predict + refuse correctly, and the receipt must confirm it runs (or honestly refuses). Mind the ~31 GB WSL2-VM RAM ceiling for CPU-resident experts (raise `.wslconfig memory=` if needed, or pick a quant whose offloaded experts fit). This both proves "runs what otherwise can't" AND gathers receipt points across N to feed (1).

**(3) Per-expert adaptive calibration — the flagship's deep half. STUDY-SWARM FIRST.** Hot/warm/cold *per-expert* tiering, **Least-Stale** eviction (not LRU — SpecMD), router-lookahead prefetch, workload-representative traces (skew is request-level — MoE-Infinity). This is a **new product layer** needing (a) per-expert **activation traces** (which experts fire) and (b) **finer-than-layer placement** — `--n-cpu-moe` is too coarse. Because it's a new layer with qualitative design questions, **fire the study-swarm** (`research-grounded-advisor-protocol`): parallel web-grounded research → retrieval oracle (WebFetch) + `mistral-small:24b` + `granite4.1:30b`, reasoning-stripped; verifier-down = HALT+restore. Research the **calibration + placement TECHNIQUE** (llama.cpp `-ot`/`--override-tensor` regex for per-expert-tensor placement? activation-trace extraction — llama.cpp logging / KTransformers / MoE-Infinity-style? eviction policy) — **NOT the engines themselves** (`tensor-engine-knowledge` owns those). Land findings as a docker-knowledge **wave-4** (`moe-placement` lane) + reconcile into `docs/moe-lane-architecture.md`.

Suggested order: (2) first (fast, high-value, seeds data) → (1) (uses the data, completes the loop) → (3) (study-swarm-gated deep dive). Adjust as you see fit.

## Rules
- **Before any Write/Edit:** read `C:/Users/mikey/.claude/projects/F--AI/memory/MEMORY.md` (hook-enforced) + `memory/gpu-container.md`.
- **README = marketing front door only** (lint hook flags internal process/status — keep it out).
- **Commit only when Mike asks**; end commit msgs with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. gpu-container → `main` + push; readouts waves → `main`. Stage explicit files (never `git add -A` — leave `KICKOFF-*.md` untracked).
- **Any research / wave-4:** study-swarm (see milestone 3). Don't re-research engines.
- **Verify in-container before claiming a number.** Keep `None`-not-guess. The roofline is a CEILING (real is a fraction) — never present it as a point prediction.

## First moves
1. Read MEMORY.md + `memory/gpu-container.md` (the "Milestone 2-3" section).
2. `cd E:\AI\gpu-container && python -m pytest tests -q` → expect 19 green.
3. Confirm assets: `docker images gpu-container; docker volume ls | rg gpc; docker run --rm -v gpc-models:/m alpine ls -la /m` (Qwen3 GGUF present).
4. Re-prove the loop fast: in-container profile (`MSYS_NO_PATHCONV=1 docker run --rm --gpus all -v gpc-bench:/bench -v "E:/AI/gpu-container:/work" gpu-container:latest --model-config /work/<cfg>.json --quant gguf-q4_k_m --bench-dir /bench -o /work/profile.json`) → `gpu-container-plan` → `llama-bench`. Then start milestone (2) or (1).

*Loose ends (ignore): `KICKOFF-phase1-benches.md` + `KICKOFF-phase2-calibration.md` untracked (Mike's); `readouts/.../wave-02-measurement/_build_raw.py` + `KICKOFF-readouts-product.md` untracked.*
