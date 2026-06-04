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
