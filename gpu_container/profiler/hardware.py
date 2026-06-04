"""Hardware profiler — detect and measure the rig from inside the container.

REAL: GPU identity/VRAM/driver/compute-cap via pynvml (preferred — NVML directly, v2 so
driver-`reserved` VRAM is not miscounted as `used`) with an nvidia-smi text fallback;
platform (os / WSL2 / container / nvidia-runtime) detection; system RAM.

MEASURED (docker-knowledge wave-2 `hw-measurement`, via `cuda_bench` + `nvme_bench`):
PCIe H2D/D2H (pinned cudaMemcpy timed by cudaEvent), NVMe sequential + random-QD1 (fio
direct-io on a validated mount), and the WSL2 pinnable-RAM ceiling (cudaHostAlloc probe).

Design rule (wave-1): a measurement we have NOT taken is `None`, never a guessed number —
honest refusal downstream depends on honest inputs.
"""
from __future__ import annotations

import os
import platform
import subprocess
from typing import List, Optional

from . import cuda_bench, nvme_bench
from .schema import BandwidthInfo, GpuInfo, HardwareProfile, MemoryInfo, PlatformInfo

_SMI_FIELDS = [
    "name", "driver_version", "memory.total", "memory.free",
    "compute_cap", "pcie.link.gen.max", "pcie.link.width.max",
]


def _nvidia_smi_query() -> Optional[List[str]]:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={','.join(_SMI_FIELDS)}",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    # first GPU only (single-GPU product)
    return [c.strip() for c in out.stdout.strip().splitlines()[0].split(",")]


def _as_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _clean(s: Optional[str]) -> Optional[str]:
    if not s or s in ("[Not Supported]", "[N/A]", "N/A"):
        return None
    return s


