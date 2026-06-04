"""Tests for activation-trace concentration analysis — the per-expert-cache de-risk gate.

Two anchor cases: a CONCENTRATED workload (a small hot set dominates → a cache helps) and a
UNIFORM one (routing spread evenly → a cache is pointless). Plus serialization + edge cases.
"""
from gpu_container.planner.activation import (
    ActivationTrace,
    LayerActivation,
    analyze_concentration,
    load_trace,
)


def _uniform(n_layers: int, E: int, per_expert: int = 125) -> ActivationTrace:
    """Every expert equally used — the no-cache-win case."""
    return ActivationTrace(
        model="uniform-moe", num_experts=E, experts_per_token=8, n_tokens=1000,
        layers=[LayerActivation(i, [per_expert] * E) for i in range(n_layers)],
    )


def _concentrated(n_layers: int, E: int, hot: int = 8, hot_count: int = 950,
                  cold_count: int = 7) -> ActivationTrace:
    """A small hot set carries most routing — the cache-helps case."""
    counts = [hot_count] * hot + [cold_count] * (E - hot)
    return ActivationTrace(
        model="concentrated-moe", num_experts=E, experts_per_token=8, n_tokens=1000,
        layers=[LayerActivation(i, list(counts)) for i in range(n_layers)],
    )


def test_uniform_trace_cache_does_not_help():
    rep = analyze_concentration(_uniform(12, 64), coverage_target=0.90)
    assert rep.cache_helps is False
    assert rep.concentration_score < 0.05            # ~0 for a uniform distribution
    assert rep.hot_frac_for_coverage >= 0.85         # need ~90% of experts for 90% coverage


def test_concentrated_trace_cache_helps():
    rep = analyze_concentration(_concentrated(12, 64), coverage_target=0.90)
    assert rep.cache_helps is True
    assert rep.concentration_score > 0.3
    assert rep.hot_frac_for_coverage < 0.5           # a small resident set covers 90%


def test_concentration_orders_uniform_below_concentrated():
    u = analyze_concentration(_uniform(8, 64))
    c = analyze_concentration(_concentrated(8, 64))
    assert c.concentration_score > u.concentration_score
    assert c.hot_frac_for_coverage < u.hot_frac_for_coverage


def test_roundtrip_serialization():
    t = _concentrated(3, 16)
    back = ActivationTrace.from_dict(t.to_dict())
    assert back.model == t.model
    assert back.num_experts == t.num_experts
    assert len(back.layers) == 3
    assert back.layers[0].expert_counts == t.layers[0].expert_counts
    assert ActivationTrace.from_json(t.to_json()).n_tokens == t.n_tokens


def test_empty_trace_is_graceful():
    rep = analyze_concentration(
        ActivationTrace(model="empty", num_experts=64, experts_per_token=8, n_tokens=0, layers=[])
    )
    assert rep.cache_helps is False
    assert rep.n_layers == 0


def test_zero_mass_layer_is_skipped():
    t = ActivationTrace(model="z", num_experts=8, experts_per_token=2, n_tokens=10,
                        layers=[LayerActivation(0, [0] * 8), LayerActivation(1, [5] * 8)])
    rep = analyze_concentration(t)
    assert rep.n_layers == 1                          # the zero-mass layer drops out, not guessed


def test_single_expert_layer_is_fully_concentrated():
    t = ActivationTrace(model="one", num_experts=1, experts_per_token=1, n_tokens=10,
                        layers=[LayerActivation(0, [10])])
    rep = analyze_concentration(t)
    assert rep.concentration_score == 1.0            # degenerate: trivially concentrated, no crash
    assert rep.n_layers == 1


def test_workload_dependence_note_present():
    rep = analyze_concentration(_uniform(4, 32))
    assert any("workload" in n.lower() for n in rep.notes)


def test_load_trace_is_tolerant(tmp_path):
    assert load_trace(tmp_path / "nope.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_trace(bad) is None
    good = tmp_path / "good.json"
    good.write_text(_concentrated(2, 8).to_json(), encoding="utf-8")
    tr = load_trace(good)
    assert tr is not None
    assert tr.num_experts == 8
    assert len(tr.layers) == 2
