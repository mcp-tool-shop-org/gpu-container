Kickoff — gpu-container Phase 3: commit the recalibration loop → (optional) a SAFE must-offload receipt → per-expert calibration (study-swarm)

## ⚠ PREFLIGHT FIRST — non-negotiable
**Read `KICKOFF-preflight-rig-safety.md` (in this repo) BEFORE any GPU/model work, and follow it.** Phase 2 (2026-06-04) crashed the host to 92–98% memory by running a 63 GB model (gpt-oss-120b) on a 64 GB rig with the WSL cap mistakenly raised to 48 GB. No hardware harm, nothing lost — but it must not repeat. The short version:
- **`.wslconfig memory` cap = 28 GB. NEVER raise it.** (Already set to 28 GB + `autoMemoryReclaim=gradual`.)
- **Models live on `E:\AI-Models` via a BIND MOUNT** (`-v "E:/AI-Models/<model>:/models"`), never a Docker named volume (those sit in `docker_data.vhdx` on C: and silently ate 63 GB of the system drive).
- **A live must-offload proof must use a model ≤ ~40 GB total whose offloaded experts are ≤ ~15 GiB.** gpt-oss-120b / GLM-4.5-Air / Qwen3-235B are **paper-only** on this rig.
- **Abort = `wsl --shutdown`** (instant), NOT `docker stop` (slow + leaves cache pinned). **Stop the instant the user flags memory.**
- **Plan on paper first:** read `gpu-container-plan`'s predicted `ram_used_mib`; if > ~15 GiB, the model is too big to run live here — pick smaller or accept on-paper validation.

## Mission
Continue building **gpu-container** — a model-aware inference memory-placement planner for single-GPU rigs. It profiles the rig + model, emits an explicit VRAM / pinned-RAM / NVMe placement plan across runtimes, proves it with a measured receipt, and refuses below ~1 tok/s. NOT "Docker VRAM overflow" — CUDA UVM oversubscription is unavailable on Windows/WSL2; explicit declared placement is the moat. Flagship lane = MoE expert tiering (hot VRAM / warm RAM / cold NVMe-gated). Director: **Mike — a 1-human + LLM-crew studio; warm, fast, high standards. NOT a traditional solo dev**; don't propose RPG-Maker-scale shortcuts.

## Rig & paths (load-bearing)
RTX 5090 (Blackwell sm_120, 32 GB VRAM), **64 GB RAM**, Windows 11 + WSL2, driver 610.47. Drives C and E (no D/F/G); every `F:/AI/...` in memory means `E:/AI/...`; the `F--AI` folder under `C:/Users/mikey/.claude/projects/` is a project hash — leave it.
- **WSL2 VM is capped at 28 GB** (`.wslconfig`); container sees ~28 GB. Do not raise.
- Docker = Linux containers (`desktop-linux`), WSL2 backend, nvidia runtime. Never Windows containers.
- **CUDA 12.8 for sm_120 — NOT 13.x** (13.x crashes sm_120 MXFP4/MMQ kernels). The prebuilt `ghcr.io/ggml-org/llama.cpp:full-cuda` image is **CUDA 12.8.90** ✓ (verified Phase 2).
- Python 3.14; `gpu-container` is `pip install -e ".[dev]"`. numpy on host.
- Ollama verifiers (study-swarm): `mistral-small:24b`, `granite4.1:30b`. May be down → `ollama serve`.
- ⚠ Bash-tool docker mounts of Windows paths need `MSYS_NO_PATHCONV=1` (else `/models` → `M:/`). Verified.
- ⚠ Git-Bash `/tmp` ≠ Windows temp — write scratch to the repo (gitignored `profile*.json`/`plan*.json`/`bench*.json`/`receipt*.json`/`*.config.json`) or use the Read tool, not `/tmp`.

## State — where Phase 2 left it (2026-06-04)
- **gpu-container** — github.com/mcp-tool-shop-org/gpu-container · `E:\AI\gpu-container` · **REPO IS PRIVATE** (Mike made it private 2026-06-04; confirm with him before any public/release work). `main` HEAD still `339aaed` — **Phase-2 work is UNCOMMITTED on disk** (commit only when Mike asks).
- **Milestone 1 (receipt-driven recalibration loop) — DONE + PROVEN, 34 tests green.** New: `gpu_container/planner/calibration.py` (CalibrationPoint/Store/Model — efficiency = f(regime, offload-fraction), ±25 % band), `calibration_seed.json` (the 3 Qwen3 receipts), `receipt_cli.py` (`gpu-container-receipt` — the write-back). Modified: `placement.py` (emits calibrated `predicted_decode_tok_s` + band + retains `ceiling_decode_tok_s`; opt-in `calibration=` param so the 19 old tests stay green; new `non_expert_bpw` — MXFP4 quantizes experts only, so non-expert weights are budgeted at f16), `receipt.py` (efficiency vs ceiling + within-band proof), `schema.py`, `cli.py` (`--calibration-dir`/`--no-calibration`), `pyproject.toml` (3rd entry point). `scripts/gen_calibration_seed.py` (+`--check` CI guard) and `scripts/ingest_sweep.py` (multi-N sweep → receipts + calibration). `tests/test_calibration.py` (12 tests incl. in-sample + leave-one-out band proofs). Docs: `architecture.md` (§ Throughput calibration), `moe-lane-architecture.md` (milestone 5 split). **The loop is proven live end-to-end:** `plan → receipt → write-back`, a re-plan of a measured shape lands inside the band.
- **readouts KB** — `E:\AI\readouts` · `main` `e3099c0`. `docker-knowledge` (waves 1/2/3; `moe-placement` lane sparse — Phase 3 fills it) + `tensor-engine-knowledge` (consult, do NOT re-research) + `model-knowledge`.
- **Memory:** `C:/Users/mikey/.claude/projects/F--AI/memory/gpu-container.md` — now has a **"⚠ RIG SAFETY CONSTRAINTS"** section near the top (read it).

