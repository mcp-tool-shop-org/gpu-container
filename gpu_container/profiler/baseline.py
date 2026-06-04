"""Close the loop: write a measured profile's readouts back into the docker-knowledge KB.

The KB's `measurements` table is a key-value-with-provenance store (metric, value, unit,
context, tool, source_file, wave_id, measured_date); `v_baseline` is the read view over it.
`--emit-baseline` takes a profile.json produced INSIDE the container and records each
measured number as a row, plus drops the full profile under `baselines/<stem>.json` so the
`source_file` provenance points at a real artifact. Idempotent: re-emitting the same
`source_file` replaces its rows rather than duplicating them.

This runs on the HOST (where the KB lives), reading a profile that was measured in-container
— measurement and persistence are decoupled on purpose.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import List, Optional, Tuple

from .schema import Profile

# wave to associate measured baselines with (the hw-measurement methodology wave)
_DEFAULT_WAVE_NUMBER = 2


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-") or "rig"


def _context(profile: Profile, override: Optional[str]) -> str:
    if override:
        return override
    p = profile.hardware.platform
    parts = ["in-container" if p.in_container else "host"]
    if p.wsl2:
        parts.append("wsl2")
    return " ".join(parts)


def _rows(profile: Profile) -> List[Tuple[str, float, str, str, str]]:
    """(metric, value, unit, tool, note) for every measured (non-None) readout."""
    hw = profile.hardware
    bw, gpu, mem = hw.bandwidth, hw.gpu, hw.memory
    det = bw.details or {}
    pd, nd = det.get("pcie", {}) or {}, det.get("nvme", {}) or {}
    pcie_note = f"pinned cudaMemcpy, median of {pd.get('iters')} @ {pd.get('buffer_mib')} MiB ({pd.get('convention','')})"
    nvme_note = f"fio direct=1 {nd.get('ioengine')} on {nd.get('fs_type')} @ {nd.get('mount')}, size {nd.get('size_gib')}G"

    out: List[Tuple[str, float, str, str, str]] = []

    def add(metric, value, unit, tool, note):
        if value is not None:
            out.append((metric, float(value), unit, tool, note))

    add("pcie_h2d_gbps", bw.pcie_h2d_gbps, "GB/s", "cudaMemcpy-bench", pcie_note)
    add("pcie_d2h_gbps", bw.pcie_d2h_gbps, "GB/s", "cudaMemcpy-bench", pcie_note)
    add("nvme_seq_read_gbps", bw.nvme_seq_read_gbps, "GB/s", "fio", nvme_note + " (optimistic ceiling)")
    add("nvme_rand_qd1_iops", bw.nvme_rand_qd1_read_iops, "IOPS", "fio", nvme_note + " (the honest offload metric)")
    add("nvme_rand_qd1_mbps", bw.nvme_rand_qd1_read_mbps, "MB/s", "fio", nvme_note)
    add("pinnable_ram_ceiling_gib", mem.pinnable_ceiling_gib, "GiB", "cudaHostAlloc-probe",
        (mem.pinnable_method or "") + (" [capped=lower-bound]" if mem.pinnable_capped else ""))
    add("vram_total", gpu.vram_total_mib, "MiB", gpu.vram_source or "nvidia-smi", "device total")
    add("vram_free", gpu.vram_free_mib, "MiB", gpu.vram_source or "nvidia-smi", "device free at profile time")
    return out


def emit_baseline(
    profile: Profile,
    db_path: str,
    baselines_dir: Optional[str] = None,
    context: Optional[str] = None,
    source_stem: Optional[str] = None,
    measured_date: Optional[str] = None,
    wave_number: int = _DEFAULT_WAVE_NUMBER,
) -> dict:
    """Write the profile's measured rows into `measurements` and drop the artifact. Returns a summary."""
    if not os.path.exists(db_path):
        return {"error": f"findings.db not found at {db_path}"}

    measured_date = measured_date or profile.created
    ctx = _context(profile, context)
    stem = source_stem or f"{measured_date}-{_slug(profile.hardware.gpu.name)}"
    source_file = f"baselines/{stem}.json"
    baselines_dir = baselines_dir or os.path.join(os.path.dirname(os.path.abspath(db_path)), "baselines")

    rows = _rows(profile)
    if not rows:
        return {"error": "no measured (non-None) readouts in profile — nothing to emit; "
                         "run the profiler in-container with benches enabled first"}

    # 1) drop the profile artifact the source_file points at
    os.makedirs(baselines_dir, exist_ok=True)
    artifact_path = os.path.join(baselines_dir, f"{stem}.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write(profile.to_json() + "\n")

    # 2) write rows (idempotent by source_file)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        wid = cur.execute("SELECT id FROM waves WHERE wave_number=?", (wave_number,)).fetchone()
        wave_id = wid[0] if wid else None
        cur.execute("DELETE FROM measurements WHERE source_file=?", (source_file,))
        cur.executemany(
            "INSERT INTO measurements (metric, value, unit, context, tool, source_file, note, "
            "wave_id, measured_date) VALUES (?,?,?,?,?,?,?,?,?)",
            [(m, v, u, ctx, tool, source_file, note, wave_id, measured_date)
             for (m, v, u, tool, note) in rows],
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "written": len(rows),
        "metrics": [r[0] for r in rows],
        "source_file": source_file,
        "artifact": artifact_path,
        "context": ctx,
        "db": db_path,
        "wave_number": wave_number,
    }
