"""CUDA bandwidth + pinned-memory benchmarks via ctypes against libcudart.

No PyTorch, no CuPy, no nvcc: we `dlopen` the CUDA Runtime library that ships in the
`nvidia/cuda:*-runtime` base image and call it directly. cudaMemcpy and cudaHostAlloc
are copy-engine / driver operations — they do NOT launch a compiled device kernel — so
this works on sm_120 (Blackwell / RTX 5090) without a kernel image targeting it.

Methodology is the docker-knowledge wave-2 `hw-measurement` spec (run INSIDE the container,
the only honest vantage):
  - PCIe: PINNED (page-locked) host buffer, large transfer (>=64 MB, we use 256 MB),
    one untimed warmup, median of N copies timed by cudaEvent. H2D and D2H measured
    SEPARATELY (asymmetry is real). Report achieved GB/s — NEVER the 64 GB/s theoretical.
  - Pinnable ceiling: WSL2/WDDM collapses cudaHostAlloc to ~300-500 MB inside Docker-on-WSL2
    (vs GBs native). MEASURE it with an escalating alloc probe — do not assume.

Every entry point degrades to an honest error dict (never raises) so the profiler can record
`None` + provenance rather than crash or guess.
"""
from __future__ import annotations

import ctypes
import statistics
from ctypes.util import find_library
from typing import Optional

# --- CUDA Runtime constants ------------------------------------------------------------
_cudaSuccess = 0
_cudaErrorMemoryAllocation = 2
_cudaMemcpyHostToDevice = 1
_cudaMemcpyDeviceToHost = 2
_cudaHostAllocDefault = 0

_MIB = 1024 * 1024

# Sonames to try, newest first. The runtime image ships libcudart.so.12; we stay
# version-agnostic so a 12.x or 13.x base both work.
_CUDART_NAMES = [
    "libcudart.so.13", "libcudart.so.12", "libcudart.so",
    "cudart64_13.dll", "cudart64_12.dll",
]

_cudart: Optional[ctypes.CDLL] = None
_load_error: Optional[str] = None


def _load_cudart() -> Optional[ctypes.CDLL]:
    """Load libcudart once and pin the ctypes prototypes. Returns None if unavailable."""
    global _cudart, _load_error
    if _cudart is not None or _load_error is not None:
        return _cudart

    lib = None
    for name in _CUDART_NAMES:
        try:
            lib = ctypes.CDLL(name)
            break
        except OSError:
            continue
    if lib is None:
        found = find_library("cudart")
        if found:
            try:
                lib = ctypes.CDLL(found)
            except OSError:
                lib = None
    if lib is None:
        _load_error = "libcudart not found (expected in an nvidia/cuda:*-runtime image)"
        return None

    cvp, cvpp = ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
    ci, cipp = ctypes.c_int, ctypes.POINTER(ctypes.c_int)
    cf, cfp = ctypes.c_float, ctypes.POINTER(ctypes.c_float)
    csz = ctypes.c_size_t

    sigs = {
        "cudaGetDeviceCount": [cipp],
        "cudaSetDevice": [ci],
        "cudaMalloc": [cvpp, csz],
        "cudaFree": [cvp],
        "cudaHostAlloc": [cvpp, csz, ctypes.c_uint],
        "cudaFreeHost": [cvp],
        "cudaMemcpy": [cvp, cvp, csz, ci],
        "cudaEventCreate": [cvpp],
        "cudaEventRecord": [cvp, cvp],
        "cudaEventSynchronize": [cvp],
        "cudaEventElapsedTime": [cfp, cvp, cvp],
        "cudaEventDestroy": [cvp],
        "cudaDeviceSynchronize": [],
        "cudaGetLastError": [],
        "cudaRuntimeGetVersion": [cipp],
    }
    for fn, argtypes in sigs.items():
        f = getattr(lib, fn)
        f.argtypes = argtypes
        f.restype = ctypes.c_int
    lib.cudaGetErrorString.argtypes = [ci]
    lib.cudaGetErrorString.restype = ctypes.c_char_p

    _cudart = lib
    return _cudart


