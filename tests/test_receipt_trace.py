"""Receipt --trace (item B): the per-expert routing de-risk verdict folds into the receipt."""
from gpu_container.planner.receipt import build_receipt
from gpu_container.planner.activation import ActivationTrace, LayerActivation, analyze_concentration
from gpu_container.profiler.schema import PlacementPlan


def _plan():
    return PlacementPlan(fits=True, verdict="ship", n_cpu_moe=0, n_moe_layers=48,
                         ceiling_decode_tok_s=700.0, predicted_decode_tok_s=300.0,
                         predicted_band_low_tok_s=250.0, predicted_band_high_tok_s=350.0, floor_tok_s=1.0)


def _report(counts, E=64):
    tr = ActivationTrace(model="t", num_experts=E, experts_per_token=8, n_tokens=1000,
                         layers=[LayerActivation(i, list(counts)) for i in range(8)])
    return analyze_concentration(tr)


def test_receipt_carries_routing_verdict_uniform():
    r = build_receipt(_plan(), decode_tok_s=300.0, concentration=_report([125] * 64))
    assert r.routing_cache_helps is False
    assert r.routing_hot_frac_for_coverage is not None
    assert r.routing_concentration is not None
    assert any("near-uniform" in n for n in r.notes)


def test_receipt_carries_routing_verdict_concentrated():
    r = build_receipt(_plan(), decode_tok_s=300.0, concentration=_report([950] * 8 + [7] * 56))
    assert r.routing_cache_helps is True
    assert any("COULD help" in n for n in r.notes)


def test_receipt_without_trace_leaves_routing_none():
    r = build_receipt(_plan(), decode_tok_s=300.0)
    assert r.routing_cache_helps is None
    assert r.routing_hot_frac_for_coverage is None
    assert r.routing_concentration is None


# --- A2: the safety envelope (watchdog peaks) folds into the receipt ---------------------------

def test_receipt_carries_safety_envelope():
    peaks = {"samples": 12, "peak_gpu_power_pct": 41.0, "peak_gpu_vram_used_mib": 18988.0,
             "peak_host_mem_pct": 31.0, "min_host_avail_mib": 44000.0, "stayed_within_envelope": True}
    r = build_receipt(_plan(), decode_tok_s=302.0, peaks=peaks)
    assert r.peak_host_mem_pct == 31.0
    assert r.peak_gpu_power_pct == 41.0
    assert r.safety_samples == 12
    assert r.stayed_within_envelope is True
    assert any("within the safety envelope" in n for n in r.notes)


def test_receipt_safety_envelope_breached_note():
    peaks = {"samples": 3, "peak_host_mem_pct": 95.0, "stayed_within_envelope": False}
    r = build_receipt(_plan(), decode_tok_s=10.0, peaks=peaks)
    assert r.stayed_within_envelope is False
    assert any("BREACHED" in n for n in r.notes)


def test_receipt_without_peaks_leaves_envelope_none():
    r = build_receipt(_plan(), decode_tok_s=300.0)
    assert r.peak_host_mem_pct is None
    assert r.stayed_within_envelope is None
    assert r.safety_samples is None


def test_peaks_do_not_clobber_within_band():
    # Regression: the safety-envelope verdict and the throughput within_band verdict are
    # independent. A breached envelope must NOT flip within_band (they once shared a variable).
    peaks = {"samples": 1, "peak_host_mem_pct": 24.5, "stayed_within_envelope": False}
    r = build_receipt(_plan(), decode_tok_s=300.0, peaks=peaks)   # 300 is inside band [250, 350]
    assert r.within_band is True
    assert r.stayed_within_envelope is False
