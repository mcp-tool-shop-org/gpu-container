<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.md">English</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

![CI](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/gpu-container)
![npm](https://img.shields.io/npm/v/gpu-container)
![许可证：MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![手册](https://img.shields.io/badge/handbook-docs-blue)

**启用 GPU 的容器会暴露设备。一个具备模型感知能力的运行时环境会决定哪些数据存储在显存 (VRAM)、固定内存 (pinned RAM) 和 NVMe 存储中。**

</div>

运行您机器能够稳定支持的最大规模的实用本地模型——通过明确的部署计划、基准测试结果，并在计划可能导致系统崩溃时进行拒绝。这个 npm 包是一个**无需任何先决条件的启动器**：`npx gpu-container` 从 [GitHub 发布页面](https://github.com/mcp-tool-shop-org/gpu-container/releases) 下载平台二进制文件，验证其 SHA256 值与已发布的校验和是否匹配，然后将其缓存并运行。**无需 Python。**

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m
```

如果您更喜欢使用 Python，请运行 `pip install "gpu-container[host]"`，此命令将直接安装五个 `gpu-container-*` 命令。

## 它存在的意义是什么？

在 Windows/WSL2 平台上，CUDA 统一内存超配功能**不可用**（已得到 NVIDIA 的确认），即使在 Linux 平台上，它也不是解码的合适工具。因此，`gpu-container` 不依赖于运行时溢出机制，而是采用**明确、声明式的资源分配**方式。这就是它的优势所在。

## 它的作用是什么

`gpu-container <命令>` 是一个包含五个工具的程序：

| 命令；指挥 | 是否 |
|---|---|
| `profile` | 测量硬件配置（显存、PCIe、NVMe、可分配的内存、CPU 带宽）以及模型。 |
| `plan` | 计算出明确的 VRAM/RAM/NVMe 存储分配方案，并进行校准后的性能预测；**如果可行，就交付；如果不可行，就拒绝。** |
| `receipt` | 将计划与实际的 `llama-bench` 运行结果进行比对；并将校准点写回。 |
| `concentration` | 降低专家级缓存的风险——在构建缓存之前，先评估路由集中度。 |
| `watchdog` | 监控 GPU 任务；如果出现主机内存、电源或显存不足的情况，则中止任务。 |

- **MoE 专家分层**（旗舰版）——在 VRAM 中共享/注意力层，通过 llama.cpp 的 `--n-cpu-moe` 参数，将专家模型置于 CPU RAM 中。已在 Qwen3-30B-A3B 上进行过实际测试。
- **精确的验证**——通过实际运行，将预测结果与性能上限和校准后的性能范围进行对比；验证结果将用于优化下一个计划。
- **诚实的拒绝**——如果没有任何计划能够达到超过 1 个 token/秒的性能，系统会拒绝该计划，并解释原因。
- **硬件安全监控**——源于一次真实的事件；监控任何 GPU 任务，以防止不良计划导致系统崩溃。

## 安全地运行 GPU 任务

```bash
gpu-container watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json
```

## 文档

- **快速入门指南 + 使用手册：**https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **源代码 + 完整文档：**https://github.com/mcp-tool-shop-org/gpu-container
- **隐私与安全：**本地运行，离线使用，不收集用户数据，不进行网络数据传输。[SECURITY.md](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/SECURITY.md)

<div align="center">

由 <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> 构建 · 采用 MIT 许可。

</div>
