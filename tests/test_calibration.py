"""Calibration tests: the receipt-driven recalibration loop.

Pins (1) the store/model math, (2) the planner's calibrated-vs-ceiling behavior, and (3) THE PROOF
that the loop closes — a plan for a measured shape predicts a band that contains the measured decode,
both in-sample and leave-one-out (genuine interpolation, not memorization). The measured numbers are
the milestone 2-3 live Qwen3-30B-A3B receipt; the ceilings are the planner's own closed form.
"""
from gpu_container.planner import (
    CalibrationModel,
    CalibrationPoint,
    CalibrationStore,
    load_seed_points,
    plan_llama_cpp,
    plan_to_calibration_point,
)
from gpu_container.planner.receipt import build_receipt
from gpu_container.profiler import model as m
from gpu_container.profiler.schema import (
    GpuInfo,
    HardwareProfile,
    MemoryInfo,
    PlacementPlan,
    PlatformInfo,
    Profile,
)

QWEN3_MOE = {
    "model_type": "qwen3_moe", "num_hidden_layers": 48, "hidden_size": 2048,
    "moe_intermediate_size": 768, "intermediate_size": 768, "num_attention_heads": 32,
    "num_key_value_heads": 4, "head_dim": 128, "num_experts": 128, "num_experts_per_tok": 8,
    "vocab_size": 151936, "torch_dtype": "bfloat16",
}
# Measured llama-bench decode (tg128) from the live receipt — the ground truth the loop must contain.
QWEN3_MEASURED = {0: 302.4, 24: 41.9, 48: 20.4}


def _live_qwen3_profile():
    """The milestone 2-3 in-container profile: vram_free 29613, measured CPU bw 40.7 GB/s."""
    prof = Profile(
        schema_version="0.1.0", created="2026-06-04",
        hardware=HardwareProfile(
            gpu=GpuInfo(name="RTX 5090", vram_total_mib=32607, vram_free_mib=29613),
            platform=PlatformInfo(os="linux", in_container=True, wsl2=True),
            memory=MemoryInfo(ram_total_gib=60.0, ram_available_gib=60.0, cpu_mem_bw_gbps=40.7),
        ),
    )
    prof.model = m.analyze_config(QWEN3_MOE, name="Qwen3-30B-A3B", quant="gguf-q4_k_m")
    return prof


# --- store + point ---------------------------------------------------------------

def test_seed_has_three_qwen3_points_with_expected_efficiency():
    pts = load_seed_points()
    assert len(pts) == 3
    by_n = {p.n_cpu_moe: p for p in pts}
    assert set(by_n) == {0, 24, 48}
    assert round(by_n[0].efficiency, 2) == 0.41   # in-VRAM, overhead-bound
    assert round(by_n[24].efficiency, 2) == 0.61  # offload, CPU-bw-bound
    assert round(by_n[48].efficiency, 2) == 0.56
    assert by_n[0].regime == "in_vram" and by_n[24].regime == "offload"
    assert by_n[24].offload_fraction == 0.5 and by_n[48].offload_fraction == 1.0


def test_store_roundtrip(tmp_path):
    store = CalibrationStore(str(tmp_path))
    p = CalibrationPoint(model="X", quant="gguf-q4_k_m", n_cpu_moe=12, n_moe_layers=48,
                         ceiling_tok_s=100.0, measured_tok_s=55.0, created="2026-06-04")
    store.add(p)
    back = store.points()
    assert len(back) == 1 and back[0].measured_tok_s == 55.0
    assert round(back[0].efficiency, 3) == 0.55 and back[0].regime == "offload"


def test_store_tolerates_garbage(tmp_path):
    (tmp_path / "broken.json").write_text("{not json")
    (tmp_path / "ignore.txt").write_text("nope")
    assert CalibrationStore(str(tmp_path)).points() == []


# --- model -----------------------------------------------------------------------

