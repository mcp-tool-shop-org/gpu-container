"""Hardware profiler — detect and (eventually) measure the rig.

REAL today: GPU identity/VRAM/driver/compute-cap/PCIe-link via `nvidia-smi`; platform
(os / WSL2 / container) detection; system RAM. These run wherever `nvidia-smi` is on PATH
— ideally INSIDE the container, which is the only honest vantage point (docker-knowledge
lane `hw-measurement`: figures like PCIe link width can differ host-vs-container).

STUBBED (wave-2 hardens the methodology, then this fills in): the *measured* bandwidth
benchmarks — PCIe H2D/D2H via cudaMemcpy timing, NVMe sequential AND random-QD1 — and the
WSL2 pinnable-RAM ceiling. Until measured they are `None`, never guessed.
"""
from __future__ import annotations

import os
import platform
import subprocess
from typing import List, Optional

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


def _as_int(s: str) -> Optional[int]:
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _clean(s: Optional[str]) -> Optional[str]:
    if not s or s in ("[Not Supported]", "[N/A]", "N/A"):
        return None
    return s


def detect_gpu() -> GpuInfo:
    vals = _nvidia_smi_query()
    if not vals or len(vals) < 4:
        return GpuInfo(name="unknown (nvidia-smi unavailable)")
    g = dict(zip(_SMI_FIELDS, vals + [None] * (len(_SMI_FIELDS) - len(vals))))
    return GpuInfo(
        name=_clean(g["name"]) or "unknown",
        vram_total_mib=_as_int(g["memory.total"]),
        vram_free_mib=_as_int(g["memory.free"]),
        driver_version=_clean(g["driver_version"]),
        compute_capability=_clean(g["compute_cap"]),
        pcie_gen=_as_int(g["pcie.link.gen.max"]),
        pcie_width=_as_int(g["pcie.link.width.max"]),
    )


def detect_platform() -> PlatformInfo:
    osname = platform.system().lower()  # "windows" | "linux" | "darwin"
    in_container = os.path.exists("/.dockerenv")
    wsl2 = False
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
            wsl2 = "microsoft" in f.read().lower()
    except OSError:
        wsl2 = False
    # UVM oversubscription is unavailable on windows/wsl2 (docker-knowledge container-runtime).
    # The planner confirms against the KB; we record the platform signal where it's certain.
    uvm = False if (osname == "windows" or wsl2) else None
    return PlatformInfo(
        os=osname,
        in_container=in_container,
        wsl2=wsl2,
        container_runtime="docker" if in_container else None,
        nvidia_runtime=None,  # not reliably detectable from inside; left unknown
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


def measure_bandwidth() -> BandwidthInfo:
    """STUB — wave-2 (docker-knowledge `hw-measurement`) hardens the in-container method.

    Planned: PCIe H2D/D2H via pinned-buffer cudaMemcpy timing; NVMe sequential via large
    bypass-cache read; NVMe random-QD1 read IOPS (the figure a sequential assumption gets
    wrong, and the one the cold-expert / KV-spill path actually hits). Until then: None.
    """
    return BandwidthInfo(method="not-measured: pending docker-knowledge wave-2 in-container methodology")


def profile_hardware(created: str) -> HardwareProfile:
    return HardwareProfile(
        gpu=detect_gpu(),
        platform=detect_platform(),
        bandwidth=measure_bandwidth(),
        memory=detect_memory(),
    )
