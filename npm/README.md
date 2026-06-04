<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**A GPU-enabled container exposes the device. A model-aware runtime decides what lives in VRAM, pinned RAM, and NVMe.**

</div>

Run the largest useful local model your machine can honestly support — with explicit placement plans, benchmark receipts, and refusal when the plan would thrash. This npm package is a **zero-prerequisite launcher**: `npx gpu-container` downloads the platform binary from the [GitHub Release](https://github.com/mcp-tool-shop-org/gpu-container/releases), verifies its SHA256 against the published checksums, caches it, and runs it. **No Python required.**

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m
```

> Prefer Python? `pip install "gpu-container[host]"` installs the five `gpu-container-*` commands directly.

## Why it exists

On Windows/WSL2, CUDA Unified-Memory oversubscription is **unavailable** (NVIDIA-confirmed) and the wrong tool for decode even on Linux. So `gpu-container` doesn't rely on runtime overflow magic — it makes **explicit, declared placement** the product. That's the moat.

## What it does

`gpu-container <command>` is five tools in one binary:

| Command | Does |
|---|---|
| `profile` | Measure the rig (VRAM, PCIe, NVMe, pinnable RAM, CPU bandwidth) + the model |
| `plan` | Compute explicit VRAM/RAM/NVMe placement + a calibrated throughput forecast; **ship or refuse** |
| `receipt` | Verify a plan against a real `llama-bench` run; write a calibration point back |
| `concentration` | De-risk the per-expert cache — measure routing concentration before building for it |
| `watchdog` | Supervise a GPU job; abort on a host-memory / power / VRAM breach |

- **MoE expert tiering** (flagship) — shared/attention layers in VRAM, experts in CPU RAM via llama.cpp `--n-cpu-moe`. Proven live on Qwen3-30B-A3B.
- **Measured receipts** — a real run verifies the forecast against a roofline *ceiling* and a calibrated *band*; the receipt sharpens the next plan.
- **Honest refusal** — no plan clears >1 tok/s? It refuses, and explains why.
- **Rig-safety watchdog** — born from a real incident; supervise any GPU job so a bad plan can't take the machine down.

## Run a GPU job safely

```bash
gpu-container watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json
```

## Docs

- **Quickstart + handbook:** https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **Source + full docs:** https://github.com/mcp-tool-shop-org/gpu-container
- **Privacy & safety:** local, offline, no telemetry, no network egress. [SECURITY.md](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/SECURITY.md)

<div align="center">

Built by <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> · MIT Licensed

</div>
