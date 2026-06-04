"""Measurement-layer tests: baseline emission, schema round-trip of measured fields, and
honest no-crash degradation when CUDA/fio are absent (the host, off-GPU).

The benchmarks themselves (real GB/s, IOPS, pinnable ceiling) are environment-dependent and
verified in-container — asserting a number here would be dishonest. These tests pin the
deterministic glue: what gets recorded, how, and that nothing raises when a probe can't run.
"""
import sqlite3

from gpu_container.profiler import baseline as baseline_mod
from gpu_container.profiler import cuda_bench, nvme_bench
from gpu_container.profiler.schema import (
    BandwidthInfo,
    GpuInfo,
    HardwareProfile,
    MemoryInfo,
    PlatformInfo,
    Profile,
)

# The relevant slice of the docker-knowledge findings.db schema (measurements + waves).
_DDL = """
CREATE TABLE measurements (
  id INTEGER PRIMARY KEY, metric TEXT NOT NULL, value REAL, unit TEXT, context TEXT,
  tool TEXT, source_file TEXT, note TEXT, wave_id INTEGER, measured_date TEXT
);
CREATE TABLE waves (
  id INTEGER PRIMARY KEY, wave_number INTEGER NOT NULL UNIQUE, title TEXT NOT NULL,
  dispatched_date TEXT NOT NULL
);
CREATE VIEW v_baseline AS SELECT metric, value, unit, context, tool, measured_date, source_file
  FROM measurements ORDER BY metric, context;
"""


def _measured_profile() -> Profile:
    return Profile(
        schema_version="0.1.0", created="2026-06-04",
        hardware=HardwareProfile(
            gpu=GpuInfo(name="NVIDIA GeForce RTX 5090", vram_total_mib=32607,
                        vram_free_mib=30000, vram_reserved_mib=420, vram_source="pynvml-v2"),
            platform=PlatformInfo(os="linux", in_container=True, wsl2=True,
                                  container_runtime="docker", uvm_oversubscription=False),
            bandwidth=BandwidthInfo(
                pcie_h2d_gbps=52.3, pcie_d2h_gbps=51.1, nvme_seq_read_gbps=12.0,
                nvme_rand_qd1_read_iops=18000.0, nvme_rand_qd1_read_mbps=70.3,
                method="pcie:cudaMemcpy-pinned-cudaEvent; nvme:fio-direct-libaio",
                details={"pcie": {"iters": 11, "buffer_mib": 256, "convention": "1e9"},
                         "nvme": {"ioengine": "libaio", "fs_type": "ext4",
                                  "mount": "/bench", "size_gib": 4}},
            ),
            memory=MemoryInfo(ram_total_gib=63.4, pinnable_ceiling_gib=0.44,
                              pinnable_capped=False,
                              pinnable_method="escalating cudaHostAlloc probe"),
        ),
    )


def _seed_db(path: str) -> None:
    c = sqlite3.connect(path)
    c.executescript(_DDL)
    c.execute("INSERT INTO waves (wave_number, title, dispatched_date) VALUES (2, 'Measurement', '2026-06-04')")
    c.commit()
    c.close()


def test_emit_baseline_writes_measured_rows(tmp_path):
    db = tmp_path / "findings.db"
    _seed_db(str(db))
    prof = _measured_profile()

    summary = baseline_mod.emit_baseline(prof, db_path=str(db), baselines_dir=str(tmp_path / "baselines"))

    # 8 measured readouts: pcie h2d/d2h, nvme seq/qd1-iops/qd1-mbps, pinnable, vram total/free
    assert summary["written"] == 8
    assert summary["context"] == "in-container wsl2"
    assert "pcie_h2d_gbps" in summary["metrics"] and "pinnable_ram_ceiling_gib" in summary["metrics"]
    assert (tmp_path / "baselines").exists()  # artifact dropped

    c = sqlite3.connect(str(db))
    rows = dict(c.execute("SELECT metric, value FROM measurements").fetchall())
    wave_id = c.execute("SELECT wave_id FROM measurements WHERE metric='pcie_h2d_gbps'").fetchone()[0]
    units = dict(c.execute("SELECT metric, unit FROM measurements").fetchall())
    c.close()
    assert rows["pcie_h2d_gbps"] == 52.3
    assert rows["nvme_rand_qd1_iops"] == 18000.0
    assert units["nvme_rand_qd1_mbps"] == "MB/s" and units["pcie_d2h_gbps"] == "GB/s"
    assert wave_id == 1  # the seeded wave row's PK (wave_number 2)


def test_emit_baseline_idempotent_by_source_file(tmp_path):
    db = tmp_path / "findings.db"
    _seed_db(str(db))
    prof = _measured_profile()

    baseline_mod.emit_baseline(prof, db_path=str(db), baselines_dir=str(tmp_path / "b"))
    baseline_mod.emit_baseline(prof, db_path=str(db), baselines_dir=str(tmp_path / "b"))  # re-emit

    c = sqlite3.connect(str(db))
    n = c.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
    c.close()
    assert n == 8  # replaced, not duplicated


def test_emit_baseline_refuses_unmeasured_profile(tmp_path):
    db = tmp_path / "findings.db"
    _seed_db(str(db))
    bare = Profile(
        schema_version="0.1.0", created="2026-06-04",
        hardware=HardwareProfile(gpu=GpuInfo(name="unknown"), platform=PlatformInfo(os="linux")),
    )
    summary = baseline_mod.emit_baseline(bare, db_path=str(db), baselines_dir=str(tmp_path / "b"))
    assert "error" in summary and "nothing to emit" in summary["error"]


def test_emit_baseline_missing_db():
    summary = baseline_mod.emit_baseline(_measured_profile(), db_path="/no/such/findings.db")
    assert "error" in summary and "not found" in summary["error"]


def test_schema_roundtrip_preserves_measured_fields():
    prof = _measured_profile()
    p2 = Profile.from_json(prof.to_json())
    bw = p2.hardware.bandwidth
    assert bw.pcie_h2d_gbps == 52.3 and bw.nvme_rand_qd1_read_mbps == 70.3
    assert isinstance(bw.details, dict) and bw.details["nvme"]["fs_type"] == "ext4"
    assert p2.hardware.memory.pinnable_ceiling_gib == 0.44
    assert p2.hardware.memory.pinnable_capped is False
    assert p2.hardware.gpu.vram_reserved_mib == 420


def test_benches_degrade_without_crashing_off_gpu():
    # On a host without libcudart / a CUDA device, the probes return honest error dicts.
    assert isinstance(cuda_bench.available(), bool)
    pcie = cuda_bench.measure_pcie()
    assert pcie["h2d_gbps"] is None or isinstance(pcie["h2d_gbps"], float)
    pin = cuda_bench.measure_pinnable_ceiling()
    assert "ceiling_mib" in pin


def test_resolve_bench_dir_explicit_and_missing(monkeypatch):
    monkeypatch.delenv("GPU_CONTAINER_BENCH_DIR", raising=False)
    assert nvme_bench.resolve_bench_dir("/data/nvme") == ("/data/nvme", None)
    monkeypatch.setenv("GPU_CONTAINER_BENCH_DIR", "/envdir")
    assert nvme_bench.resolve_bench_dir() == ("/envdir", None)