def test_estimate_in_vram_centers_on_measured_efficiency():
    est = CalibrationModel(load_seed_points()).estimate("in_vram", 0.0)
    assert est is not None and round(est.efficiency, 2) == 0.41
    assert est.low < 0.41 < est.high and est.high <= 1.0
    assert est.n_samples == 1


def test_estimate_offload_interpolates_over_fraction():
    model = CalibrationModel(load_seed_points())
    at_half = model.estimate("offload", 0.5)
    at_full = model.estimate("offload", 1.0)
    assert round(at_half.efficiency, 2) == 0.61 and round(at_full.efficiency, 2) == 0.56
    # a fraction between the two knots interpolates between their efficiencies
    mid = model.estimate("offload", 0.75).efficiency
    assert at_full.efficiency <= mid <= at_half.efficiency


def test_estimate_returns_none_for_unseen_regime():
    # only an in-VRAM point -> the offload regime has no data -> None (planner falls back to ceiling)
    only_invram = [p for p in load_seed_points() if p.n_cpu_moe == 0]
    assert CalibrationModel(only_invram).estimate("offload", 0.5) is None


# --- planner integration ---------------------------------------------------------

def test_planner_uncalibrated_forecast_is_the_ceiling():
    prof = _live_qwen3_profile()
    plan = plan_llama_cpp(prof, ctx_len=4096)  # no calibration passed
    assert plan.predicted_decode_tok_s == plan.ceiling_decode_tok_s
    assert plan.calibration_n_samples == 0
    assert plan.predicted_band_low_tok_s is None
    assert "uncalibrated" in plan.calibration_basis


def test_planner_calibrated_forecast_is_below_ceiling_with_band():
    prof = _live_qwen3_profile()
    model = CalibrationModel(load_seed_points())
    plan = plan_llama_cpp(prof, ctx_len=4096, calibration=model)
    assert plan.n_cpu_moe == 0  # Qwen3 Q4 fits fully
    assert plan.ceiling_decode_tok_s > plan.predicted_decode_tok_s  # calibrated below the ceiling
    assert plan.predicted_band_low_tok_s < plan.predicted_decode_tok_s < plan.predicted_band_high_tok_s
    assert plan.calibration_n_samples >= 1
    assert "calibrated" in plan.calibration_basis


# --- THE PROOF: the loop closes --------------------------------------------------

def test_recalibration_loop_closes_in_sample():
    """For every measured Qwen3 config, the calibrated plan's band contains the measured decode."""
    prof = _live_qwen3_profile()
    model = CalibrationModel(load_seed_points())
    for n, measured in QWEN3_MEASURED.items():
        plan = plan_llama_cpp(prof, ctx_len=4096, calibration=model, force_n_cpu_moe=n)
        rec = build_receipt(plan, decode_tok_s=measured, method="seed")
        assert rec.within_band is True, f"N={n}: {measured} not in band " \
            f"[{plan.predicted_band_low_tok_s}, {plan.predicted_band_high_tok_s}]"
        assert any("loop closed" in note for note in rec.notes)


def test_recalibration_loop_closes_leave_one_out():
    """The stronger proof: hold out N=24, calibrate from N=0 + N=48 only, predict N=24 -> still in band.
    This is genuine generalization across the offload regime, not memorization of the held-out point."""
    prof = _live_qwen3_profile()
    held_out_n, measured = 24, QWEN3_MEASURED[24]
    train = [p for p in load_seed_points() if p.n_cpu_moe != held_out_n]
    model = CalibrationModel(train)
    plan = plan_llama_cpp(prof, ctx_len=4096, calibration=model, force_n_cpu_moe=held_out_n)
    rec = build_receipt(plan, decode_tok_s=measured, method="leave-one-out")
    assert rec.within_band is True, \
        f"LOO N=24: {measured} not in [{plan.predicted_band_low_tok_s}, {plan.predicted_band_high_tok_s}]"


