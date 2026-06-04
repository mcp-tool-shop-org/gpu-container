# gpu-container profiler — runs INSIDE the container, the only honest measurement vantage
# (docker-knowledge wave-2 hw-measurement). Base = CUDA 12.8 *runtime*: it ships libcudart
# for the ctypes PCIe bench and targets sm_120 (RTX 5090 / Blackwell). No nvcc needed —
# cudaMemcpy/cudaHostAlloc are copy-engine ops, not compiled device kernels.
#
# Build:  docker build -t gpu-container .
# Run:    docker run --rm --gpus all -v gpc-bench:/bench gpu-container            # full profile
#         docker run --rm --gpus all gpu-container --no-bench                     # identity only
#         docker run --rm --gpus all -v gpc-bench:/bench -v "$PWD":/out \
#                    gpu-container -o /out/profile.json
FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04

# fio = NVMe seq + random-QD1 (pulls libaio); python3/pip = the profiler itself.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip fio \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY gpu_container ./gpu_container
# [gpu]=pynvml (NVML v2 VRAM), [host]=psutil (RAM). Container venv is fine to write into.
RUN pip3 install --no-cache-dir --break-system-packages ".[gpu,host]"

# The NVMe bench writes here. Mount an ext4-backed volume (named volumes live on the WSL2
# ext4 vdisk — fast); NEVER a /mnt/<letter> drvfs bind (9p, ~5-10x slower) or the overlay
# layer (breaks O_DIRECT). The profiler refuses the wrong filesystem rather than mismeasure.
ENV GPU_CONTAINER_BENCH_DIR=/bench
VOLUME ["/bench"]

ENTRYPOINT ["python3", "-m", "gpu_container.profiler.cli"]