def _errstr(lib: ctypes.CDLL, rc: int) -> str:
    try:
        s = lib.cudaGetErrorString(rc)
        return s.decode() if s else f"cuda error {rc}"
    except Exception:
        return f"cuda error {rc}"


def available() -> bool:
    """True if libcudart loaded and at least one CUDA device is visible."""
    lib = _load_cudart()
    if lib is None:
        return False
    cnt = ctypes.c_int(0)
    rc = lib.cudaGetDeviceCount(ctypes.byref(cnt))
    return rc == _cudaSuccess and cnt.value > 0


def runtime_version() -> Optional[str]:
    lib = _load_cudart()
    if lib is None:
        return None
    v = ctypes.c_int(0)
    if lib.cudaRuntimeGetVersion(ctypes.byref(v)) != _cudaSuccess:
        return None
    # encoded as 1000*major + 10*minor
    return f"{v.value // 1000}.{(v.value % 1000) // 10}"


def load_error() -> Optional[str]:
    _load_cudart()
    return _load_error


# --- PCIe bandwidth --------------------------------------------------------------------
def _time_copies(lib, dst, src, nbytes, kind, iters) -> Optional[list]:
    """Return per-iteration milliseconds for cudaMemcpy, timed by cudaEvent. None on failure."""
    start, stop = ctypes.c_void_p(), ctypes.c_void_p()
    if lib.cudaEventCreate(ctypes.byref(start)) != _cudaSuccess:
        return None
    if lib.cudaEventCreate(ctypes.byref(stop)) != _cudaSuccess:
        lib.cudaEventDestroy(start)
        return None
    times = []
    try:
        for _ in range(iters):
            lib.cudaEventRecord(start, None)
            rc = lib.cudaMemcpy(dst, src, nbytes, kind)
            lib.cudaEventRecord(stop, None)
            lib.cudaEventSynchronize(stop)
            if rc != _cudaSuccess:
                return None
            ms = ctypes.c_float(0.0)
            if lib.cudaEventElapsedTime(ctypes.byref(ms), start, stop) != _cudaSuccess:
                return None
            times.append(ms.value)
        return times
    finally:
        lib.cudaEventDestroy(start)
        lib.cudaEventDestroy(stop)


def measure_pcie(buffer_mib: int = 256, iters: int = 11, warmup: int = 3) -> dict:
    """Measure achieved pinned H2D and D2H PCIe bandwidth (GB/s, decimal 1e9 convention).

    Returns a dict with `h2d_gbps`, `d2h_gbps`, and provenance; on any failure returns
    `{"error": ...}` with whatever was obtained left as None — the caller records None,
    never a guess.
    """
    out: dict = {
        "h2d_gbps": None, "d2h_gbps": None, "buffer_mib": None,
        "iters": iters, "warmup": warmup, "buffer": "pinned",
        "convention": "GB/s = bytes / seconds / 1e9 (decimal, matches nvbandwidth)",
    }
    lib = _load_cudart()
    if lib is None:
        out["error"] = _load_error
        return out
    if not available():
        out["error"] = "no CUDA device visible"
        return out

    lib.cudaSetDevice(0)

    # Allocate the PINNED host buffer first, shrinking on failure (WSL2 caps this low).
    h = ctypes.c_void_p()
    nbytes = 0
    for mib in (buffer_mib, 128, 64):
        rc = lib.cudaHostAlloc(ctypes.byref(h), mib * _MIB, _cudaHostAllocDefault)
        if rc == _cudaSuccess:
            nbytes = mib * _MIB
            out["buffer_mib"] = mib
            break
        lib.cudaGetLastError()  # clear the (non-sticky) alloc error before retry
    if nbytes == 0:
        out["error"] = "cudaHostAlloc failed even at 64 MiB (pinned-memory ceiling too low)"
        return out

    d = ctypes.c_void_p()
    rc = lib.cudaMalloc(ctypes.byref(d), nbytes)
    if rc != _cudaSuccess:
        lib.cudaFreeHost(h)
        out["error"] = f"cudaMalloc({nbytes}) failed: {_errstr(lib, rc)}"
        return out

    try:
        # Warmup (untimed) per direction, then sync, to leave the cold/launch regime.
        for _ in range(max(1, warmup)):
            lib.cudaMemcpy(d, h, nbytes, _cudaMemcpyHostToDevice)
            lib.cudaMemcpy(h, d, nbytes, _cudaMemcpyDeviceToHost)
        lib.cudaDeviceSynchronize()

        h2d = _time_copies(lib, d, h, nbytes, _cudaMemcpyHostToDevice, iters)
        d2h = _time_copies(lib, h, d, nbytes, _cudaMemcpyDeviceToHost, iters)

        def gbps(times):
            if not times:
                return None
            med = statistics.median(times)
            return round(nbytes / (med / 1000.0) / 1e9, 2) if med > 0 else None

        out["h2d_gbps"] = gbps(h2d)
        out["d2h_gbps"] = gbps(d2h)
        if h2d:
            out["h2d_median_ms"] = round(statistics.median(h2d), 4)
            out["h2d_min_ms"] = round(min(h2d), 4)
        if d2h:
            out["d2h_median_ms"] = round(statistics.median(d2h), 4)
        if out["h2d_gbps"] is None and out["d2h_gbps"] is None:
            out["error"] = "all timed copies failed"
    finally:
        lib.cudaFree(d)
        lib.cudaFreeHost(h)
    return out


