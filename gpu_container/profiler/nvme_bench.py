"""NVMe benchmark via fio — sequential AND random-QD1, on the path that actually matters.

docker-knowledge wave-2 `hw-measurement` spec:
  - Two passes: SEQUENTIAL (`--rw=read --bs=256k --iodepth=64`) and RANDOM-QD1
    (`--rw=randread --bs=4k --iodepth=1`). QD1 4k is the latency-bound figure the
    cold-expert / KV-spill streaming path actually hits; the sequential headline overstates
    offload throughput by ~10x, so the planner keys streaming math off the QD1 number.
  - `--direct=1 --ioengine=libaio` is mandatory to bypass the OS page cache (otherwise we
    measure RAM, not the SSD). If O_DIRECT is unsupported we REFUSE — never a silent
    buffered fallback that reports a dishonest number.
  - Target a bind-mounted / named volume on the ext4 vdisk. The container's overlay2 layer
    breaks O_DIRECT and mismeasures; a `/mnt/<letter>` drvfs/9p path is ~5-10x slower than
    real ext4. We detect the mount type and refuse the wrong filesystem rather than lie.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Optional, Tuple

# Filesystems we must NOT measure on (they produce dishonest numbers).
_BAD_FS = {"overlay", "overlayfs", "9p", "drvfs", "v9fs", "fuse.drvfs"}


def _mount_for(path: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (mountpoint, fstype, device) for the filesystem backing `path`.

    Reads /proc/mounts and picks the longest mountpoint that is a prefix of `path`.
    Returns (None, None, None) where /proc/mounts is unavailable (e.g. a Windows host).
    """
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as f:
            entries = []
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    entries.append((parts[1], parts[2], parts[0]))  # mountpoint, fstype, device
    except OSError:
        return (None, None, None)
    target = os.path.abspath(path)
    best = (None, None, None)
    best_len = -1
    for mp, fstype, dev in entries:
        if (target == mp or target.startswith(mp.rstrip("/") + "/") or mp == "/") and len(mp) > best_len:
            best, best_len = (mp, fstype, dev), len(mp)
    return best


def resolve_bench_dir(explicit: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Pick the directory to benchmark. Returns (dir, reason_if_none)."""
    candidate = explicit or os.environ.get("GPU_CONTAINER_BENCH_DIR")
    if candidate:
        return (candidate, None)
    if os.path.isdir("/bench"):  # the conventional bind-mount target (see Dockerfile)
        return ("/bench", None)
    return (None, "no bench dir: pass --bench-dir or mount an ext4 volume at /bench "
                  "(-v <host-nvme-path>:/bench)")


def _run_fio(fio: str, testfile: str, rw: str, bs: str, qd: int,
             size_gib: int, runtime_s: int, ramp_s: int) -> dict:
    cmd = [
        fio, "--name=gpc", f"--filename={testfile}",
        "--direct=1", "--ioengine=libaio",
        f"--rw={rw}", f"--bs={bs}", f"--iodepth={qd}", "--numjobs=1",
        f"--size={size_gib}G", "--time_based", f"--runtime={runtime_s}",
        f"--ramp_time={ramp_s}", "--group_reporting", "--output-format=json",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=runtime_s + ramp_s + 180)
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        return {"error": f"fio invocation failed: {e}"}

    blob = (p.stdout or "") + "\n" + (p.stderr or "")
    if "O_DIRECT" in blob or "does not support" in blob or "Operation not supported" in blob:
        return {"error": "O_DIRECT unsupported on this path (overlay fs?) — refusing buffered "
                         "fallback; mount an ext4 volume", "stderr": (p.stderr or "")[:400]}
    if p.returncode != 0:
        return {"error": f"fio exit {p.returncode}", "stderr": (p.stderr or "")[:400]}

    try:
        j = json.loads(p.stdout)
        r = j["jobs"][0]["read"]
    except (ValueError, KeyError, IndexError) as e:
        return {"error": f"could not parse fio json: {e}"}

    lat = r.get("lat_ns") or r.get("clat_ns") or {}
    return {
        "bw_bytes": r.get("bw_bytes"),          # bytes/sec
        "iops": r.get("iops"),
        "lat_us_mean": round(lat["mean"] / 1000.0, 2) if lat.get("mean") is not None else None,
    }


def measure_nvme(bench_dir: Optional[str] = None, size_gib: int = 4,
                 runtime_s: int = 8, ramp_s: int = 2) -> dict:
    """Run the seq + random-QD1 fio passes on a validated mount. Honest dict, never raises."""
    out: dict = {
        "seq_read_gbps": None, "rand_qd1_iops": None, "rand_qd1_mbps": None,
        "rand_qd1_lat_us": None, "fs_type": None, "mount": None, "bench_dir": None,
        "direct": True, "ioengine": "libaio", "size_gib": size_gib,
    }
    fio = shutil.which("fio")
    if not fio:
        out["error"] = "fio not found (install fio in the container)"
        return out

    target, reason = resolve_bench_dir(bench_dir)
    if target is None:
        out["error"] = reason
        return out
    out["bench_dir"] = target

    try:
        os.makedirs(target, exist_ok=True)
    except OSError as e:
        out["error"] = f"bench dir not writable: {e}"
        return out

    mp, fstype, _dev = _mount_for(target)
    out["mount"], out["fs_type"] = mp, fstype
    if fstype and fstype.lower() in _BAD_FS:
        out["error"] = (f"refusing to benchmark fs '{fstype}' at {mp}: overlay/drvfs/9p "
                        f"mismeasure NVMe — mount an ext4 volume at {target}")
        return out
    if target.startswith("/mnt/") and fstype not in (None,):
        out["error"] = f"refusing /mnt drvfs path {target} (~5-10x slower than ext4)"
        return out

    testfile = os.path.join(target, ".gpu_container_fio_test.bin")
    try:
        seq = _run_fio(fio, testfile, "read", "256k", 64, size_gib, runtime_s, ramp_s)
        qd1 = _run_fio(fio, testfile, "randread", "4k", 1, size_gib, runtime_s, ramp_s)
    finally:
        try:
            if os.path.exists(testfile):
                os.remove(testfile)
        except OSError:
            pass

    errors = []
    if "error" in seq:
        errors.append("seq: " + seq["error"])
    elif seq.get("bw_bytes"):
        out["seq_read_gbps"] = round(seq["bw_bytes"] / 1e9, 3)
    if "error" in qd1:
        errors.append("qd1: " + qd1["error"])
    else:
        if qd1.get("iops") is not None:
            out["rand_qd1_iops"] = round(qd1["iops"], 1)
        if qd1.get("bw_bytes"):
            out["rand_qd1_mbps"] = round(qd1["bw_bytes"] / 1e6, 2)
        out["rand_qd1_lat_us"] = qd1.get("lat_us_mean")
    if errors:
        out["error"] = " | ".join(errors)
    return out