## Assets on the rig
- Docker volume `gpc-models` holds **Qwen3-30B-A3B-Q4_K_M.gguf (17.4 GB)** — fits VRAM (N=0). (gpt-oss-120b was deleted; its 63 GB reclaimed off C: by vhdx compaction.) **NOTE: this volume is C:-backed — for any NEW model, bind-mount from `E:\AI-Models` instead.**
- `gpc-bench` (ext4 volume, for fio). Image `gpu-container:latest` (profiler). `ghcr.io/ggml-org/llama.cpp:full-cuda` (CUDA 12.8, runs sm_120 + MXFP4).
- **llama-bench arg gotchas (learned Phase 2):** `-fa` now REQUIRES a value (`-fa on`) or omit it (default auto); `--n-cpu-moe` is comma-sweepable (`24,27`); point `-m` at shard `00001-of-000NN` of a split GGUF (auto-loads the rest); `-hf` HANGS — use `-m` + a volume/bind mount.

## Measured baselines (driver 610.47, in-container)
PCIe H2D ~44–48 / D2H ~34–37 GB/s; NVMe seq 7.1 GB/s / rand-QD1 ~10k IOPS; CPU RAM bw ~38–41 GB/s (numpy copy). Qwen3-30B-A3B Q4 decode 302/42/20 tok/s at N=0/24/48 → realized **41 % in-VRAM, 56–61 % offload** of the roofline ceiling (these ARE the calibration seed).

## Milestone — Phase 3 (suggested order; adjust as you see fit)
1. **Commit Milestone 1** (the recalibration loop) — it's done, proven, 34 tests green, but uncommitted. Verify, then commit **when Mike asks** (gpu-container → `main` + push). End commit msgs with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Stage explicit files (never `git add -A`). Confirm repo-visibility intent with Mike first (it's private).
2. **(Optional — Mike's call) A SAFE live must-offload receipt.** The headline "runs what otherwise can't" is validated on paper (planner picks N=21 for gpt-oss) + the offload *mechanism* is proven live on Qwen3 N=24/48. A genuine can't-fit-at-all live receipt needs a **≤ 40 GB MoE whose offloaded experts ≤ 15 GiB** (e.g. a ~38 GB Mixtral-8x7B-class quant), downloaded to **`E:\AI-Models`** (bind mount), run through the full loop per the preflight. Plan-on-paper first; abort-monitor throughout. Skip if Mike prefers — M1 + paper validation already stand.
3. **Per-expert adaptive calibration — the flagship's deep half. STUDY-SWARM FIRST.** Hot/warm/cold per-expert tiering, Least-Stale eviction (not LRU — SpecMD), router-lookahead prefetch, workload-representative traces (skew is request-level — MoE-Infinity). New product layer with qualitative design questions → fire the study-swarm (research-grounded-advisor-protocol): parallel web-grounded research → retrieval oracle (WebFetch) + `mistral-small:24b` + `granite4.1:30b`, reasoning-stripped; verifier-down = HALT+restore. Research the **technique** (llama.cpp `-ot`/`--override-tensor` regex for per-expert-tensor placement? activation-trace extraction — llama.cpp logging / KTransformers / MoE-Infinity-style? eviction policy) — NOT the engines (tensor-engine-knowledge owns those). Land findings as a **docker-knowledge wave-4 (moe-placement lane)** + reconcile into `docs/moe-lane-architecture.md`. (`-ot` IS exposed in this llama-bench build — confirmed Phase 2.)

## Rules
- Before any Write/Edit: read `C:/Users/mikey/.claude/projects/F--AI/memory/MEMORY.md` (hook-enforced) + `memory/gpu-container.md` + **`KICKOFF-preflight-rig-safety.md`**.
- README = marketing front door only (lint hook flags internal process/status).
- **Commit only when Mike asks.** gpu-container → `main` + push; readouts waves → `main`. Stage explicit files; leave `KICKOFF-*.md` untracked.
- Any research / wave-4: study-swarm. Don't re-research engines.
- Verify in-container before claiming a number. Keep None-not-guess. Roofline is a CEILING (real is a fraction) — never present it as a point prediction.
- **Honor the preflight's memory-safety rules above everything. Stop instantly on a memory warning.**

## First moves
1. Read MEMORY.md + memory/gpu-container.md (the rig-safety section) + **KICKOFF-preflight-rig-safety.md**.
2. `cd E:\AI\gpu-container && python -m pytest tests -q` → expect **34 green**.
3. Confirm state: `git status` (Phase-2 work uncommitted), `git log --oneline -3` (HEAD `339aaed`), `gh repo view mcp-tool-shop-org/gpu-container --json visibility` (PRIVATE), `docker run --rm alpine free -m` (~28 GB cap), `docker volume ls | rg gpc`.
4. Ask Mike which track: commit M1 / the safe live receipt / the per-expert study-swarm.

## Loose ends (ignore / clean as needed)
Untracked scratch in the repo: `KICKOFF-phase1-benches.md`, `KICKOFF-phase2-calibration.md`, `KICKOFF-preflight-rig-safety.md`, this file, `gptoss.config.json`, `profile-gptoss.json`, `plan-gptoss.json` (gpt-oss artifacts — safe to delete; the model is gone). readouts: `KICKOFF-readouts-product.md`, wave-02 `_build_raw.py`.
