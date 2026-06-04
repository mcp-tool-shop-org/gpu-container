# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

The full feature set below is built and tested; it becomes `[1.0.0]` at the first release.

### Added
- **Hardware + model profiler** (`gpu-container-profile`) — measured PCIe H2D/D2H, NVMe sequential + random-QD1, pinnable-RAM ceiling, CPU RAM bandwidth (all measured in-container, `None`-not-guess); closed-form model param-split (expert vs always-resident) and KV growth.
- **Placement planner** (`gpu-container-plan`) — minimal llama.cpp `--n-cpu-moe N` to fit VRAM, a roofline ceiling **and** a calibrated forecast band, and an honest ship/refuse verdict at the >1 tok/s floor.
- **Receipt + recalibration loop** (`gpu-container-receipt`) — pairs a `llama-bench` run with the plan's forecast, records realized efficiency / within-band, and writes a calibration point back so the next plan is calibrated. The verifier is a real GPU run, a different mechanism than the planner's math.
- **Routing de-risk gate** (`gpu-container-concentration`) — scores expert-routing concentration (`hot_frac_for_coverage`, `concentration_score`) from an activation trace or a `llama-imatrix` capture, to decide whether per-expert caching is worth building. Backed by [ADR-0001](docs/decisions/0001-per-expert-cache-build-vs-upstream.md).
- **Rig-safety watchdog** (`gpu-container-watchdog`) — polls GPU power/temp/VRAM (worst-case across all GPUs) + host memory against thresholds; emits ok/warn/abort (exit 0/5/7). A **supervisor mode** (`run -- <cmd>`) launches a GPU job as a child, polls in parallel, and aborts on a breach via `kill-job` (soft) or `wsl-shutdown` (catastrophic). Peak metrics export to the receipt (`--peaks-out` → `--peaks`) prove a run stayed inside the safe envelope. Shipped `watchdog.example.json`; `mem_source` tags host vs WSL2 VM; `--log` JSONL trajectory.
- **Docs** — `docs/cli.md` (CLI reference), `docs/quickstart.md` (end-to-end walkthrough), `docs/derisk-concentration.md` (the de-risk methodology), `docs/architecture.md`, `docs/features.md`, `docs/moe-lane-architecture.md`, `docs/feasibility.md`, ADR-0001.

### Fixed
- Planner emits `-fa on` (current llama.cpp rejects a value-less `-fa`).
- Receipt: the safety-envelope verdict no longer clobbers the throughput `within_band` verdict (independent fields).

### Notes
- Runtime support: **llama.cpp** is the integrated backend; the placement math is backend-agnostic and vLLM/Accelerate/ExLlamaV2/TensorRT-LLM are designed targets.
- Per-expert tiering is gated behind the de-risk gate + the upstream llama.cpp `#20757` mechanism (ADR-0001); the per-layer hot tier ships today.
