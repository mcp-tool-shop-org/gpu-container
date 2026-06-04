# Prior Art

Existing solutions that touch parts of this problem space. None of them are the complete product.

## Inference Runtimes (backends we orchestrate)

### llama.cpp

- Memory placement: `--n-gpu-layers` (integer layer split), `--mmap` (disk-backed), `--mlock` (pinned RAM)
- MoE support: expert offload via `--override-kv` flags (limited)
- Strengths: lightweight, GGUF ecosystem, quantization variety (Q2–Q8, IQ, FP16)
- Gap: no automated planning. User must manually calculate layer counts. No receipt.

### vLLM (v0.22.0)

- Memory placement: `--gpu-memory-utilization`, `--cpu-offload-gb`, `--enforce-eager`
- KV offload: `v1/kv_offload/` module — CPU offload (LRU/ARC policies), filesystem tiering
- Weight offload: `model_executor/offloader/` — prefetch and UVA modes
- Strengths: PagedAttention, continuous batching, production-grade serving
- Gap: requires explicit configuration. No hardware auto-detection. No cross-runtime planning.

### HuggingFace Accelerate

- Memory placement: `device_map="auto"` with `max_memory` dict
- Offload: `disk_offload`, `cpu_offload` via hooks on forward pass
- Strengths: works with any HF model, simple API
- Gap: `"auto"` is naive (fills GPU then spills). No bandwidth-aware planning. No MoE specialization.

### ExLlamaV2

- Memory placement: manual GPU split across multiple GPUs, cache quantization (FP8/Q4)
- Strengths: fastest single-GPU inference for GPTQ/EXL2 models
- Gap: manual configuration only. No profiling or receipt system.

### DeepSpeed-Inference (ZeRO-Inference)

- Memory placement: automatic offload to CPU/NVMe with prefetch
- Strengths: proven at scale, handles very large models
- Gap: heavyweight, training-focused ecosystem, complex setup, Docker integration unclear

### TensorRT-LLM

- Memory placement: weight streaming (load from host memory on demand)
- Strengths: highest throughput on NVIDIA GPUs, optimized kernels
- Gap: requires engine build step, model support lag, complex config

## Profiling / Planning Tools

### nvidia-smi / NVML / pynvml

- What it does: GPU state monitoring (memory, utilization, thermals, clocks)
- What it doesn't: no model-awareness, no placement planning

### HuggingFace Model Card / Config

- What it does: declares architecture, parameter count, context length
- What it doesn't: no per-layer memory breakdown, no quantized-size estimates, no runtime mapping

### llm-bench / vllm-bench

- What they do: measure throughput/latency for a running model
- What they don't: no pre-launch planning, no placement validation

## Container / GPU Orchestration

### NVIDIA Container Toolkit

- What it does: GPU passthrough to Docker containers, driver injection
- What it doesn't: no memory planning, no model awareness

### Run:ai / Kubernetes GPU scheduling

- What it does: cluster-level GPU allocation, fractional GPU
- What it doesn't: not for single-machine, not for memory-tier planning

## The Gap This Product Fills

```
                    Existing tools cover:
                    ┌──────────────┐
                    │ GPU detection │ ← nvidia-smi
                    │ Model loading │ ← HF, GGUF
                    │ Execution     │ ← vLLM, llama.cpp
                    │ Monitoring    │ ← nvml, bench tools
                    └──────────────┘

                    Nobody covers:
                    ┌──────────────────────────────────┐
                    │ Pre-launch placement planning     │
                    │ Cross-runtime config generation   │
                    │ Hardware-aware model feasibility  │
                    │ MoE expert tier assignment        │
                    │ Post-launch receipt + validation  │
                    │ Honest refusal when it won't work │
                    └──────────────────────────────────┘
```

Every runtime has *some* offload capability. None of them:
1. Profile your hardware first
2. Analyze the model structure
3. Generate the optimal config for YOUR machine
4. Prove it worked after launch
5. Tell you "no" when the math doesn't add up