def _refine_vram_pynvml(gpu: GpuInfo) -> GpuInfo:
    """Override VRAM total/free with NVML values read directly (pynvml), preferring v2.

    v2 (`nvmlMemory_v2`) reports driver-`reserved` separately; v1 folds it into `used`, so
    v1 `free` under-reports. If pynvml is absent or NVML init fails (can happen in some
    Docker-on-WSL2 vintages), we silently keep the nvidia-smi values.
    """
    try:
        import pynvml  # optional [gpu] dependency
    except Exception:
        return gpu
    try:
        pynvml.nvmlInit()
    except Exception:
        return gpu
    try:
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem, src = None, None
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(h, version=pynvml.nvmlMemory_v2)
            src = "pynvml-v2"
        except Exception:
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                src = "pynvml-v1"
            except Exception:
                mem = None
        if mem is not None:
            gpu.vram_total_mib = int(mem.total // (1024 * 1024))
            gpu.vram_free_mib = int(mem.free // (1024 * 1024))
            reserved = getattr(mem, "reserved", None)
            gpu.vram_reserved_mib = int(reserved // (1024 * 1024)) if reserved else None
            gpu.vram_source = src
        # compute capability, if smi left it unknown
        if gpu.compute_capability is None:
            try:
                major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(h)
                gpu.compute_capability = f"{major}.{minor}"
            except Exception:
                pass
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
    return gpu


def detect_gpu() -> GpuInfo:
    vals = _nvidia_smi_query()
    if not vals or len(vals) < 4:
        gpu = GpuInfo(name="unknown (nvidia-smi unavailable)")
    else:
        g = dict(zip(_SMI_FIELDS, vals + [None] * (len(_SMI_FIELDS) - len(vals))))
        gpu = GpuInfo(
            name=_clean(g["name"]) or "unknown",
            vram_total_mib=_as_int(g["memory.total"]),
            vram_free_mib=_as_int(g["memory.free"]),
            driver_version=_clean(g["driver_version"]),
            compute_capability=_clean(g["compute_cap"]),
            # NVML pcie.link.* are advisory under WSL2 (often N/A / downclocked) — capture but
            # the effective link is DERIVED from measured bandwidth, not from these fields.
            pcie_gen=_as_int(g["pcie.link.gen.max"]),
            pcie_width=_as_int(g["pcie.link.width.max"]),
            vram_source="nvidia-smi" if _as_int(g["memory.total"]) is not None else None,
        )
    gpu.cuda_version = cuda_bench.runtime_version()
    return _refine_vram_pynvml(gpu)


def _cgroup_container_token() -> Optional[str]:
    """Return the container engine hinted by /proc/1/cgroup, or None."""
    try:
        with open("/proc/1/cgroup", "r", encoding="utf-8", errors="ignore") as f:
            blob = f.read().lower()
    except OSError:
        return None
    for tok in ("docker", "containerd", "kubepods", "libpod", "podman"):
        if tok in blob:
            return "docker" if tok in ("docker", "containerd") else tok
    return None


def _is_wsl2() -> bool:
    # "microsoft" in the kernel version => WSL2 kernel. NOTE: a container ON the WSL2 backend
    # inherits this too, so wsl2=True means "running on the WSL2 kernel" regardless of
    # containerization; combine with in_container to tell the two apart.
    for path in ("/proc/version", "/proc/sys/kernel/osrelease"):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                if "microsoft" in f.read().lower():
                    return True
        except OSError:
            continue
    return False


def detect_platform() -> PlatformInfo:
    osname = platform.system().lower()  # "windows" | "linux" | "darwin"
    dockerenv = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")
    cgroup_tok = _cgroup_container_token()
    in_container = dockerenv or cgroup_tok is not None
    runtime: Optional[str] = "docker" if dockerenv else cgroup_tok
    wsl2 = _is_wsl2()

    # GPU passthrough device differs by platform: /dev/nvidia* (native-Linux container, via
    # the NVIDIA Container Toolkit prestart hook) vs /dev/dxg (WSL2 — the GPU rides the
    # WDDM/DirectX path and NO /dev/nvidia* node exists, so checking only that gives a false
    # negative even though the GPU is fully usable; verified on this rig).
    nvidia_runtime: Optional[bool] = None
    if in_container:
        nvidia_runtime = any(os.path.exists(p) for p in
                             ("/dev/nvidia0", "/dev/dxg", "/proc/driver/nvidia/version"))

    # UVM oversubscription is unavailable on windows/wsl2 (docker-knowledge container-runtime).
    uvm = False if (osname == "windows" or wsl2) else None
    return PlatformInfo(
        os=osname,
        in_container=in_container,
        wsl2=wsl2,
        container_runtime=runtime,
        nvidia_runtime=nvidia_runtime,
        uvm_oversubscription=uvm,
    )


def detect_memory() -> MemoryInfo:
    try:
        import psutil  # optional dependency
        vm = psutil.virtual_memory()
        return MemoryInfo(
            ram_total_gib=round(vm.total / 1024**3, 2),
            ram_available_gib=round(vm.available / 1024**3, 2),
        )
    except Exception:
        pass
    # Linux fallback without psutil
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            kb = {ln.split(":")[0]: ln.split()[1] for ln in f if ":" in ln}
        total = int(kb.get("MemTotal", 0)) / 1024**2
        avail = int(kb.get("MemAvailable", 0)) / 1024**2
        return MemoryInfo(ram_total_gib=round(total, 2) or None,
                          ram_available_gib=round(avail, 2) or None)
    except OSError:
        return MemoryInfo()


def measure_bandwidth(bench_dir: Optional[str] = None) -> BandwidthInfo:
    """Run the PCIe (cuda_bench) and NVMe (nvme_bench) measurements -> BandwidthInfo.

    Each axis fills in independently; an axis that cannot be measured stays `None` and its
    reason is recorded in `details`/`method`. Numbers are achieved/measured, never spec-sheet.
    """
    pcie = cuda_bench.measure_pcie()
    nvme = nvme_bench.measure_nvme(bench_dir=bench_dir)

    bw = BandwidthInfo(
        pcie_h2d_gbps=pcie.get("h2d_gbps"),
        pcie_d2h_gbps=pcie.get("d2h_gbps"),
        nvme_seq_read_gbps=nvme.get("seq_read_gbps"),
        nvme_rand_qd1_read_iops=nvme.get("rand_qd1_iops"),
        nvme_rand_qd1_read_mbps=nvme.get("rand_qd1_mbps"),
    )

    methods: List[str] = []
    if bw.pcie_h2d_gbps is not None:
        methods.append("pcie:cudaMemcpy-pinned-cudaEvent")
    else:
        methods.append(f"pcie:none ({pcie.get('error', 'unknown')})")
    if bw.nvme_seq_read_gbps is not None or bw.nvme_rand_qd1_read_iops is not None:
        methods.append("nvme:fio-direct-libaio")
    else:
        methods.append(f"nvme:none ({nvme.get('error', 'unknown')})")
    bw.method = "; ".join(methods)

    # Sanity flag: an achieved H2D far below Gen5 expectation points at an x8 link, a
    # downclocked link, or WSL2 perturbation — flag, don't silently trust (wave-2).
    if bw.pcie_h2d_gbps is not None and bw.pcie_h2d_gbps < 30:
        pcie["sanity"] = "H2D below Gen5 expectation (~50 GB/s); check link width / WSL2 perturbation"
    bw.details = {"pcie": pcie, "nvme": nvme}
    return bw


def measure_cpu_mem_bw(array_mib: int = 256, iters: int = 7) -> dict:
    """CPU RAM read+write bandwidth (GB/s) via a large out-of-cache numpy copy — the input the
    MoE CPU-offload throughput model keys off (CPU computes its experts at RAM bandwidth). Honest
    None if numpy is unavailable; the planner then flags a labelled default."""
    out = {"gbps": None, "method": None}
    try:
        import statistics
        import time

        import numpy as np
    except Exception:
        out["method"] = "not-measured: numpy unavailable"
        return out
    try:
        n = (array_mib * 1024 * 1024) // 8  # float64 elements; 256 MiB >> L3 to defeat cache
        a = np.empty(n, dtype=np.float64)
        b = np.ones(n, dtype=np.float64)
        np.copyto(a, b)  # warmup
        times = []
        for _ in range(iters):
            t0 = time.perf_counter()
            np.copyto(a, b)  # read b + write a == 2 * n * 8 bytes
            times.append(time.perf_counter() - t0)
        med = statistics.median(times)
        out["gbps"] = round((2 * n * 8) / med / 1e9, 1) if med > 0 else None
        out["method"] = f"numpy copy (read+write), {array_mib} MiB, median of {iters}"
    except Exception as e:
        out["method"] = f"not-measured: {e}"
    return out


def _probe_pinnable(mem: MemoryInfo) -> None:
    """Fill the pinnable-RAM ceiling on `mem` via a cudaHostAlloc probe (in place).

    The probe is capped at ~75% of available RAM (absolute max 24 GiB): pinned memory is
    page-locked and physically resident, so an unbounded probe could destabilize the host.
    A `capped` result therefore means "ceiling is at least this" — a safe lower bound.
    """
    avail = mem.ram_available_gib or mem.ram_total_gib or 16.0
    safe_max_mib = max(512, min(int(avail * 1024 * 0.75), 24576))
    pin = cuda_bench.measure_pinnable_ceiling(max_mib=safe_max_mib)
    if pin.get("ceiling_gib") is not None:
        mem.pinnable_ceiling_gib = pin["ceiling_gib"]
        mem.pinnable_capped = pin.get("capped")
        mem.pinnable_method = pin.get("method")
    else:
        mem.pinnable_method = f"not-measured: {pin.get('error', 'unknown')}"


def profile_hardware(created: str, run_benches: bool = True,
                     bench_dir: Optional[str] = None) -> HardwareProfile:
    gpu = detect_gpu()
    plat = detect_platform()
    mem = detect_memory()
    if run_benches:
        bw = measure_bandwidth(bench_dir=bench_dir)
        _probe_pinnable(mem)
        cb = measure_cpu_mem_bw()
        mem.cpu_mem_bw_gbps = cb["gbps"]
        mem.cpu_mem_bw_method = cb["method"]
    else:
        bw = BandwidthInfo(method="not-measured (--no-bench): identity detection only")
    return HardwareProfile(gpu=gpu, platform=plat, bandwidth=bw, memory=mem)