# --- Pinnable host-RAM ceiling ---------------------------------------------------------
def _can_pin(lib, mib: int) -> bool:
    p = ctypes.c_void_p()
    rc = lib.cudaHostAlloc(ctypes.byref(p), mib * _MIB, _cudaHostAllocDefault)
    if rc == _cudaSuccess:
        lib.cudaFreeHost(p)
        return True
    lib.cudaGetLastError()  # clear non-sticky alloc error
    return False


def measure_pinnable_ceiling(
    start_mib: int = 128, max_mib: int = 16384, resolution_mib: int = 32
) -> dict:
    """Find the largest single cudaHostAlloc that succeeds (escalate by doubling, then bisect).

    Historically WSL2 collapsed this to a few hundred MB; newer drivers can lift it to many
    GB (MEASURE, don't assume — that's the point). `max_mib` is a SAFETY cap (the caller
    sizes it to a fraction of RAM so the probe never tries to pin the whole VM). `capped=True`
    means the cap itself allocated without failing, so the ceiling is a LOWER BOUND (≥ value).
    """
    out: dict = {
        "ceiling_mib": None, "ceiling_gib": None, "capped": None,
        "method": f"escalating cudaHostAlloc probe (start={start_mib} MiB, "
                  f"safety cap {max_mib} MiB, bisect to {resolution_mib} MiB)",
    }
    lib = _load_cudart()
    if lib is None:
        out["error"] = _load_error
        return out
    if not available():
        out["error"] = "no CUDA device visible"
        return out
    lib.cudaSetDevice(0)

    # Doubling ladder from start up to (and including) the safety cap.
    ladder, mib = [], max(1, start_mib)
    while mib < max_mib:
        ladder.append(mib)
        mib *= 2
    ladder.append(max_mib)

    last_ok, first_fail = 0, None
    for size in ladder:
        if _can_pin(lib, size):
            last_ok = size
        else:
            first_fail = size
            break

    if first_fail is None:
        # Reached the safety cap with no failure -> ceiling is a lower bound.
        out["ceiling_mib"] = last_ok
        out["ceiling_gib"] = round(last_ok / 1024, 3)
        out["capped"] = True
        return out

    lo, hi = last_ok, first_fail
    while hi - lo > resolution_mib:
        mid = (lo + hi) // 2
        if mid > 0 and _can_pin(lib, mid):
            lo = mid
        else:
            hi = mid
    out["ceiling_mib"] = lo
    out["ceiling_gib"] = round(lo / 1024, 3)
    out["capped"] = False
    return out
