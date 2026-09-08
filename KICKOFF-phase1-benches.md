# Kickoff — gpu-container Phase 1: real profiler measurements + Dockerfile

**Paste this as the first message of a fresh session. It stands alone.**

## Mission
Continue building **gpu-container** — a model-aware inference memory-placement *planner* for single-GPU rigs. It profiles the rig + model, emits an explicit VRAM / pinned-RAM / NVMe **placement plan** across runtimes (llama.cpp / vLLM / …), proves it with a **measured receipt**, and **refuses** below ~1 tok/s. It is **NOT** "Docker VRAM overflow" — CUDA UVM oversubscription is unavailable on Windows/WSL2 (NVIDIA-confirmed); explicit declared placement is the moat. Director: Mike — a 1-human + LLM-crew studio; warm, fast, high standards.

## Rig & paths (load-bearing)
- **RTX 5090** (Blackwell **sm_120**, 32 GB VRAM ~30.6 free), 64 GB RAM, Windows 11 + **WSL2**. Drives **C and E only — no D:/F:/G:**. Every `F:/AI/...` written in memory/skills means `E:/AI/...`; the `F--AI` folder under `C:/Users/mikey/.claude/projects/` is a Claude-Code project hash — leave it.
- Docker Desktop = **Linux containers** (context `desktop-linux`), WSL2 backend, `nvidia` runtime registered. Passthrough verified: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` shows the 5090. **Never switch Docker to Windows containers** (kills the CUDA path).
- Python 3.14; `pytest` + `psutil` installed; `gpu-container` is already `pip install -e ".[dev]"`. Build CUDA with the **12.8** toolchain for sm_120 (13.x MMQ segfaults — per tensor-engine-knowledge).
- **Ollama** (local) may be down → restart with `ollama serve`. Verifier models present: `mistral-small:24b`, `granite4.1:30b`.

## State — all committed + pushed
- **gpu-container** (public, MIT) — `github.com/mcp-tool-shop-org/gpu-container`, local `E:\AI\gpu-container`, branch `main`, HEAD **`0eca183`**.
  - `gpu_container/profiler/`: `schema.py` (the Profile JSON contract — `Optional` fields default `None` meaning "unknown, never zero/guess"), `hardware.py` (REAL GPU/platform/RAM detect via nvidia-smi; **`measure_bandwidth()` is a STUB → None**), `model.py` (closed-form KV-cache + dense/MoE detection from a HF config), `cli.py` (`gpu-container-profile`). `tests/test_profiler.py` → `python -m pytest` (4 pass).
  - `docs/`: `feasibility.md` (verdict), `moe-lane-architecture.md` (Phase-1 design), architecture/features/constraints/prior-art, README (front-door — keep marketing-only).
- **docker-knowledge KB** (the research database) — `E:\AI\readouts\docker-knowledge`, in `github.com/mcp-tool-shop-org/readouts` (HEAD **`efc09d2`**). SQLite `findings.db`: **38 findings / 80 sources / 6 lanes / 2 waves**, all family-different-verified. Wave-2 lane `hw-measurement` (20 findings) is your spec.
  - Query: `python -c "import sqlite3;[print(r) for r in sqlite3.connect(r'E:\AI\readouts\docker-knowledge\findings.db').execute('SELECT name,metric,design_implication FROM v_load_bearing')]"` or read `catalog/hw-measurement.md`.

## Your milestone — make the stubs real, in-container
Read `E:\AI\readouts\docker-knowledge\waves\wave-02-measurement\dispatch.md` first — each finding's `design_implication` is the instruction. Then, in order:
1. **PCIe** (start here — easiest honest win): pinned cudaMemcpy timed by cudaEvent, or shell `nvbandwidth`; large transfers (≥64–256 MB) + warmup + median-of-N; report **per-direction** GB/s (~50–55 expected; **never emit 64** = theoretical). Fill `BandwidthInfo.pcie_h2d_gbps/pcie_d2h_gbps/method`.
2. **NVMe**: `fio` sequential (`--rw=read --bs=256k`) + **random QD1** (`--rw=randread --bs=4k --iodepth=1 --direct=1`) on the **actual mount** weights live on (avoid `/mnt` drvfs — >10× slower; `--direct=1` can fail on the overlay fs → bind-mount a volume).
3. **Pinnable-RAM ceiling**: `cudaHostAlloc` probe (expect ~300–500 MB cap in Docker-on-WSL2 vs GB native — caps the warm-tier KV/prefetch staging budget).
4. **Platform refinement**: container = `/.dockerenv` + docker token in `/proc/1/cgroup`; WSL2 = "microsoft" in `/proc/version` (gotcha: a container *on* WSL2 also carries "microsoft" — combine signals).
5. **Dockerfile** (`FROM nvidia/cuda:12.x-runtime-ubuntu24.04`) so the profiler runs INSIDE the container (the only honest vantage). `:runtime` runs; `:devel` adds `nvcc` only if you compile a bench (else ship `nvbandwidth`).
6. **Close the loop**: `gpu-container-profile --emit-baseline` writes the measured readouts into docker-knowledge's `measurements`/`baselines` (knowledge → measurement → knowledge).

Keep the rule: a measurement you HAVEN'T taken is `None`, never a guess. Update tests. Verify a number in-container before claiming it.

## Rules (read memory FIRST — non-negotiable)
- **Before any Write/Edit:** read `C:/Users/mikey/.claude/projects/F--AI/memory/MEMORY.md` (a hook enforces this) + `memory/gpu-container.md`.
- **README = marketing front door only** — never internal process/methodology/status dumps (a lint hook flags them); that detail goes in docs/CHANGELOG.
- **Commit only when Mike asks.** When you do, end commit messages with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. readouts waves commit to `main` directly; gpu-container → `main` + push.
- **Any research / a wave-3:** study-swarm doctrine — identify load-bearing questions → parallel web-grounded research agents → verify with a **retrieval oracle (WebFetch) + ≥2 different-family models** (`mistral-small:24b` + `granite4.1:30b` via the ollama-intern `ollama_chat` tool), reasoning-stripped. Verifier-unavailable = HALT + restore Ollama, never skip. Protocol: `C:/Users/mikey/.claude/projects/F--AI/memory/research-grounded-advisor-protocol.md`.
- **Do NOT re-research inference engines** — the sibling `tensor-engine-knowledge` KB owns them (llama.cpp/vLLM/KTransformers + the CUDA-12.8/sm_120 footgun).

## First moves
1. Read `MEMORY.md` + `memory/gpu-container.md`.
2. Read `E:\AI\readouts\docker-knowledge\waves\wave-02-measurement\dispatch.md` + `catalog/hw-measurement.md` (the spec).
3. `python -m pytest E:\AI\gpu-container\tests` → confirm 4 green baseline.
4. Implement the **PCIe bench + a Dockerfile**, then verify inside the container.

*Loose ends (safe to ignore or clean): `_build_raw.py` — an untracked one-off transform in `docker-knowledge/waves/wave-02-measurement/`; `KICKOFF-readouts-product.md` — untracked, Mike's.*
