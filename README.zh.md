<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.md">English</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![npm](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Handbook](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**一个支持 GPU 的容器会暴露设备。一个具有模型感知能力的运行时会决定哪些内容驻留在显存 (VRAM)、固定内存 (pinned RAM) 和 NVMe 中。**

</div>

运行您机器能够实际支持的最大且有用的本地模型，并采用明确的放置计划、基准测试结果，并在计划可能导致性能下降时拒绝执行。

## 架构

```
Windows / WSL2 / Linux host
  └─ GPU-enabled Docker container
      └─ Inference runtime
          ├─ VRAM: hot weights, active layers, activations, KV working set
          ├─ pinned RAM: CPU-offloaded weights, MoE experts, KV spill/reuse
          └─ NVMe: mmap shards, disk offload, cold experts, cold KV
```

## 产品边界

```
Docker         = packaging + GPU exposure
CUDA/runtime   = compute backend
Planner        = memory law
Inference engine = execution
```

## 核心功能

1. **硬件分析器** — 检测显存 (VRAM)、内存 (RAM)、GPU 类型、WSL/原生 Linux、NVMe 速度、CUDA 是否可用
2. **模型分析器** — 检测密集型与 MoE（混合专家）模型、最大层、总权重、量化、按上下文长度计算的 KV 增长
3. **运行时规划器** — 为 llama.cpp、vLLM、Accelerate、TensorRT-LLM 或 DeepSpeed 风格的卸载生成启动计划
4. **放置结果** — 显示哪些内容在显存 (VRAM) 中，哪些内容在内存 (RAM) 中，哪些内容在磁盘上，预期的瓶颈，测量的令牌/秒
5. **MoE 专用路径** — 将始终处于活动状态的层保留在 GPU 上，将专家路由到 CPU/RAM，对于冷备用，则路由到 NVMe
6. **路由风险缓解** — 测量模型的 MoE 路由是否偏斜到足以使每个专家的缓存有所帮助，然后再进行构建 (`gpu-container-concentration`)
7. **设备安全看门狗** — 轮询 GPU 功耗/温度/显存 + 主机内存，并与可配置的阈值进行比较；AI 代理或自主循环会在运行危及设备之前中止运行 (`gpu-container-watchdog`)

## 关键约束

在 Windows/WSL 上，CUDA 统一内存超配**不是正确的做法**。CUDA 将 Windows/WSL 视为有限的统一内存支持——没有细粒度的 GPU 页面错误迁移，没有超出物理显存的 GPU 内存超配。该产品是**明确的推理内存放置**，而不是“Docker 显存溢出”。

## 状态

已构建并可运行：`gpu-container-profile`、`gpu-container-plan`、`gpu-container-receipt`（带有重新校准循环）、`gpu-container-concentration`（路由风险缓解）和 `gpu-container-watchdog`（安全地监控 GPU 作业）。llama.cpp 是集成的后端；放置计算与后端无关。从 [快速入门](docs/quickstart.md) 开始。

## 隐私与安全

`gpu-container` 是一种**本地、离线工具**——它不会进行任何网络调用，并且默认情况下或以其他方式不会收集任何遥测数据。它会读取 GPU 指标 (`nvidia-smi` / NVML) 和主机内存 (`psutil`)、您提供的模型 `config.json` 以及您指向它的 JSON 文件；它只会写入您指定的输出路径。它**不会**读取或传输模型权重、凭据或令牌。主机级别的操作 (`wsl --shutdown`、`docker stop`、`kill`) 仅在您通过看门狗的 `--on-breach` 明确选择时才会运行；默认情况下，它不会对您的机器进行任何操作，超出它所监控的作业范围。完整策略：[SECURITY.md](SECURITY.md)。

## 文档

- [`docs/quickstart.md`](docs/quickstart.md) — 端到端演练：分析 → 计划 → 在看门狗下启动 → 结果 → 重新校准
- [`docs/cli.md`](docs/cli.md) — 五个命令：概要、标志、退出代码、示例
- [`docs/architecture.md`](docs/architecture.md) — 内存分层模型、数据流、MoE 专家路由、重新校准循环
- [`docs/features.md`](docs/features.md) — 七个核心功能的详细介绍
- [`docs/moe-lane-architecture.md`](docs/moe-lane-architecture.md) — 旗舰 MoE 通道
- [`docs/derisk-concentration.md`](docs/derisk-concentration.md) — 每个专家的缓存风险缓解门控（路由集中度）
- [`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`](docs/decisions/0001-per-expert-cache-build-vs-upstream.md) — ADR-0001：使用缓存机制，贡献策略
- [`docs/constraints.md`](docs/constraints.md) — 非目标 + Windows/WSL CUDA 统一内存的修正
- [`docs/prior-art.md`](docs/prior-art.md) — 我们编排的运行时，以及该产品填补的空白
- [`docs/feasibility.md`](docs/feasibility.md) — 可行性评估、研究基础，以及已确认可行的内容

---

<div align="center">

由 <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> 构建 · MIT 许可

</div>