def test_receipt_records_efficiency_and_band_membership():
    plan = PlacementPlan(fits=True, verdict="ship", n_cpu_moe=0, predicted_decode_tok_s=300.0,
                         ceiling_decode_tok_s=738.0, predicted_band_low_tok_s=225.0,
                         predicted_band_high_tok_s=375.0, floor_tok_s=1.0)
    rec = build_receipt(plan, decode_tok_s=302.0, method="t")
    assert rec.realized_efficiency_pct == round(100 * 302.0 / 738.0, 1)  # vs ceiling, the seed
    assert rec.decode_error_pct == round(100 * (302.0 - 300.0) / 300.0, 1)  # vs calibrated forecast
    assert rec.within_band is True


def test_plan_to_calibration_point_feeds_the_store(tmp_path):
    """The write-back: a (plan, measured) pair -> a point that reloads with the right efficiency."""
    prof = _live_qwen3_profile()
    plan = plan_llama_cpp(prof, ctx_len=4096, force_n_cpu_moe=24)
    point = plan_to_calibration_point(plan, measured_decode_tok_s=41.9, model_name="Qwen3-30B-A3B",
                                      quant="gguf-q4_k_m", created="2026-06-04", source="test")
    store = CalibrationStore(str(tmp_path))
    store.add(point)
    reloaded = store.points()[0]
    assert reloaded.n_cpu_moe == 24 and reloaded.measured_tok_s == 41.9
    assert 0.55 < reloaded.efficiency < 0.65  # ~0.61 against the N=24 ceiling


def test_seed_ceilings_consistent_with_current_planner():
    """Guard: the bundled seed's stored ceilings must still match the planner's closed form, or the
    seed efficiencies silently mis-scale every prediction. Re-run scripts/gen_calibration_seed.py."""
    prof = _live_qwen3_profile()
    for p in load_seed_points():
        plan = plan_llama_cpp(prof, ctx_len=p.ctx_len or 4096, force_n_cpu_moe=p.n_cpu_moe)
        assert abs(plan.ceiling_decode_tok_s - p.ceiling_tok_s) / p.ceiling_tok_s < 0.02


# --- the CLI loop ----------------------------------------------------------------

def test_plan_cli_calibrates_by_default(tmp_path):
    from gpu_container.planner.cli import main as plan_main
    from gpu_container.profiler.schema import PlacementPlan

    prof_path = tmp_path / "profile.json"
    prof_path.write_text(_live_qwen3_profile().to_json(), encoding="utf-8")
    out = tmp_path / "plan.json"
    rc = plan_main(["--profile", str(prof_path), "--quant", "gguf-q4_k_m", "-o", str(out)])
    assert rc == 0
    plan = PlacementPlan.from_json(out.read_text(encoding="utf-8"))
    assert plan.calibration_n_samples >= 1                       # bundled seed was applied
    assert plan.predicted_decode_tok_s < plan.ceiling_decode_tok_s


def test_receipt_cli_writes_back_to_store(tmp_path):
    from gpu_container.planner.cli import main as plan_main
    from gpu_container.planner.receipt_cli import main as receipt_main

    prof_path = tmp_path / "profile.json"
    prof_path.write_text(_live_qwen3_profile().to_json(), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    plan_main(["--profile", str(prof_path), "--quant", "gguf-q4_k_m", "-o", str(plan_path)])

    calib_dir = tmp_path / "calib"
    receipt_path = tmp_path / "receipt.json"
    rc = receipt_main(["--plan", str(plan_path), "--decode-tok-s", "302.4",
                       "--model-name", "Qwen3-30B-A3B", "--quant", "gguf-q4_k_m",
                       "--calibration-dir", str(calib_dir), "--created", "2026-06-04",
                       "-o", str(receipt_path)])
    assert rc == 0  # cleared floor, at/below ceiling
    assert receipt_path.is_file()
    # the write-back left exactly one point in the store
    assert calib_dir.is_dir() and list(calib_dir.glob("*.json"))
    pts = CalibrationStore(str(calib_dir)).points()
    assert len(pts) == 1 and pts[0].n_cpu_moe == 0 and pts[0].measured_tok_s == 302.4
